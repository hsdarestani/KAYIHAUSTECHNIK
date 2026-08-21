from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME CATALOGUE EXACT PARITY 2026-08-21"
VERSION = "20260821-catalogue-exact-1"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Catalogue parity target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def install_views() -> None:
    write("erp/tooltime_catalogue_views.py", r'''from __future__ import annotations

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
        key = lambda row: (row["changed"] or timezone.make_aware(timezone.datetime.min), row["item"].pk)
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
''')


def patch_urls() -> None:
    rel = "erp/rebuild_urls.py"
    text = read(rel)
    import_line = "from . import tooltime_catalogue_views as catalogue\n"
    if import_line not in text:
        anchor = "from . import tooltime_parity_views as tooltime_parity\n"
        if anchor not in text:
            anchor = "from . import rebuild_views as views\n"
        if anchor not in text:
            raise RuntimeError("Catalogue URL import anchor changed")
        text = text.replace(anchor, anchor + import_line, 1)

    routes = (
        '    path("catalogue/", catalogue.catalogue_list, name="next-catalogue"),\n',
        '    path("catalogue/new/", catalogue.catalogue_edit, name="next-catalogue-create"),\n',
        '    path("catalogue/<int:pk>/edit/", catalogue.catalogue_edit, name="next-catalogue-edit"),\n',
        '    path("catalogue/<int:pk>/delete/", catalogue.catalogue_delete, name="next-catalogue-delete"),\n',
    )
    if 'name="next-catalogue"' not in text:
        marker = "urlpatterns = [\n"
        if marker not in text:
            raise RuntimeError("Catalogue urlpatterns anchor changed")
        text = text.replace(marker, marker + "".join(routes), 1)
    write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def patch_navigation() -> None:
    rel = "templates/rebuild/base.html"
    text = read(rel)
    if "next-catalogue" in text:
        return
    link = '''      <a class="{% if 'catalogue' in request.resolver_match.url_name %}is-active{% endif %}" href="{% url 'next-catalogue' %}"><span class="nx-ico">▤</span>Katalog</a>\n'''
    lines = text.splitlines(True)
    insertion = None
    for preferred in ("next-payments", "next-invoices"):
        for index, line in enumerate(lines):
            if preferred in line and "href=" in line:
                insertion = index + 1
                break
        if insertion is not None:
            break
    if insertion is None:
        raise RuntimeError("Catalogue navigation anchor changed")
    lines.insert(insertion, link)
    write(rel, "".join(lines))


