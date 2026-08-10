from __future__ import annotations

import re
from decimal import Decimal

from django.db.models import Q

from erp import models as m


ZERO = Decimal("0")
_ALIAS_GROUPS = (
    ("dusch", "braus"),
    ("waschtisch", "waschbecken"),
    ("dicht", "dichtigkeit", "dichtheit"),
    ("ausgleich", "nivellier", "spachtel"),
    ("rinne", "ablauf", "entwaesser"),
    ("montage", "montieren", "einbau", "einbauen"),
    ("demontage", "demontieren", "ausbau", "ausbauen"),
    ("erneuern", "austausch", "austauschen", "ersetzen"),
    ("heizkoerper", "radiator"),
    ("toilette", "wc"),
)


def _ascii(value: str) -> str:
    return (value or "").lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")


def _source_text(source) -> str:
    supplier = getattr(source, "supplier", None)
    return " ".join(
        str(part or "")
        for part in (
            getattr(source, "name", ""),
            getattr(source, "original_filename", ""),
            getattr(supplier, "name", ""),
            getattr(source, "import_summary", ""),
        )
    ).lower()


def is_bo_source(source) -> bool:
    compact = re.sub(r"\s+", " ", _source_text(source))
    return any(token in compact for token in ("b&o", "b & o", "b+o", "b + o", "b und o", "b-und-o", "b_o"))


def bo_source_ids(org) -> list[int]:
    sources = m.PriceSource.objects.filter(organization=org, active=True).select_related("supplier")
    return [source.pk for source in sources if is_bo_source(source)]


def _price(row):
    if row.sales_price is not None and row.sales_price > ZERO:
        return row.sales_price, "VK"
    if row.purchase_price is not None and row.purchase_price > ZERO:
        return row.purchase_price, "EK"
    return None, ""


def _terms(query: str) -> list[str]:
    return [token for token in re.findall(r"[a-zA-ZäöüÄÖÜß0-9]+", query or "") if len(token) >= 2][:8]


def _expanded_terms(query: str) -> set[str]:
    normalized = _ascii(query)
    result = {_ascii(token) for token in _terms(query)}
    for group in _ALIAS_GROUPS:
        if any(token in normalized for token in group):
            result.update(group)
    if "aufputz" in normalized:
        result.add("ap")
    if "unterputz" in normalized:
        result.add("up")
    return {token for token in result if len(token) >= 2}


def _rank(row, query: str, expanded: set[str]):
    query_n = _ascii(query).strip()
    code = _ascii(getattr(row, "code", ""))
    description = _ascii(getattr(row, "description", ""))
    score = 0
    if query_n and code == query_n:
        score += 1000
    elif query_n and query_n in code:
        score += 400
    if query_n and query_n in description:
        score += 300
    for term in expanded:
        if term in code:
            score += 80
        if term in description:
            score += 35
    # Prefer the concise base position over highly qualified variants when
    # relevance is otherwise equal.
    score -= min(len(description.split()), 40)
    price, mode = _price(row)
    if mode == "VK":
        score += 5
    return score, price or ZERO, getattr(row, "pk", 0) or 0


def search_bo_prices(org, query: str, *, limit: int = 30):
    """Search actual priced B&O rows, not KAYI's internal shortcut catalog.

    The result is always an existing imported PriceItem. Search accepts VA04
    codes and German service wording and expands a small set of safe trade
    synonyms so e.g. Duscharmatur can also surface Brausearmatur.
    """
    query = (query or "").strip()
    if len(query) < 2:
        return []
    source_ids = bo_source_ids(org)
    if not source_ids:
        return []
    expanded = _expanded_terms(query)
    condition = Q(code__icontains=query) | Q(description__icontains=query)
    for term in expanded:
        condition |= Q(code__icontains=term) | Q(description__icontains=term)
    rows = list(
        m.PriceItem.objects.filter(organization=org, source_id__in=source_ids, source__active=True)
        .filter(Q(sales_price__gt=0) | Q(purchase_price__gt=0))
        .filter(condition)
        .select_related("source")[:500]
    )
    rows.sort(key=lambda row: _rank(row, query, expanded), reverse=True)
    return rows[: max(1, min(int(limit or 30), 50))]


def serialize_bo_price(row) -> dict:
    price, mode = _price(row)
    return {
        "id": row.pk,
        "code": (row.code or "").strip(),
        "description": (row.description or "").strip(),
        "unit": (row.unit or "Stk.").strip(),
        "price": str(price or ZERO),
        "price_mode": mode,
        "tax": "19",
        "source": getattr(row.source, "name", "") or "B&O",
    }
