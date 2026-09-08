from __future__ import annotations

from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import models as m
from . import rebuild_views as base


TYPE_LABELS = {
    "all": "Alle Artikeltypen",
    "material": "Material",
    "labor": "Lohn / Leistung",
    "jumbo": "Jumbo",
    "other": "Sonstiges",
}


def _office_only(request):
    checker = getattr(base, "_is_field_user", None)
    return bool(checker(request)) if checker else False


def _model_fields(model):
    return {field.name: field for field in model._meta.get_fields()}


def _as_decimal(value, default=Decimal("0")):
    try:
        raw = str(value if value not in (None, "") else default).strip().replace(",", ".")
        return Decimal(raw)
    except (InvalidOperation, TypeError, ValueError):
        return default


def _canonical_type(raw):
    value = str(raw or "").strip().casefold().replace("_", "-")
    if any(token in value for token in ("material", "ware", "produkt")):
        return "material"
    if any(token in value for token in ("labor", "labour", "lohn", "service", "leistung", "arbeit")):
        return "labor"
    if "jumbo" in value or "mixed" in value or "misch" in value:
        return "jumbo"
    return "other"


def _item_type(item):
    for name in ("item_type", "article_type", "kind", "type", "category"):
        if hasattr(item, name):
            value = getattr(item, name, None)
            if value not in (None, ""):
                return _canonical_type(value)
    return "other"


def _assign_type(item, requested):
    requested = requested if requested in {"material", "labor", "jumbo", "other"} else "other"
    fields = _model_fields(type(item))
    candidates = {
        "material": ("material", "MATERIAL", "product", "ware"),
        "labor": ("labor", "LABOR", "service", "leistung", "lohn"),
        "jumbo": ("jumbo", "JUMBO", "mixed", "misch"),
        "other": ("other", "OTHER", "sonstiges"),
    }[requested]
    for name in ("item_type", "article_type", "kind", "type", "category"):
        field = fields.get(name)
        if field is None:
            continue
        choices = [choice[0] for choice in (getattr(field, "choices", None) or [])]
        if choices:
            normalized = {str(choice).casefold(): choice for choice in choices}
            for candidate in candidates:
                if str(candidate).casefold() in normalized:
                    setattr(item, name, normalized[str(candidate).casefold()])
                    return
            for choice in choices:
                if _canonical_type(choice) == requested:
                    setattr(item, name, choice)
                    return
            return
        setattr(item, name, candidates[0])
        return


def _changed_at(item):
    for name in ("updated_at", "modified_at", "changed_at", "created_at"):
        value = getattr(item, name, None)
        if value is not None:
            return value
    return None


def _changed_label(value):
    if value is None:
        return "—"
    try:
        now = timezone.now()
        if timezone.is_naive(value):
            value = timezone.make_aware(value, timezone.get_current_timezone())
        seconds = max(0, int((now - value).total_seconds()))
        if seconds < 60:
            return "gerade eben"
        minutes = seconds // 60
        if minutes < 60:
            return f"vor {minutes} Min."
        hours = minutes // 60
        if hours < 24:
            return f"vor {hours} Std."
        days = hours // 24
        if days == 1:
            return "vor einem Tag"
        if days < 14:
            return f"vor {days} Tagen"
        return value.strftime("%d.%m.%Y")
    except Exception:
        return "—"


def _row(item):
    purchase = _as_decimal(getattr(item, "purchase_price", None))
    sales = _as_decimal(getattr(item, "sales_price", None))
    if sales <= 0:
        sales = purchase
    markup = Decimal("0")
    if purchase > 0 and sales >= 0:
        markup = ((sales - purchase) / purchase * Decimal("100")).quantize(Decimal("0.01"))
    changed = _changed_at(item)
    name = (getattr(item, "name", "") or "").strip()
    description = (getattr(item, "description", "") or "").strip()
    return {
        "item": item,
        "code": (getattr(item, "code", "") or "").strip(),
        "name": name or description or "Artikel",
        "description": description if description and description != name else "",
        "unit": (getattr(item, "unit", "") or "Stk.").strip(),
        "purchase": purchase,
        "sales": sales,
        "markup": markup,
        "type": _item_type(item),
        "changed": changed,
        "changed_label": _changed_label(changed),
    }


def _next_code(org):
    existing = set(
        str(value or "").strip().casefold()
        for value in m.CatalogItem.objects.filter(organization=org).values_list("code", flat=True)
    )
    number = 1
    while True:
        code = f"ART-{number:05d}"
        if code.casefold() not in existing:
            return code
        number += 1