def install_templates() -> None:
    write("templates/rebuild/catalogue.html", r'''{% extends 'rebuild/base.html' %}{% load static %}
{% block title %}Katalog · A+Bau{% endblock %}
{% block content %}
<link rel="stylesheet" href="{% static 'css/tooltime-catalogue-exact.css' %}?v=20260821-catalogue-exact">
<script src="{% static 'js/tooltime-catalogue-exact.js' %}?v=20260821-catalogue-exact" defer></script>
<div class="ttc-page" data-tooltime-catalogue>
  <div class="ttc-topbar">
    <div class="ttc-heading"><h1>Katalog</h1><span class="ttc-help" title="Artikel und Leistungen verwalten">?</span></div>
    <div class="ttc-top-actions">
      <form class="ttc-search" method="get" role="search">
        <input type="hidden" name="type" value="{{ type_filter }}"><input type="hidden" name="sort" value="{{ sort }}"><input type="hidden" name="amount" value="{{ amount }}">
        <span aria-hidden="true">⌕</span><input type="search" name="q" value="{{ q }}" placeholder="Suchen" aria-label="Katalog durchsuchen"><button type="submit" class="sr-only">Suchen</button>
      </form>
      <a class="ttc-new" href="{% url 'next-catalogue-create' %}"><span aria-hidden="true">＋</span> Artikel hinzufügen</a>
    </div>
  </div>
  <form class="ttc-filters" method="get" data-catalogue-filters>
    <input type="hidden" name="q" value="{{ q }}"><input type="hidden" name="sort" value="{{ sort }}"><input type="hidden" name="amount" value="{{ amount }}">
    <label class="ttc-select"><span class="sr-only">Artikeltyp</span><select name="type" aria-label="Artikeltyp">
      <option value="all" {% if type_filter == 'all' %}selected{% endif %}>Alle Artikeltypen</option>
      <option value="material" {% if type_filter == 'material' %}selected{% endif %}>Material</option>
      <option value="labor" {% if type_filter == 'labor' %}selected{% endif %}>Lohn / Leistung</option>
      <option value="jumbo" {% if type_filter == 'jumbo' %}selected{% endif %}>Jumbo</option>
      <option value="other" {% if type_filter == 'other' %}selected{% endif %}>Sonstiges</option>
    </select></label>
    <label class="ttc-mobile-sort"><span>Sortieren</span><select name="sort" aria-label="Katalog sortieren"><option value="changed_desc" {% if sort == 'changed_desc' %}selected{% endif %}>Letzte Änderung ↓</option><option value="changed_asc" {% if sort == 'changed_asc' %}selected{% endif %}>Letzte Änderung ↑</option><option value="code_asc" {% if sort == 'code_asc' %}selected{% endif %}>Artikelnummer ↑</option><option value="code_desc" {% if sort == 'code_desc' %}selected{% endif %}>Artikelnummer ↓</option><option value="price_asc" {% if sort == 'price_asc' %}selected{% endif %}>Stückpreis ↑</option><option value="price_desc" {% if sort == 'price_desc' %}selected{% endif %}>Stückpreis ↓</option></select></label>
  </form>
  <div class="ttc-table-wrap"><table class="ttc-table" data-catalogue-table>
    <thead><tr><th>Artikelnummer</th><th>Beschreibung</th><th>Einheit</th><th class="ttc-money">Einkaufspreis</th><th class="ttc-money">Aufschlag</th><th class="ttc-money">Stückpreis</th><th><a class="ttc-sort-link" href="?{{ changed_query }}{% if changed_query %}&{% endif %}offset=0">Letzte Änderung <span aria-hidden="true">{% if sort == 'changed_asc' %}↑{% else %}↓{% endif %}</span></a></th><th aria-label="Aktionen"></th></tr></thead>
    <tbody>{% for row in rows %}<tr data-catalogue-row>
      <td data-label="Artikelnummer"><a class="ttc-code" href="{% url 'next-catalogue-edit' row.item.pk %}">{% if row.code %}{{ row.code }}{% else %}—{% endif %}</a></td>
      <td data-label="Beschreibung"><a class="ttc-title" href="{% url 'next-catalogue-edit' row.item.pk %}">{{ row.name }}</a>{% if row.description %}<small>{{ row.description }}</small>{% endif %}</td>
      <td data-label="Einheit">{{ row.unit }}</td><td class="ttc-money" data-label="Einkaufspreis">{{ row.purchase|floatformat:2 }} €</td><td class="ttc-money" data-label="Aufschlag">{{ row.markup|floatformat:2 }}%</td><td class="ttc-money" data-label="Stückpreis"><strong>{{ row.sales|floatformat:2 }} €</strong></td><td data-label="Letzte Änderung"><span class="ttc-changed">{{ row.changed_label }}</span></td>
      <td class="ttc-actions"><details class="ttc-row-menu"><summary aria-label="Artikelaktionen">•••</summary><div><a href="{% url 'next-catalogue-edit' row.item.pk %}">Artikel bearbeiten</a><form method="post" action="{% url 'next-catalogue-delete' row.item.pk %}" data-catalogue-delete>{% csrf_token %}<button type="submit">Artikel entfernen</button></form></div></details></td>
    </tr>{% empty %}<tr><td colspan="8"><div class="ttc-empty"><strong>Keine Artikel gefunden.</strong><span>Filter anpassen oder einen neuen Artikel hinzufügen.</span></div></td></tr>{% endfor %}</tbody>
  </table></div>
  <div class="ttc-pagination"><div><span>{% if total_count %}{{ first_item }}–{{ last_item }} von {{ total_count }}{% else %}0 Artikel{% endif %}</span><label>Zeilen <select data-catalogue-page-size aria-label="Zeilen pro Seite"><option value="20" {% if amount == 20 %}selected{% endif %}>20</option><option value="50" {% if amount == 50 %}selected{% endif %}>50</option><option value="100" {% if amount == 100 %}selected{% endif %}>100</option></select></label></div><div class="ttc-page-buttons">{% if offset > 0 %}<a href="?{{ query_tail }}{% if query_tail %}&{% endif %}offset={{ prev_offset }}" aria-label="Vorherige Seite">‹</a>{% else %}<span aria-disabled="true">‹</span>{% endif %}{% if next_offset != None %}<a href="?{{ query_tail }}{% if query_tail %}&{% endif %}offset={{ next_offset }}" aria-label="Nächste Seite">›</a>{% else %}<span aria-disabled="true">›</span>{% endif %}</div></div>
</div>
{% endblock %}''')

    write("templates/rebuild/catalogue_edit.html", r'''{% extends 'rebuild/base.html' %}{% load static %}
{% block title %}{% if item %}Artikel bearbeiten{% else %}Artikel hinzufügen{% endif %} · A+Bau{% endblock %}
{% block content %}
<link rel="stylesheet" href="{% static 'css/tooltime-catalogue-exact.css' %}?v=20260821-catalogue-exact">
<div class="ttc-editor" data-tooltime-catalogue-editor>
  <div class="ttc-editor-head"><div><a href="{% url 'next-catalogue' %}">← Katalog</a><h1>{% if item %}Artikel bearbeiten{% else %}Artikel hinzufügen{% endif %}</h1><p>Artikel- und Leistungsdaten zentral für Angebote, Rechnungen und Kalkulation pflegen.</p></div></div>
  {% if errors %}<div class="ttc-errors">{% for error in errors %}<div>{{ error }}</div>{% endfor %}</div>{% endif %}
  <form method="post" class="ttc-editor-form">{% csrf_token %}
    <div class="ttc-form-grid"><label><span>Artikelnummer</span><input name="code" value="{{ values.code }}" placeholder="z. B. ART-00001"></label><label><span>Artikeltyp</span><select name="type"><option value="material" {% if values.type == 'material' %}selected{% endif %}>Material</option><option value="labor" {% if values.type == 'labor' %}selected{% endif %}>Lohn / Leistung</option><option value="jumbo" {% if values.type == 'jumbo' %}selected{% endif %}>Jumbo</option><option value="other" {% if values.type == 'other' or not values.type %}selected{% endif %}>Sonstiges</option></select></label><label class="ttc-wide"><span>Bezeichnung</span><input name="name" value="{{ values.name }}" required></label><label class="ttc-wide"><span>Beschreibung</span><textarea name="description" rows="3">{{ values.description }}</textarea></label><label><span>Einheit</span><input name="unit" value="{{ values.unit|default:'Stk.' }}"></label><label><span>Steuersatz</span><div class="ttc-input-suffix"><input type="number" step="0.01" min="0" max="100" name="tax_rate" value="{{ values.tax_rate|default:'19' }}"><span>%</span></div></label><label><span>Einkaufspreis</span><div class="ttc-input-suffix"><input type="number" step="0.01" min="0" name="purchase_price" value="{{ values.purchase_price }}"><span>€</span></div></label><label><span>Stückpreis</span><div class="ttc-input-suffix"><input type="number" step="0.01" min="0" name="sales_price" value="{{ values.sales_price }}"><span>€</span></div></label></div>
    <div class="ttc-editor-actions"><a href="{% url 'next-catalogue' %}">Abbrechen</a><button type="submit">Speichern</button></div>
  </form>
</div>
{% endblock %}''')


