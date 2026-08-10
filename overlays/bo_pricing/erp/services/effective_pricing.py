from __future__ import annotations

import re
from decimal import Decimal

from erp import models as m


ZERO = Decimal("0")


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


def apply_effective_prices(org, catalog_items):
    """Attach effective price/source attributes to CatalogItem objects.

    Priority is deliberately explicit:
    1. A non-zero B&O PriceItem with the same code.
    2. The CatalogItem's own non-zero sales price.
    3. The best other active PriceItem with the same code.
    4. Zero only when no usable price exists anywhere.

    The database rows are not mutated; this is safe for quotes, invoices and
    field authorization previews and keeps the original source data auditable.
    """
    items = list(catalog_items)
    best = _best_by_code(org, [item.code for item in items])
    for item in items:
        row = best.get((item.code or "").strip())
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
        item.effective_price_mode = row_mode if row is not None else "catalog"
    return items


def catalog_with_effective_prices(org, *, limit=500):
    queryset = m.CatalogItem.objects.filter(organization=org, active=True).order_by("name")[:limit]
    return apply_effective_prices(org, queryset)


def effective_price_for_catalog_item(org, catalog_item):
    apply_effective_prices(org, [catalog_item])
    return catalog_item.effective_sales_price
