from __future__ import annotations

import re
from collections import defaultdict
from decimal import Decimal
from difflib import SequenceMatcher

from erp import models as m


ZERO = Decimal("0")
_STOPWORDS = {
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einer", "einem", "einen",
    "und", "oder", "mit", "ohne", "bei", "auf", "aus", "in", "im", "am", "an", "zum", "zur",
    "von", "vorh", "vorhanden", "vorhandene", "vorhandenen", "inkl", "inklusive", "ggf", "ca",
    "stk", "stueck", "pausch", "pauschal", "meter", "qm", "m2", "durchfuehren", "durchgefuehrt",
}
_TECH_SHORT_TOKENS = {"wc", "ap", "up", "dn"}
_ACTION_FEATURES = {
    "montage", "demontage", "pruef", "einbring", "verleg", "anschliess", "erneuer", "abkleb",
    "abdeck", "bohr", "stemm", "abdicht", "reinig", "wartung",
}
# Domain concepts are deliberately conservative. They normalize common German
# B&O wording differences without inventing a price or crossing variants.
_FEATURE_RULES = (
    (r"\b(?:wc|toilett\w*)\b", "wc"),
    (r"dusch|braus", "dusch"),
    (r"armatur", "armatur"),
    (r"abtrenn|trennwand", "abtrennung"),
    (r"rinn", "rinne"),
    (r"ablauf|entwaesser", "ablauf"),
    (r"waschtisch|waschbecken", "waschtisch"),
    (r"spuelbecken|spuele", "spuele"),
    (r"spuelkasten", "spuelkasten"),
    (r"badewanne|wannen", "wanne"),
    (r"urinal", "urinal"),
    (r"bidet", "bidet"),
    (r"siphon|sifon", "siphon"),
    (r"dicht", "dicht"),
    (r"pruef|kontroll", "pruef"),
    (r"ausgleich|nivellier|spachtelmasse", "ausgleich"),
    (r"\bmasse\b|ausgleichsmasse|nivelliermasse", "masse"),
    (r"aufputz|\bap\b", "ap"),
    (r"unterputz|\bup\b", "up"),
    (r"montag|montier|einbau|einbauen", "montage"),
    (r"demont|ausbau|ausbauen", "demontage"),
    (r"einbring|eingebrach", "einbring"),
    (r"verleg", "verleg"),
    (r"anschliess|anschluss|anschluess", "anschliess"),
    (r"erneuer|austausch|ersetzen|ersetz", "erneuer"),
    (r"abdicht", "abdicht"),
    (r"abkleb", "abkleb"),
    (r"abdeck", "abdeck"),
    (r"bohr", "bohr"),
    (r"stemm", "stemm"),
    (r"reinig", "reinig"),
    (r"wartung|warten", "wartung"),
    (r"durchlauferhitzer", "durchlauferhitzer"),
    (r"warmwasserbereiter", "warmwasserbereiter"),
    (r"heizkoerp|radiator", "heizkoerper"),
    (r"thermostat", "thermostat"),
    (r"ventil", "ventil"),
    (r"pumpe", "pumpe"),
    (r"rohr|leitung", "rohr"),
    (r"fliese|plattenbelag|wandplatte|bodenplatte", "fliese"),
    (r"silikon|dauerelast", "silikon"),
    (r"fug", "fuge"),
    (r"estrich", "estrich"),
    (r"daemm|isolier", "daemmung"),
)
_CONFLICT_GROUPS = (
    frozenset({"ap", "up"}),
    frozenset({"montage", "demontage"}),
)


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


def _ascii(value: str) -> str:
    return (value or "").lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")


def _canonical_word(word: str) -> str:
    word = _ascii(word)
    if re.fullmatch(r"montag(?:e|en)?|montier(?:en|t|ung)?", word):
        return "montage"
    if re.fullmatch(r"demontag(?:e|en)?|demontier(?:en|t|ung)?", word):
        return "demontage"
    if word.startswith("pruef"):
        return "pruef"
    if word.startswith(("verleg", "verlege")):
        return "verleg"
    if word.startswith(("einbring", "eingebrach")):
        return "einbring"
    if word.startswith(("abkleb", "abgekle")):
        return "abkleb"
    if word.startswith(("abdeck", "abgedeck")):
        return "abdeck"
    if word.startswith(("anschliess", "anschluess")):
        return "anschliess"
    if word.startswith(("erneuer", "erneu")):
        return "erneuer"
    if word == "aufputz":
        return "ap"
    if word == "unterputz":
        return "up"
    return word


def _tokens(value: str) -> tuple[str, ...]:
    raw = re.findall(r"[a-zA-ZäöüÄÖÜß0-9]+", value or "")
    result = []
    for word in raw:
        token = _canonical_word(word)
        if token.isdigit() or token in _STOPWORDS:
            continue
        if len(token) < 3 and token not in _TECH_SHORT_TOKENS:
            continue
        if token not in result:
            result.append(token)
    return tuple(result)


def _domain_features(value: str) -> set[str]:
    normalized = _ascii(value)
    return {feature for pattern, feature in _FEATURE_RULES if re.search(pattern, normalized)}