def install_assets() -> None:
    write("static/css/tooltime-catalogue-exact.css", r'''.ttc-page{max-width:100%;margin:0 auto;color:#1f2c3a}.ttc-topbar{display:flex;align-items:center;justify-content:space-between;gap:24px;margin-bottom:21px}.ttc-heading{display:flex;align-items:center;gap:10px}.ttc-heading h1{margin:0;font-size:27px;letter-spacing:-.035em;font-weight:760}.ttc-help{display:inline-flex;width:19px;height:19px;border:2px solid #1682e8;border-radius:50%;align-items:center;justify-content:center;color:#1682e8;font-size:11px;font-weight:900}.ttc-top-actions{display:flex;align-items:center;gap:14px}.ttc-search{height:42px;min-width:270px;border:1px solid #d4dce5;border-radius:9px;background:#fff;display:flex;align-items:center;gap:9px;padding:0 12px}.ttc-search span{font-size:21px;color:#758497;transform:rotate(-18deg)}.ttc-search input{width:100%;border:0;outline:0;background:transparent;font:inherit}.ttc-new{height:42px;display:inline-flex;align-items:center;justify-content:center;gap:7px;padding:0 15px;border-radius:9px;background:#147de0;color:#fff;text-decoration:none;font-weight:750}.ttc-filters{display:flex;align-items:center;gap:10px;margin-bottom:23px}.ttc-select select,.ttc-mobile-sort select{appearance:none;border:1px solid #d3dbe4;border-radius:8px;background:#fff;padding:9px 34px 9px 12px;min-height:39px;color:#2d3c4e;font:inherit;font-size:13px;font-weight:600}.ttc-mobile-sort{display:none}.ttc-table-wrap{background:#fff;border-top:1px solid #e5e9ee;overflow-x:auto}.ttc-table{width:100%;border-collapse:collapse;font-size:13px}.ttc-table th{padding:13px;text-align:left;color:#7f8b99;font-size:11px;font-weight:650;white-space:nowrap;border-bottom:1px solid #dfe5eb}.ttc-table td{padding:18px 13px;border-bottom:1px solid #e4e8ed;color:#57677a;vertical-align:middle}.ttc-table tbody tr:hover{background:#fafbfd}.ttc-code,.ttc-title{color:#34465a;text-decoration:none;font-weight:700}.ttc-title{display:block;max-width:590px}.ttc-title+small{display:block;margin-top:4px;color:#6f7f91;font-size:10.5px;max-width:640px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ttc-money{text-align:right!important;font-variant-numeric:tabular-nums;white-space:nowrap}.ttc-changed{white-space:nowrap;color:#637387}.ttc-sort-link{color:inherit;text-decoration:none}.ttc-actions{width:44px}.ttc-row-menu{position:relative}.ttc-row-menu>summary{list-style:none;cursor:pointer;font-weight:900;letter-spacing:1px;color:#334b64;padding:7px 9px;border-radius:7px}.ttc-row-menu>summary::-webkit-details-marker{display:none}.ttc-row-menu>div{position:absolute;z-index:40;right:0;top:34px;min-width:180px;padding:6px;border:1px solid #dfe5ec;border-radius:9px;background:#fff;box-shadow:0 12px 30px rgba(23,39,57,.15)}.ttc-row-menu a,.ttc-row-menu button{display:block;width:100%;box-sizing:border-box;padding:9px 10px;border:0;border-radius:6px;background:transparent;text-align:left;text-decoration:none;color:#34475b;font:inherit;white-space:nowrap;cursor:pointer}.ttc-row-menu a:hover,.ttc-row-menu button:hover{background:#f2f5f8}.ttc-row-menu form{margin:0}.ttc-empty{min-height:180px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:5px;color:#8a96a4}.ttc-pagination{display:flex;align-items:center;justify-content:space-between;padding:14px 4px;color:#7b8794;font-size:12px}.ttc-pagination>div{display:flex;align-items:center;gap:14px}.ttc-page-buttons{gap:6px!important}.ttc-page-buttons a,.ttc-page-buttons span{width:30px;height:30px;border:1px solid #d9e0e7;border-radius:7px;display:flex;align-items:center;justify-content:center;text-decoration:none;color:#34495e;background:#fff;font-size:19px}.ttc-editor{max-width:880px;margin:0 auto}.ttc-editor-head a{color:#54708d;text-decoration:none;font-size:13px}.ttc-editor-head h1{margin:12px 0 5px;font-size:28px}.ttc-editor-head p{margin:0 0 22px;color:#718092}.ttc-editor-form{background:#fff;border:1px solid #e0e5eb;border-radius:13px;padding:22px}.ttc-form-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.ttc-form-grid label{display:grid;gap:7px}.ttc-form-grid label>span{font-size:12px;font-weight:750;color:#536377}.ttc-form-grid input,.ttc-form-grid select,.ttc-form-grid textarea{width:100%;box-sizing:border-box;border:1px solid #d6dee7;border-radius:8px;padding:10px 11px;background:#fff;color:#243449;font:inherit}.ttc-wide{grid-column:1/-1}.ttc-input-suffix{display:flex;align-items:center;border:1px solid #d6dee7;border-radius:8px;overflow:hidden}.ttc-input-suffix input{border:0;border-radius:0}.ttc-input-suffix span{padding:0 11px;color:#7a8795}.ttc-editor-actions{display:flex;justify-content:flex-end;align-items:center;gap:10px;margin-top:22px}.ttc-editor-actions a{padding:10px 14px;color:#4f6479;text-decoration:none}.ttc-editor-actions button{border:0;border-radius:8px;background:#147de0;color:#fff;padding:10px 18px;font-weight:750;cursor:pointer}.ttc-errors{margin:0 0 14px;padding:12px 14px;border-radius:9px;background:#fff0f0;color:#a83d3d;font-size:13px}.sr-only{position:absolute!important;width:1px!important;height:1px!important;padding:0!important;margin:-1px!important;overflow:hidden!important;clip:rect(0,0,0,0)!important;white-space:nowrap!important;border:0!important}@media(max-width:900px){.ttc-mobile-sort{display:block}.ttc-filters{flex-wrap:wrap}.ttc-table th:nth-child(7),.ttc-table td:nth-child(7){display:none}}@media(max-width:720px){.ttc-topbar{display:grid}.ttc-top-actions{width:100%}.ttc-search{flex:1;min-width:0}.ttc-table-wrap{border:0;overflow:visible}.ttc-table,.ttc-table tbody{display:block}.ttc-table thead{display:none}.ttc-table tr[data-catalogue-row]{display:block;padding:14px;margin-bottom:10px;border:1px solid #e0e5ea;border-radius:12px}.ttc-table tr[data-catalogue-row] td{display:flex!important;align-items:center;justify-content:space-between;gap:12px;padding:5px 0;border:0;text-align:right!important}.ttc-table tr[data-catalogue-row] td:before{content:attr(data-label);font-size:10px;text-transform:uppercase;color:#98a3af;font-weight:750}.ttc-form-grid{grid-template-columns:1fr}.ttc-wide{grid-column:auto}}@media(max-width:480px){.ttc-top-actions{display:grid}.ttc-new{width:100%;box-sizing:border-box}.ttc-filters{display:grid}.ttc-select select,.ttc-mobile-sort select{width:100%}}''')
    write("static/js/tooltime-catalogue-exact.js", r'''(()=>{const root=document.querySelector('[data-tooltime-catalogue]');if(!root)return;const filters=root.querySelector('[data-catalogue-filters]');filters?.querySelectorAll('select').forEach(s=>s.addEventListener('change',()=>filters.requestSubmit()));root.querySelector('[data-catalogue-page-size]')?.addEventListener('change',e=>{const u=new URL(location.href);u.searchParams.set('amount',e.target.value);u.searchParams.set('offset','0');location.assign(u.toString())});root.querySelectorAll('[data-catalogue-delete]').forEach(f=>f.addEventListener('submit',e=>{if(!confirm('Artikel wirklich entfernen?'))e.preventDefault()}));document.addEventListener('click',e=>root.querySelectorAll('.ttc-row-menu[open]').forEach(m=>{if(!m.contains(e.target))m.removeAttribute('open')}));document.addEventListener('keydown',e=>{if(e.key==='Escape')root.querySelectorAll('details[open]').forEach(n=>n.removeAttribute('open'))})})();''')


