from __future__ import annotations

import re
import unicodedata
from decimal import Decimal

from django.db.models import Q

from erp import models as m


ZERO = Decimal("0")
_ALIAS_GROUPS = (
    ("dusch", "braus"),
    ("waschtisch", "waschbecken"),
    ("toilette", "wc"),
    ("grundier", "haftgrund", "tiefgrund"),
    ("dispersionsfarbe", "anstrich", "streichen", "maler"),
    ("spachtel", "ausgleich", "nivellier"),
    ("abdecken", "schutz", "abkleben"),
    ("wandfliesen", "wandfliese", "fliesen wand"),
    ("bodenfliesen", "bodenfliese", "fliesen boden"),
    ("demontage", "abbrechen", "entfernen", "ausbau"),
    ("erneuern", "austausch", "austauschen", "ersetzen"),
)


def _norm(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).casefold()
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).replace("ß", "ss")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _source_ids(org) -> list[int]:
    return list(m.PriceSource.objects.filter(organization=org, active=True).values_list("pk", flat=True))


def _price(row):
    if getattr(row, "sales_price", None) is not None and row.sales_price > ZERO:
        return row.sales_price, "VK"
    if getattr(row, "purchase_price", None) is not None and row.purchase_price > ZERO:
        return row.purchase_price, "EK"
    return None, ""


def _expanded_terms(query: str) -> set[str]:
    normalized = _norm(query)
    terms = {token for token in normalized.split() if len(token) >= 2}
    for group in _ALIAS_GROUPS:
        if any(_norm(token) in normalized for token in group):
            terms.update(_norm(token) for token in group)
    return terms


def _rank(row, query: str, expanded: set[str]) -> tuple[int, int]:
    q = _norm(query)
    code = _norm(getattr(row, "code", ""))
    description = _norm(getattr(row, "description", ""))
    score = 0
    if q and code == q:
        score += 1200
    elif q and q in code:
        score += 500
    if q and q in description:
        score += 360
    for term in expanded:
        if term in code:
            score += 90
        if term in description:
            score += 45
    if _price(row)[1] == "VK":
        score += 8
    return score, -(getattr(row, "pk", 0) or 0)


def search_org_prices(org, query: str, *, limit: int = 30):
    """Search only active price lists belonging to the current organization."""
    query = str(query or "").strip()
    if len(query) < 2:
        return []
    source_ids = _source_ids(org)
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
        .select_related("source")[:700]
    )
    rows.sort(key=lambda row: _rank(row, query, expanded), reverse=True)
    return rows[: max(1, min(int(limit or 30), 60))]


def serialize_org_price(row) -> dict:
    price, mode = _price(row)
    return {
        "id": row.pk,
        "code": (getattr(row, "code", "") or "").strip(),
        "description": (getattr(row, "description", "") or "").strip(),
        "unit": (getattr(row, "unit", "") or "Stk.").strip(),
        "price": str(price or ZERO),
        "price_mode": mode,
        "tax": str(getattr(row, "tax_rate", None) or "19"),
        "source": getattr(getattr(row, "source", None), "name", "") or "Preislisten-Import",
    }