def _has_conflict(query_features: set[str], row_features: set[str]) -> bool:
    for group in _CONFLICT_GROUPS:
        query_variant = query_features & group
        row_variant = row_features & group
        if query_variant and row_variant and not (query_variant & row_variant):
            return True
    return False


def _fuzzy_overlap(query_tokens: set[str], row_tokens: set[str]) -> int:
    """Count close German compound/stem matches after exact tokens are removed."""
    unmatched_query = [token for token in query_tokens if token not in row_tokens and len(token) >= 5]
    unmatched_row = [token for token in row_tokens if token not in query_tokens and len(token) >= 5]
    matched = 0
    used = set()
    for query in unmatched_query:
        best_index = None
        best_ratio = 0.0
        for index, row in enumerate(unmatched_row):
            if index in used:
                continue
            ratio = SequenceMatcher(None, query, row).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_index = index
        if best_index is not None and best_ratio >= 0.78:
            used.add(best_index)
            matched += 1
    return matched


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
    """Resolve internal KAYI services against the imported B&O VA04 library.

    Resolution is deterministic and price-safe: explicit external codes still
    win, while this fallback only selects an existing priced B&O row. German
    trade synonyms/compounds are normalized (for example Dusch/Brause,
    Dichtigkeit/Dichtheit and Ausgleich/Nivellier). Conflicting AP/UP and
    Montage/Demontage variants are rejected.
    """
    queries = {}
    inverted = defaultdict(set)
    for item in items:
        name = getattr(item, "name", "") or ""
        description = getattr(item, "description", "") or ""
        name_tokens = set(_tokens(name))
        tokens = name_tokens or set(_tokens(" ".join(part for part in (name, description) if part)))
        features = _domain_features(name) or _domain_features(" ".join(part for part in (name, description) if part))
        if len(tokens) < 2 and len(features) < 2:
            continue
        queries[item.pk] = {"tokens": tokens, "features": features}
        for key in tokens | features:
            inverted[key].add(item.pk)
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
        description = getattr(row, "description", "") or ""
        row_tokens = set(_tokens(description))
        row_features = _domain_features(description)
        if not row_tokens and not row_features:
            continue
        candidate_ids = set()
        for key in row_tokens | row_features:
            candidate_ids.update(inverted.get(key, ()))
        for item_id in candidate_ids:
            query = queries[item_id]
            query_tokens = query["tokens"]
            query_features = query["features"]
            if _has_conflict(query_features, row_features):
                continue

            exact_overlap = len(query_tokens & row_tokens)
            fuzzy_overlap = _fuzzy_overlap(query_tokens, row_tokens)
            feature_overlap = len(query_features & row_features)
            query_actions = query_features & _ACTION_FEATURES
            row_actions = row_features & _ACTION_FEATURES
            subject_query = query_features - _ACTION_FEATURES
            subject_overlap = len(subject_query & row_features)

            # Domain-aware path. At least one subject concept must agree. For
            # two-concept services (e.g. Waschtisch + Montage) both concepts
            # are normally required; longer names tolerate one extra qualifier.
            domain_ok = False
            if len(query_features) >= 2 and subject_query and subject_overlap >= 1:
                action_ok = not query_actions or not row_actions or bool(query_actions & row_actions)
                coverage = feature_overlap / max(len(query_features), 1)
                minimum = 1.0 if len(query_features) == 2 else 0.60
                domain_ok = action_ok and coverage >= minimum

            # Legacy/fuzzy path keeps coverage for services outside the domain
            # lexicon. Fuzzy matching is only a supplement to an exact/action
            # anchor, never a free nearest-neighbour price guess.
            token_matches = exact_overlap + fuzzy_overlap
            token_ok = token_matches >= 2
            if len(query_tokens) == 2:
                token_ok = token_matches >= 2
            elif len(query_tokens) >= 3:
                token_ok = token_matches / len(query_tokens) >= 0.66

            if not domain_ok and not token_ok:
                continue

            feature_coverage = feature_overlap / max(len(query_features), 1) if query_features else 0.0
            token_coverage = min(token_matches / max(len(query_tokens), 1), 1.0) if query_tokens else 0.0
            precision = (feature_overlap + exact_overlap) / max(len(row_features) + len(row_tokens), 1)
            extra_words = max((len(row_features) + len(row_tokens)) - (feature_overlap + exact_overlap), 0)
            price_score = _candidate_score(row) or (0, 0, 0, 0)
            score = (feature_coverage, token_coverage, precision, -extra_words, price_score)
            previous = best.get(item_id)
            if previous is None or score > previous[0]:
                best[item_id] = (score, row)
    return {item_id: pair[1] for item_id, pair in best.items()}


def apply_effective_prices(org, catalog_items):
    """Attach effective price/source attributes to CatalogItem objects.

    Priority:
    1. non-zero B&O PriceItem addressed by KAYI code or external code;
    2. CatalogItem's own non-zero sales price;
    3. deterministic semantic B&O match for internal KAYI service codes;
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