def patch_browser_smoke() -> None:
    rel = "scripts/production_browser_smoke.py"
    text = read(rel)
    marker = "            # A+BAU TOOLTIME CATALOGUE EXACT PARITY BROWSER SMOKE\n"
    if marker in text:
        return
    office_start = text.find("def run_office_surface(")
    field_start = text.find("\ndef run_field_surface(", office_start)
    close = "            context.close()\n"
    if office_start < 0 or field_start < 0:
        raise RuntimeError("Catalogue browser smoke could not find office/field surfaces")
    office_close = text.rfind(close, office_start, field_start)
    if office_close < 0:
        raise RuntimeError("Catalogue browser smoke could not find office context close")
    block = r'''            # A+BAU TOOLTIME CATALOGUE EXACT PARITY BROWSER SMOKE
            response = page.goto(base_url.rstrip("/") + "/catalogue/", wait_until="domcontentloaded", timeout=30_000)
            if response is None or response.status != 200:
                fail(f"ToolTime catalogue parity expected 200, got {response.status if response else 'no response'}")
            if page.locator('[data-tooltime-catalogue]').count() != 1:
                fail("ToolTime catalogue shell is missing")
            if page.locator('input[aria-label="Katalog durchsuchen"]').count() != 1:
                fail("ToolTime catalogue search is missing")
            if page.locator('[data-catalogue-filters] select[name="type"]').count() != 1:
                fail("ToolTime catalogue article type filter is missing")
            headers = " ".join(page.locator('[data-catalogue-table] thead th').all_inner_texts())
            for expected_header in ("Artikelnummer", "Beschreibung", "Einheit", "Einkaufspreis", "Aufschlag", "Stückpreis", "Letzte Änderung"):
                if expected_header not in headers:
                    fail(f"ToolTime catalogue table header missing: {expected_header}")
'''
    text = text[:office_close] + block + text[office_close:]
    write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def install_contract_tests() -> None:
    write("tests/test_tooltime_catalogue_exact_parity.py", r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]

