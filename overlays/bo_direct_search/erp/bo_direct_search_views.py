from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .rebuild_views import _org
from .services.bo_direct_search import bo_source_ids, search_bo_prices, serialize_bo_price


@login_required
@require_GET
def bo_price_search(request):
    org = _org(request)
    query = (request.GET.get("q") or "").strip()
    rows = search_bo_prices(org, query, limit=30)
    return JsonResponse({
        "ok": True,
        "query": query,
        "results": [serialize_bo_price(row) for row in rows],
        "bo_sources": len(bo_source_ids(org)),
    })
