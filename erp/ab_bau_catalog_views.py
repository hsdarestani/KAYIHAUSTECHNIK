from __future__ import annotations

from decimal import Decimal

from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required

from . import models as m
from .rebuild_views import _is_field_user, _org

ZERO = Decimal("0")


def _price(item):
    if item.sales_price is not None and item.sales_price > ZERO:
        return item.sales_price
    if item.purchase_price is not None and item.purchase_price > ZERO:
        return item.purchase_price
    return ZERO


@login_required
@require_GET
def catalog_quick_search(request):
    if _is_field_user(request):
        return JsonResponse({"ok": False, "error": "Keine Preisberechtigung."}, status=403)
    org = _org(request)
    query = (request.GET.get("q") or "").strip()
    if len(query) < 2:
        return JsonResponse({"ok": True, "query": query, "results": []})
    rows = list(
        m.CatalogItem.objects.filter(organization=org, active=True)
        .filter(Q(name__icontains=query) | Q(code__icontains=query) | Q(description__icontains=query))
        .filter(Q(sales_price__gt=0) | Q(purchase_price__gt=0))
        .only("id", "code", "name", "description", "unit", "kind", "purchase_price", "sales_price")
        .order_by("name")[:24]
    )
    return JsonResponse({
        "ok": True,
        "query": query,
        "results": [
            {
                "id": item.pk,
                "code": item.code or "",
                "name": item.name or "",
                "description": item.description or "",
                "unit": item.unit or "Stk.",
                "kind": item.kind or "material",
                "purchase": str(item.purchase_price or ZERO),
                "sales": str(_price(item)),
            }
            for item in rows
        ],
    })