class ToolTimeCatalogueExactParityContractTests(SimpleTestCase):
    def test_catalogue_route_and_navigation_are_real(self):
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        for required in ("next-catalogue", "next-catalogue-create", "next-catalogue-edit", "next-catalogue-delete"):
            self.assertIn(required, urls)
        self.assertIn("next-catalogue", base)
        self.assertIn("Katalog", base)

    def test_catalogue_matches_tooltime_index_controls(self):
        template = (ROOT / "templates/rebuild/catalogue.html").read_text(encoding="utf-8")
        for required in ("data-tooltime-catalogue", "Alle Artikeltypen", "Katalog durchsuchen", "Artikel hinzufügen", "Artikelnummer", "Beschreibung", "Einheit", "Einkaufspreis", "Aufschlag", "Stückpreis", "Letzte Änderung", "ttc-row-menu"):
            self.assertIn(required, template)

    def test_catalogue_is_backed_by_existing_catalog_items(self):
        module = (ROOT / "erp/tooltime_catalogue_views.py").read_text(encoding="utf-8")
        self.assertIn("m.CatalogItem.objects.filter(organization=org)", module)
        self.assertIn("item.save()", module)
        self.assertIn("catalogue_delete", module)
        self.assertNotIn("hard-coded article", module)

    def test_browser_smoke_covers_catalogue(self):
        smoke = (ROOT / "scripts/production_browser_smoke.py").read_text(encoding="utf-8")
        self.assertIn("A+BAU TOOLTIME CATALOGUE EXACT PARITY BROWSER SMOKE", smoke)
        self.assertIn("/catalogue/", smoke)
''')


def final_guard() -> None:
    urls = read("erp/rebuild_urls.py")
    base = read("templates/rebuild/base.html")
    template = read("templates/rebuild/catalogue.html")
    module = read("erp/tooltime_catalogue_views.py")
    for required in ("next-catalogue", "next-catalogue-create", "next-catalogue-edit", "next-catalogue-delete"):
        if required not in urls:
            raise RuntimeError(f"Catalogue route missing: {required}")
    if "next-catalogue" not in base:
        raise RuntimeError("Catalogue navigation is missing")
    for required in ("data-tooltime-catalogue", "Artikelnummer", "Einkaufspreis", "Aufschlag", "Stückpreis", "Letzte Änderung"):
        if required not in template:
            raise RuntimeError(f"Catalogue template contract missing: {required}")
    compile(module, str(ROOT / "erp/tooltime_catalogue_views.py"), "exec")


def main() -> None:
    install_views()
    patch_urls()
    patch_navigation()
    install_templates()
    install_assets()
    patch_browser_smoke()
    install_contract_tests()
    final_guard()
    print(f"{MARKER}: standalone ToolTime-style catalogue, real CatalogItem CRUD, filters/search/sorting/pagination and navigation installed.")


if __name__ == "__main__":
    main()
