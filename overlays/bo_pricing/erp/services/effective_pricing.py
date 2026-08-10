from __future__ import annotations

import re
from collections import defaultdict
from decimal import Decimal

from erp import models as m


ZERO = Decimal("0")
_STOPWORDS = {
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einer", "einem", "einen",
    "und", "oder", "mit", "ohne", "bei", "auf", "aus", "in", "im", "am", "an", "zum", "zur",
    "von", "vorh", "vorhanden", "vorhandene", "vorhandenen", "inkl", "inklusive", "ggf", "ca",
    "stk", "stueck", "pausch", "pauschal", "meter", "qm", "m2",
}


def _positive(value):
    return value is not None and value > ZERO


def _source_text(price_item) -> str:
    source = price_item.source
    supplier = getattr(source, "supplier", None)
    parts = [
        getattr(source, "name", "") or "",
        getattr(source, "original_filename", "") or "",
        getattr(supplier, "name", "") or "",
        str(getattr(source, "import_summary", "") or ""),
        str(getattr(price_item, "external_data", "") or ""),
    ]
    return " ".join(parts).lower()


def _is_bo(price_item) -> bool:
    raw = _source_text(price_item)
    compact = re.sub(r"\s+", " ", raw)
    return any(token in compact for token in (
        "b&o", "b & o", "b+o", "b + o", "b und o", "b-und-o", "b_o",
    ))


def _price_value(price_item):
    if _positive(price_item.sales_price):
        return price_item.sales_price, "sales"
    if _positive(price_item.purchase_price):
        return price_item.purchase_price, "purchase"
    return None, "none"


def _candidate_score(price_item):
    value, mode = _price_value(price_item)
    if value is None:
        return None
    imported_at = getattr(price_item.source, "imported_at", None)
    imported_score = imported_at.timestamp() if imported_at else 0
    return (
        1 if _is_bo(price_item) else 0,
        1 if mode == "sales" else 0,
        imported_score,
        getattr(price_item, "pk", 0) or 0,
    )


def _canonical_word(word: str) -> str:
    word = (word or "").lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    if re.fullmatch(r"montag(?:e|en)?|montier(?:en|t|ung)?", word):
        return "montage"
    if re.fullmatch(r"demontag(?:e|en)?|demontier(?:en|t|ung)?", word):
        return "demontage"
    if word.startswith(("verleg", "verlege")):
        return "verleg"
    if word.startswith(("einbring", "eingebrach")):
        return "einbring"
    if word.startswith(("abkleb", "abgekle")):
        return "abkleb"
    if word.startswith(("abdeck", "abgedeck")):
        return "abdeck"
    if word.startswith(("anschliess", "anschließ")):
        return "anschliess"
    if word.startswith(("erneuer", "erneu")):
        return "erneuer"
    return word


def _tokens(value: str) -> tuple[str, ...]:
    raw = re.findall(r"[a-zA-ZäöüÄÖÜß0-9]+", value or "")
    result = []
    for word in raw:
        token = _canonical_word(word)
        if len(token) < 3 or token in _STOPWORDS or token.isdigit():
            continue
        if token not in result:
            result.append(token)
    return tuple(result)


def _external_codes(value):
    """Flatten CatalogItem.external_codes without assuming one importer schema."""
    result = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_l = str(key).lower()
            if isinstance(item, (dict, list, tuple, set)):
                result.extend(_external_codes(item))
            elif item not in (None, "") and any(token in key_l for token in ("code", "leist", "position", "bo", "b&o", "va04")):
                result.append(str(item).strip())
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            result.extend(_external_codes(item))
    elif value not in (None, ""):
        result.append(str(value).strip())
    return [code for code in result if code]


def _best_by_code(org, codes):
    normalized_codes = [str(code or "").strip() for code in codes if str(code or "").strip()]
    if not normalized_codes:
        return {}
    rows = (
        m.PriceItem.objects.filter(
            organization=org,
            code__in=normalized_codes,
            source__active=True,
        )
        .select_related("source", "source__supplier")
        .order_by("code")
    )
    result = {}
    for row in rows:
        score = _candidate_score(row)
        if score is None:
            continue
        key = (row.code or "").strip()
        previous = result.get(key)
        if previous is None or score > previous[0]:
            result[key] = (score, row)
    return {key: value[1] for key, value in result.items()}


