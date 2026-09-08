from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, Q, QuerySet

from erp.models import Organization, PriceItem, PriceSource, Project


COMMERCIAL_SOURCE_KINDS = (
    PriceSource.Kind.INSURANCE,
    PriceSource.Kind.PARTNER,
    PriceSource.Kind.CUSTOMER,
    PriceSource.Kind.CATALOG,
)


def is_material_only_source(source: PriceSource) -> bool:
    """Return True for supplier purchasing lists such as JOKA/Raab Karcher.

    Supplier lists remain available in Material/Marketplace, but must never be
    offered as the commercial basis of an Angebot.
    """
    haystack = " ".join(
        filter(
            None,
            [
                source.name,
                source.original_filename,
                getattr(source.supplier, "name", "") if source.supplier_id else "",
                str((source.import_summary or {}).get("original_path", "")),
            ],
        )
    ).casefold()
    return source.kind == PriceSource.Kind.SUPPLIER or any(
        token in haystack for token in ("joka", "raab karcher", "raab_karcher")
    )


def commercial_price_sources(organization: Organization, *, include_empty: bool = False) -> QuerySet[PriceSource]:
    priced_filter = Q(items__active=True) & (
        Q(items__sales_price__gt=0) | Q(items__purchase_price__gt=0)
    )
    queryset = (
        PriceSource.objects.filter(
            organization=organization,
            active=True,
            kind__in=COMMERCIAL_SOURCE_KINDS,
        )
        .select_related("supplier")
        .annotate(priced_item_count=Count("items", filter=priced_filter, distinct=True))
        .order_by("kind", "name", "-imported_at")
    )
    if not include_empty:
        queryset = queryset.filter(priced_item_count__gt=0)
    return queryset


def price_source_matches_job_type(source: PriceSource, job_type: str) -> bool:
    if is_material_only_source(source):
        return False
    if job_type == Project.JobType.INSURANCE:
        return source.kind in {PriceSource.Kind.INSURANCE, PriceSource.Kind.PARTNER}
    return source.kind in {PriceSource.Kind.CUSTOMER, PriceSource.Kind.CATALOG, PriceSource.Kind.PARTNER}


def resolved_item_price(item: PriceItem) -> Decimal | None:
    """Return a positive commercial price or None.

    Imported partner files sometimes place the usable net price in the purchase
    column. We accept that as a fallback for commercial sources, while never
    exposing supplier-only lists in Angebot/Kalkulation.
    """
    for value in (item.sales_price, item.purchase_price):
        if value is not None and value > 0:
            return value
    return None


def is_sellable_item(item: PriceItem) -> bool:
    return bool(item.active and resolved_item_price(item) is not None)


def preferred_price_source(organization: Organization, job_type: str) -> PriceSource | None:
    sources = commercial_price_sources(organization)
    matching = [source for source in sources if price_source_matches_job_type(source, job_type)]
    if not matching:
        return None
    if job_type == Project.JobType.INSURANCE:
        for source in matching:
            label = f"{source.name} {source.original_filename}".casefold()
            if "b&o" in label or "pl1658" in label or "1658" in label or "va04" in label:
                return source
    return matching[0]


def quantity_for_price_item(item: PriceItem, measurement) -> Decimal:
    if not measurement:
        return Decimal("1")
    unit = (item.unit or "").lower().replace("²", "2")
    text = f"{item.category} {item.description}".lower()
    if unit in {"m2", "m²", "qm"}:
        if any(word in text for word in ("wand", "fliese", "putz", "tapete", "anstrich")):
            return measurement.wall_with_waste_m2 or measurement.wall_area_m2 or Decimal("1")
        return measurement.floor_with_waste_m2 or measurement.floor_area_m2 or Decimal("1")
    if unit in {"m", "lfm", "lm"}:
        return measurement.perimeter_m or Decimal("1")
    return Decimal("1")
