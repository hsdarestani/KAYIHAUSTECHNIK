from __future__ import annotations

from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from . import models as m
from .rebuild_views import _is_field_user, _org


ZERO = Decimal("0")


def _price_item_payload(row):
    sales = getattr(row, "sales_price", None)
    purchase = getattr(row, "purchase_price", None)
    price = sales if sales is not None and sales > ZERO else purchase
    return {
        "kind": "price_item",
        "id": row.pk,
        "code": (getattr(row, "code", "") or "").strip(),
        "name": (getattr(row, "description", "") or "").strip(),
        "description": (getattr(row, "description", "") or "").strip(),
        "unit": (getattr(row, "unit", "") or "Stk.").strip(),
        "purchase_price": str(price or ZERO),
        "sales_price": str(price or ZERO),
        "tax_rate": str(getattr(row, "tax_rate", None) or "19"),
        "source": getattr(getattr(row, "source", None), "name", "") or "Preisliste",
    }


def _catalog_payload(row):
    purchase = getattr(row, "purchase_price", None) or ZERO
    sales = getattr(row, "sales_price", None) or ZERO
    effective = sales if sales > ZERO else purchase
    return {
        "kind": "catalog",
        "id": row.pk,
        "code": (getattr(row, "code", "") or "").strip(),
        "name": (getattr(row, "name", "") or "").strip(),
        "description": (getattr(row, "description", "") or "").strip(),
        "unit": (getattr(row, "unit", "") or "Stk.").strip(),
        "purchase_price": str(purchase if purchase > ZERO else effective),
        "sales_price": str(effective),
        "tax_rate": str(getattr(row, "tax_rate", None) or "19"),
        "source": "Leistungskatalog",
    }


def _is_owner_source(source) -> bool:
    summary = getattr(source, "import_summary", None)
    if isinstance(summary, dict) and summary.get("kind") in {"owner_upload", "customer_upload", "price_library_upload"}:
        return True
    name = (getattr(source, "name", "") or "").casefold()
    filename = (getattr(source, "original_filename", "") or "").casefold()
    return any(token in name or token in filename for token in ("privat", "eigene", "kunde", "customer", "kayi_p", "kayi p"))


def _matches_reference(source) -> bool:
    name = f"{getattr(source, 'name', '')} {getattr(source, 'original_filename', '')}".casefold()
    return any(token in name for token in ("b&o", "b+o", "b und o", "bo ", "va04", "referenz"))


@login_required
@require_GET
def live_pricing_search(request):
    if _is_field_user(request):
        return JsonResponse({"ok": False, "error": "Keine Preisberechtigung."}, status=403)
    org = _org(request)
    family = (request.GET.get("catalog") or "catalog").strip().lower()
    query = (request.GET.get("q") or "").strip()
    limit = max(5, min(int(request.GET.get("limit") or 30), 60))

    if family == "catalog":
        qs = m.CatalogItem.objects.filter(organization=org, active=True)
        if query:
            qs = qs.filter(Q(code__icontains=query) | Q(name__icontains=query) | Q(description__icontains=query))
        rows = list(qs.order_by("name")[:limit])
        return JsonResponse({"ok": True, "catalog": family, "results": [_catalog_payload(row) for row in rows]})

    source_qs = m.PriceSource.objects.filter(organization=org, active=True).order_by("name")
    sources = list(source_qs)
    if family == "own":
        selected = [source for source in sources if _is_owner_source(source)]
        if not selected:
            selected = [source for source in sources if not _matches_reference(source)]
    elif family == "reference":
        selected = [source for source in sources if _matches_reference(source)]
        if not selected:
            selected = [source for source in sources if not _is_owner_source(source)]
    else:
        selected = sources

    source_ids = [source.pk for source in selected]
    qs = m.PriceItem.objects.filter(organization=org, source_id__in=source_ids, source__active=True).select_related("source")
    qs = qs.filter(Q(sales_price__gt=0) | Q(purchase_price__gt=0))
    if query:
        qs = qs.filter(Q(code__icontains=query) | Q(description__icontains=query))
    rows = list(qs.order_by("source__name", "description")[:limit])
    return JsonResponse({"ok": True, "catalog": family, "results": [_price_item_payload(row) for row in rows]})
