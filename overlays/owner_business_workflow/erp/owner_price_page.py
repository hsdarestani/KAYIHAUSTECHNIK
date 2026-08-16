from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpResponseForbidden
from django.shortcuts import render

from . import models as m
from .owner_business_views import _can_manage_price_lists
from .rebuild_views import _org


@login_required
def price_list_page(request):
    if not _can_manage_price_lists(request):
        return HttpResponseForbidden("Keine Berechtigung für Preislisten.")
    org = _org(request)
    sources = (
        m.PriceSource.objects.filter(organization=org)
        .annotate(position_count=Count("priceitem"))
        .order_by("-active", "-pk")
    )
    # Some historical schemas use a custom related_name. Fall back without the
    # annotation instead of breaking the owner settings page.
    try:
        sources = list(sources)
    except Exception:
        sources = list(m.PriceSource.objects.filter(organization=org).order_by("-active", "-pk"))
        for source in sources:
            source.position_count = m.PriceItem.objects.filter(source=source, organization=org).count()
    return render(request, "rebuild/owner_price_lists.html", {"organization": org, "price_sources": sources})