@login_required
def catalogue_list(request):
    if _office_only(request):
        return HttpResponseForbidden("Der Katalog ist nur für Büro-Rollen verfügbar.")
    org = base._org(request)
    query = (request.GET.get("q") or "").strip()
    type_filter = (request.GET.get("type") or "all").strip().lower()
    if type_filter not in TYPE_LABELS:
        type_filter = "all"
    sort = (request.GET.get("sort") or "changed_desc").strip().lower()
    if sort not in {"changed_desc", "changed_asc", "code_asc", "code_desc", "price_asc", "price_desc"}:
        sort = "changed_desc"
    try:
        amount = int(request.GET.get("amount") or 20)
    except (TypeError, ValueError):
        amount = 20
    if amount not in {20, 50, 100}:
        amount = 20
    try:
        offset = max(0, int(request.GET.get("offset") or 0))
    except (TypeError, ValueError):
        offset = 0

    qs = m.CatalogItem.objects.filter(organization=org)
    fields = _model_fields(m.CatalogItem)
    if "active" in fields:
        qs = qs.filter(active=True)
    if query:
        condition = Q(code__icontains=query) | Q(name__icontains=query) | Q(description__icontains=query)
        qs = qs.filter(condition)

    rows = [_row(item) for item in qs[:3000]]
    if type_filter != "all":
        rows = [row for row in rows if row["type"] == type_filter]

    if sort.startswith("code"):
        key = lambda row: (row["code"].casefold(), row["item"].pk)
    elif sort.startswith("price"):
        key = lambda row: (row["sales"], row["item"].pk)
    else:
        key = lambda row: (row["changed"] or timezone.now().replace(year=1970, month=1, day=1, hour=0, minute=0, second=0, microsecond=0), row["item"].pk)
    rows.sort(key=key, reverse=sort.endswith("_desc"))

    total_count = len(rows)
    if offset >= total_count and total_count:
        offset = max(0, ((total_count - 1) // amount) * amount)
    page_rows = rows[offset:offset + amount]
    prev_offset = max(0, offset - amount)
    next_offset = offset + amount if offset + amount < total_count else None
    params = {"q": query, "type": type_filter, "sort": sort, "amount": amount}
    query_tail = urlencode({key: value for key, value in params.items() if value not in ("", "all")})
    changed_params = dict(params)
    changed_params["sort"] = "changed_asc" if sort == "changed_desc" else "changed_desc"
    changed_query = urlencode({key: value for key, value in changed_params.items() if value not in ("", "all")})

    return render(request, "rebuild/catalogue.html", {
        "rows": page_rows,
        "q": query,
        "type_filter": type_filter,
        "type_labels": TYPE_LABELS,
        "sort": sort,
        "amount": amount,
        "offset": offset,
        "total_count": total_count,
        "first_item": offset + 1 if total_count else 0,
        "last_item": min(offset + amount, total_count),
        "prev_offset": prev_offset,
        "next_offset": next_offset,
        "query_tail": query_tail,
        "changed_query": changed_query,
    })


def _catalogue_form_context(item=None, values=None, errors=None):
    values = dict(values or {})
    if item is not None and not values:
        values = {
            "code": getattr(item, "code", "") or "",
            "name": getattr(item, "name", "") or "",
            "description": getattr(item, "description", "") or "",
            "unit": getattr(item, "unit", "") or "Stk.",
            "purchase_price": getattr(item, "purchase_price", "") or "",
            "sales_price": getattr(item, "sales_price", "") or "",
            "tax_rate": getattr(item, "tax_rate", "") or "19",
            "type": _item_type(item),
        }
    return {"item": item, "values": values, "errors": errors or [], "type_labels": TYPE_LABELS}


@login_required
def catalogue_edit(request, pk=None):
    if _office_only(request):
        return HttpResponseForbidden("Der Katalog ist nur für Büro-Rollen verfügbar.")
    org = base._org(request)
    item = None
    if pk is not None:
        try:
            item = m.CatalogItem.objects.get(pk=pk, organization=org)
        except m.CatalogItem.DoesNotExist as exc:
            raise Http404 from exc

    if request.method == "POST":
        values = {key: (request.POST.get(key) or "").strip() for key in ("code", "name", "description", "unit", "purchase_price", "sales_price", "tax_rate", "type")}
        errors = []
        code = values["code"] or _next_code(org)
        name = values["name"] or values["description"]
        if not name:
            errors.append("Bitte eine Bezeichnung eingeben.")
        duplicate = m.CatalogItem.objects.filter(organization=org, code__iexact=code)
        if item is not None:
            duplicate = duplicate.exclude(pk=item.pk)
        if duplicate.exists():
            errors.append("Diese Artikelnummer ist bereits vergeben.")
        purchase = _as_decimal(values["purchase_price"])
        sales = _as_decimal(values["sales_price"])
        tax = _as_decimal(values["tax_rate"], Decimal("19"))
        if purchase < 0 or sales < 0:
            errors.append("Preise dürfen nicht negativ sein.")
        if tax < 0 or tax > 100:
            errors.append("Der Steuersatz muss zwischen 0 und 100 liegen.")
        if errors:
            values["code"] = code
            return render(request, "rebuild/catalogue_edit.html", _catalogue_form_context(item, values, errors), status=400)

        if item is None:
            item = m.CatalogItem(organization=org)
        fields = _model_fields(m.CatalogItem)
        assignments = {
            "code": code,
            "name": name,
            "description": values["description"],
            "unit": values["unit"] or "Stk.",
            "purchase_price": purchase,
            "sales_price": sales,
            "tax_rate": tax,
        }
        for key, value in assignments.items():
            if key in fields:
                setattr(item, key, value)
        if "active" in fields and item.pk is None:
            item.active = True
        _assign_type(item, values["type"])
        item.save()
        messages.success(request, "Artikel gespeichert.")
        return redirect("next-catalogue")

    return render(request, "rebuild/catalogue_edit.html", _catalogue_form_context(item))


@login_required
@require_POST
def catalogue_delete(request, pk):
    if _office_only(request):
        return HttpResponseForbidden("Der Katalog ist nur für Büro-Rollen verfügbar.")
    org = base._org(request)
    try:
        item = m.CatalogItem.objects.get(pk=pk, organization=org)
    except m.CatalogItem.DoesNotExist as exc:
        raise Http404 from exc
    fields = _model_fields(m.CatalogItem)
    if "active" in fields:
        item.active = False
        item.save(update_fields=["active"])
    else:
        item.delete()
    messages.success(request, "Artikel wurde entfernt.")
    return redirect("next-catalogue")