def _semantic_bo_matches(org, items):
    """Match KAYI's short internal service names to the imported B&O catalogue.

    KAYI intentionally keeps stable internal codes such as S1002 while B&O uses
    VA04 codes. A semantic fallback is therefore required when an explicit
    external code has not yet been stored. It is deliberately conservative:
    at least two meaningful service tokens must match, all tokens of a two-word
    KAYI service must be present, and the shortest/closest B&O description wins.
    Price rows are streamed so the 13k+ reference library is not loaded twice.
    """
    queries = {}
    inverted = defaultdict(set)
    for item in items:
        tokens = _tokens(" ".join(part for part in (getattr(item, "name", ""), getattr(item, "description", "")) if part))
        name_tokens = _tokens(getattr(item, "name", ""))
        if len(name_tokens) >= 2:
            tokens = name_tokens
        if len(tokens) < 2:
            continue
        queries[item.pk] = tokens
        for token in tokens:
            inverted[token].add(item.pk)
    if not queries:
        return {}

    best = {}
    rows = (
        m.PriceItem.objects.filter(organization=org, source__active=True)
        .select_related("source", "source__supplier")
        .only("id", "code", "description", "sales_price", "purchase_price", "external_data", "source__id", "source__name", "source__original_filename", "source__import_summary", "source__imported_at", "source__active", "source__supplier__id", "source__supplier__name")
        .iterator(chunk_size=1000)
    )
    for row in rows:
        if not _is_bo(row) or _price_value(row)[0] is None:
            continue
        row_tokens = set(_tokens(getattr(row, "description", "")))
        if not row_tokens:
            continue
        candidate_ids = set()
        for token in row_tokens:
            candidate_ids.update(inverted.get(token, ()))
        for item_id in candidate_ids:
            query = queries[item_id]
            qset = set(query)
            overlap = len(qset & row_tokens)
            coverage = overlap / len(qset)
            if overlap < 2:
                continue
            if len(qset) == 2 and coverage < 1:
                continue
            if len(qset) >= 3 and coverage < 0.75:
                continue
            precision = overlap / max(len(row_tokens), 1)
            extra_words = max(len(row_tokens) - overlap, 0)
            price_score = _candidate_score(row) or (0, 0, 0, 0)
            score = (coverage, precision, -extra_words, price_score)
            previous = best.get(item_id)
            if previous is None or score > previous[0]:
                best[item_id] = (score, row)
    return {item_id: pair[1] for item_id, pair in best.items()}


def apply_effective_prices(org, catalog_items):
    """Attach effective price/source attributes to CatalogItem objects.

    Priority:
    1. non-zero B&O PriceItem addressed by KAYI code or external code;
    2. CatalogItem's own non-zero sales price;
    3. conservative semantic B&O match for internal KAYI service codes;
    4. best other active PriceItem addressed by code;
    5. zero only when no usable price exists anywhere.

    The database rows are not mutated. Every selected reference keeps its B&O
    code and source id on the in-memory catalog item for audit/UI purposes.
    """
    items = list(catalog_items)
    lookup_codes = []
    codes_by_item = {}
    for item in items:
        codes = [(item.code or "").strip()] + _external_codes(getattr(item, "external_codes", {}))
        codes = [code for index, code in enumerate(codes) if code and code not in codes[:index]]
        codes_by_item[item.pk] = codes
        lookup_codes.extend(codes)
    best = _best_by_code(org, lookup_codes)

    unresolved = []
    matched = {}
    fallback_rows = {}
    for item in items:
        candidates = [best.get(code) for code in codes_by_item.get(item.pk, ()) if best.get(code) is not None]
        bo_candidates = [row for row in candidates if _is_bo(row) and _price_value(row)[0] is not None]
        if bo_candidates:
            row = bo_candidates[0]
            matched[item.pk] = (row, "code" if (row.code or "").strip() == (item.code or "").strip() else "external_code")
            continue
        if candidates:
            row = candidates[0]
            fallback_rows[item.pk] = (row, "code" if (row.code or "").strip() == (item.code or "").strip() else "external_code")
        if not _positive(item.sales_price):
            unresolved.append(item)

    semantic = _semantic_bo_matches(org, unresolved)
    for item_id, row in semantic.items():
        matched[item_id] = (row, "semantic")
    for item_id, pair in fallback_rows.items():
        if item_id not in matched:
            matched[item_id] = pair

    for item in items:
        pair = matched.get(item.pk)
        row, match_kind = pair if pair else (None, "none")
        row_value, row_mode = _price_value(row) if row is not None else (None, "none")
        catalog_value = item.sales_price if _positive(item.sales_price) else None
        use_reference = bool(row is not None and _is_bo(row) and row_value is not None)

        if use_reference:
            effective = row_value
            source_name = getattr(row.source, "name", "") or getattr(getattr(row.source, "supplier", None), "name", "") or "B&O"
            source_kind = "B&O"
        elif catalog_value is not None:
            effective = catalog_value
            source_name = item.supplier or "Katalog"
            source_kind = "Katalog"
            row = None
            match_kind = "catalog"
        elif row_value is not None:
            effective = row_value
            source_name = getattr(row.source, "name", "") or getattr(getattr(row.source, "supplier", None), "name", "") or "Preisquelle"
            source_kind = "Preisquelle"
        else:
            effective = ZERO
            source_name = "Kein Preis hinterlegt"
            source_kind = "Fehlt"

        item.effective_sales_price = effective
        item.effective_price_source = source_name
        item.effective_price_source_kind = source_kind
        item.effective_price_reference_id = row.pk if row is not None else None
        item.effective_price_reference_code = (row.code or "").strip() if row is not None else ""
        item.effective_price_match_kind = match_kind
        item.effective_price_mode = row_mode if row is not None else "catalog"
    return items


def catalog_with_effective_prices(org, *, limit=500):
    queryset = m.CatalogItem.objects.filter(organization=org, active=True).order_by("name")[:limit]
    return apply_effective_prices(org, queryset)


def effective_price_for_catalog_item(org, catalog_item):
    apply_effective_prices(org, [catalog_item])
    return catalog_item.effective_sales_price
