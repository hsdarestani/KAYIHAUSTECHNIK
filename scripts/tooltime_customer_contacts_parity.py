from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME CUSTOMER CONTACTS PARITY 2026-08-21"
ASSET_MARKER = "A+Bau ToolTime customer contacts parity 20260821"
MIGRATION_NAME = "0011_tooltime_customer_contacts"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Customer parity target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_customer_model() -> None:
    path = "erp/models.py"
    text = read(path)
    if all(f"{name} = models.CharField" in text for name in ("debtor_number", "routing_id", "supplier_id")):
        return

    match = re.search(r"class Customer\([^\n]*\):\n(?P<body>.*?)(?=\nclass [A-Z])", text, re.S)
    if not match:
        raise RuntimeError("Customer model class could not be located")
    block = match.group(0)
    vat = re.search(r"(?m)^(?P<indent>\s+)vat_id\s*=\s*models\.CharField\([^\n]+\)\s*$", block)
    if not vat:
        raise RuntimeError("Customer VAT field anchor changed")
    indent = vat.group("indent")
    insert = (
        vat.group(0)
        + f"\n{indent}debtor_number = models.CharField(max_length=80, blank=True)"
        + f"\n{indent}routing_id = models.CharField(max_length=80, blank=True)"
        + f"\n{indent}supplier_id = models.CharField(max_length=80, blank=True)"
    )
    block = block.replace(vat.group(0), insert, 1)
    text = text[: match.start()] + block + text[match.end() :]
    write(path, text)


def install_migration() -> None:
    path = ROOT / "erp" / "migrations" / f"{MIGRATION_NAME}.py"
    content = '''from django.db import migrations, models\n\n\nclass Migration(migrations.Migration):\n    dependencies = [("erp", "0010_ab_bau_commercial")]\n\n    operations = [\n        migrations.AddField(\n            model_name="customer",\n            name="debtor_number",\n            field=models.CharField(blank=True, max_length=80),\n        ),\n        migrations.AddField(\n            model_name="customer",\n            name="routing_id",\n            field=models.CharField(blank=True, max_length=80),\n        ),\n        migrations.AddField(\n            model_name="customer",\n            name="supplier_id",\n            field=models.CharField(blank=True, max_length=80),\n        ),\n    ]\n'''
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        for needle in ("debtor_number", "routing_id", "supplier_id", "0010_ab_bau_commercial"):
            if needle not in existing:
                raise RuntimeError(f"Existing {MIGRATION_NAME} is incompatible: {needle} missing")
        return
    path.write_text(content, encoding="utf-8")


def ensure_db_model_imports(text: str) -> str:
    match = re.search(r"^from django\.db\.models import (?P<names>[^\n]+)$", text, re.M)
    if not match:
        raise RuntimeError("django.db.models import anchor changed")
    names = [part.strip() for part in match.group("names").split(",")]
    for name in ("Count", "Max"):
        if name not in names:
            names.append(name)
    replacement = "from django.db.models import " + ", ".join(sorted(set(names)))
    return text[: match.start()] + replacement + text[match.end() :]


CUSTOMER_FORM = '''class CustomerForm(StyledModelForm):
    customer_number = forms.CharField(label="Kundennummer", required=False, max_length=30)

    class Meta:
        model = m.Customer
        fields = [
            "type", "company", "salutation", "first_name", "last_name", "email", "phone", "mobile",
            "street", "postal_code", "city", "country", "vat_id", "debtor_number", "routing_id", "supplier_id", "notes",
        ]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, organization=None, modal=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        labels = {
            "type": "Kundentyp",
            "company": "Firmenname",
            "salutation": "Anrede",
            "first_name": "Vorname",
            "last_name": "Nachname",
            "email": "E-Mail",
            "phone": "Telefon",
            "mobile": "Mobil",
            "street": "Straße und Hausnummer",
            "postal_code": "PLZ",
            "city": "Ort",
            "country": "Land",
            "vat_id": "USt-IdNr.",
            "debtor_number": "Debitorennummer",
            "routing_id": "Routing-ID",
            "supplier_id": "Lieferanten-ID",
            "notes": "Beschreibung",
        }
        for name, label in labels.items():
            if name in self.fields:
                self.fields[name].label = label
        self.fields["customer_number"].widget.attrs.setdefault("placeholder", "Optional")
        if getattr(self.instance, "pk", None):
            self.fields["customer_number"].initial = self.instance.number
        if modal:
            self.fields["type"].choices = [("business", "Firmenkunde"), ("private", "Privatkunde")]
            self.fields["type"].widget = forms.RadioSelect(choices=self.fields["type"].choices)
        for name in ("debtor_number", "routing_id", "supplier_id", "vat_id"):
            self.fields[name].required = False
            self.fields[name].widget.attrs.setdefault("placeholder", "Optional")

    def clean(self):
        cleaned = super().clean()
        customer_type = cleaned.get("type")
        if customer_type == "business" and not str(cleaned.get("company") or "").strip():
            self.add_error("company", "Bitte den Firmennamen angeben.")
        if customer_type == "private" and not (str(cleaned.get("first_name") or "").strip() or str(cleaned.get("last_name") or "").strip()):
            self.add_error("last_name", "Bitte mindestens einen Namen angeben.")
        return cleaned
'''


CUSTOMER_VIEWS = '''@login_required
def customer_list(request):
    org = _org(request)
    return render(request, "rebuild/customers.html", _customer_list_context(request, org))


def _customer_list_context(request, org, create_form=None, create_location_form=None, modal_open=False):
    keyword = (request.GET.get("keyword") or request.GET.get("q") or "").strip()
    sort_type = (request.GET.get("sortType") or "NAME").upper()
    if sort_type not in {"NAME", "LAST_CHANGE", "PROJECTS"}:
        sort_type = "NAME"
    sort_order = (request.GET.get("sortOrder") or "ASCENDING").upper()
    if sort_order not in {"ASCENDING", "DESCENDING"}:
        sort_order = "ASCENDING"
    try:
        offset = max(0, int(request.GET.get("offset") or 0))
    except (TypeError, ValueError):
        offset = 0

    customers_qs = m.Customer.objects.filter(organization=org, active=True).annotate(projects_count=Count("projects", distinct=True))
    if keyword:
        customers_qs = customers_qs.filter(
            Q(company__icontains=keyword)
            | Q(first_name__icontains=keyword)
            | Q(last_name__icontains=keyword)
            | Q(email__icontains=keyword)
            | Q(phone__icontains=keyword)
            | Q(mobile__icontains=keyword)
            | Q(number__icontains=keyword)
            | Q(debtor_number__icontains=keyword)
            | Q(routing_id__icontains=keyword)
            | Q(supplier_id__icontains=keyword)
            | Q(street__icontains=keyword)
            | Q(city__icontains=keyword)
        )

    descending = sort_order == "DESCENDING"
    prefix = "-" if descending else ""
    if sort_type == "LAST_CHANGE":
        ordering = [f"{prefix}updated_at", f"{prefix}pk"]
    elif sort_type == "PROJECTS":
        ordering = [f"{prefix}projects_count", "company", "last_name", "first_name", "pk"]
    else:
        ordering = [f"{prefix}company", f"{prefix}last_name", f"{prefix}first_name", f"{prefix}pk"]

    total_count = customers_qs.count()
    page_size = 50
    if total_count:
        max_offset = ((total_count - 1) // page_size) * page_size
        offset = min(offset, max_offset)
    else:
        offset = 0
    customers = list(customers_qs.order_by(*ordering)[offset : offset + page_size])

    if create_form is None:
        create_form = CustomerForm(
            organization=org,
            modal=True,
            initial={"type": "business", "customer_number": _unique_number(m.Customer, org, "K")},
        )
    if create_location_form is None:
        create_location_form = ObjectLocationForm(prefix="site")

    return {
        "customers": customers,
        "keyword": keyword,
        "query": keyword,
        "sort_type": sort_type,
        "sort_order": sort_order,
        "offset": offset,
        "page_size": page_size,
        "total_count": total_count,
        "prev_offset": max(0, offset - page_size),
        "next_offset": offset + page_size,
        "has_prev": offset > 0,
        "has_next": offset + page_size < total_count,
        "name_sort_next": "DESCENDING" if sort_type == "NAME" and sort_order == "ASCENDING" else "ASCENDING",
        "last_change_sort_next": "DESCENDING" if sort_type == "LAST_CHANGE" and sort_order == "ASCENDING" else "ASCENDING",
        "projects_sort_next": "DESCENDING" if sort_type == "PROJECTS" and sort_order == "ASCENDING" else "ASCENDING",
        "create_form": create_form,
        "create_location_form": create_location_form,
        "customer_modal_open": modal_open,
    }


@login_required
@require_http_methods(["GET", "POST"])
def customer_create(request):
    org = _org(request)
    modal = request.GET.get("modal") == "1" or request.POST.get("modal") == "1"
    suggested_number = _unique_number(m.Customer, org, "K")
    form = CustomerForm(
        request.POST or None,
        organization=org,
        modal=modal,
        initial={"type": "business", "customer_number": suggested_number},
    )
    location_form = ObjectLocationForm(request.POST or None, prefix="site")
    if request.method == "POST" and form.is_valid():
        requested_number = str(form.cleaned_data.get("customer_number") or "").strip() or suggested_number
        if m.Customer.objects.filter(organization=org, number=requested_number).exists():
            form.add_error("customer_number", "Diese Kundennummer ist bereits vergeben.")
        else:
            with transaction.atomic():
                customer = form.save(commit=False)
                customer.organization = org
                customer.number = requested_number
                customer.save()
                if request.POST.get("site-street"):
                    if not location_form.is_valid():
                        transaction.set_rollback(True)
                    else:
                        location = location_form.save(commit=False)
                        location.organization = org
                        location.customer = customer
                        location.save()
            if not form.errors and not location_form.errors:
                messages.success(request, "Kunde wurde angelegt.")
                return redirect("next-customer-detail", pk=customer.pk)

    if modal:
        context = _customer_list_context(request, org, create_form=form, create_location_form=location_form, modal_open=True)
        return render(request, "rebuild/customers.html", context)
    return render(request, "rebuild/customer_form.html", {"form": form, "location_form": location_form, "mode": "create"})


@login_required
@require_http_methods(["GET", "POST"])
def customer_detail(request, pk):
    org = _org(request)
    customer = get_object_or_404(m.Customer, pk=pk, organization=org)
    if request.method == "POST":
        form = CustomerForm(request.POST, instance=customer, organization=org)
        if form.is_valid():
            requested_number = str(form.cleaned_data.get("customer_number") or customer.number).strip() or customer.number
            duplicate = m.Customer.objects.filter(organization=org, number=requested_number).exclude(pk=customer.pk).exists()
            if duplicate:
                form.add_error("customer_number", "Diese Kundennummer ist bereits vergeben.")
            else:
                customer = form.save(commit=False)
                customer.number = requested_number
                customer.save()
                messages.success(request, "Kundendaten gespeichert.")
                return redirect("next-customer-detail", pk=customer.pk)
    else:
        form = CustomerForm(instance=customer, organization=org, initial={"customer_number": customer.number})
    projects = customer.projects.filter(organization=org).order_by("-updated_at")
    locations = customer.object_locations.all()
    return render(request, "rebuild/customer_detail.html", {"customer": customer, "form": form, "projects": projects, "locations": locations})


@login_required
def supplier_list(request):
    org = _org(request)
    keyword = (request.GET.get("keyword") or request.GET.get("q") or "").strip()
    suppliers = m.CatalogItem.objects.filter(organization=org, active=True).exclude(supplier="")
    if keyword:
        suppliers = suppliers.filter(supplier__icontains=keyword)
    suppliers = suppliers.values("supplier").annotate(items_count=Count("id"), last_change=Max("updated_at")).order_by("supplier")
    return render(request, "rebuild/suppliers.html", {"suppliers": suppliers[:500], "keyword": keyword})
'''


def patch_views() -> None:
    path = "erp/rebuild_views.py"
    text = ensure_db_model_imports(read(path))

    form_pattern = re.compile(r"class CustomerForm\(StyledModelForm\):.*?(?=\n\nclass ObjectLocationForm\(StyledModelForm\):)", re.S)
    text, count = form_pattern.subn(CUSTOMER_FORM.rstrip(), text, count=1)
    if count != 1:
        raise RuntimeError("CustomerForm replacement anchor changed")

    view_pattern = re.compile(
        r"@login_required\ndef customer_list\(request\):.*?(?=\n\n@login_required\ndef project_list\(request\):)",
        re.S,
    )
    text, count = view_pattern.subn(CUSTOMER_VIEWS.rstrip(), text, count=1)
    if count != 1:
        raise RuntimeError("Customer view block replacement anchor changed")
    write(path, text)


def patch_urls() -> None:
    path = "erp/rebuild_urls.py"
    text = read(path)
    route = '    path("suppliers/", views.supplier_list, name="next-suppliers"),\n'
    if route not in text:
        anchor = '    path("customers/", views.customer_list, name="next-customers"),\n'
        if anchor not in text:
            raise RuntimeError("Customer URL anchor changed")
        text = text.replace(anchor, anchor + route, 1)
    write(path, text)


CUSTOMERS_TEMPLATE = r'''{% extends 'rebuild/base.html' %}
{% block title %}Kunden · A+Bau{% endblock %}
{% block content %}
<div class="tt-customers-page" data-customer-modal-open="{% if customer_modal_open %}1{% else %}0{% endif %}">
  <div class="tt-customers-head">
    <div class="tt-title-line"><h1>Kunden</h1><span class="tt-help" title="Kundenstamm verwalten">?</span></div>
    <div class="tt-customer-tools">
      <form method="get" class="tt-customer-search">
        <input type="hidden" name="sortType" value="{{ sort_type }}"><input type="hidden" name="sortOrder" value="{{ sort_order }}">
        <span>⌕</span><input name="keyword" value="{{ keyword }}" placeholder="Suchen" autocomplete="off">
      </form>
      <button class="nx-btn nx-btn-primary tt-new-customer" type="button" data-customer-modal-show>＋ Neuer Kunde</button>
    </div>
  </div>

  <section class="tt-customer-table-card">
    <div class="tt-customer-table-wrap">
      <table class="tt-customer-table">
        <thead><tr>
          <th><a href="?keyword={{ keyword|urlencode }}&sortType=NAME&sortOrder={{ name_sort_next }}&offset=0">Name {% if sort_type == 'NAME' %}<span>{% if sort_order == 'ASCENDING' %}↑{% else %}↓{% endif %}</span>{% endif %}</a></th>
          <th>Adresse</th>
          <th class="tt-num"><a href="?keyword={{ keyword|urlencode }}&sortType=PROJECTS&sortOrder={{ projects_sort_next }}&offset=0">Projekte {% if sort_type == 'PROJECTS' %}<span>{% if sort_order == 'ASCENDING' %}↑{% else %}↓{% endif %}</span>{% endif %}</a></th>
          <th><a href="?keyword={{ keyword|urlencode }}&sortType=LAST_CHANGE&sortOrder={{ last_change_sort_next }}&offset=0">Zuletzt geändert {% if sort_type == 'LAST_CHANGE' %}<span>{% if sort_order == 'ASCENDING' %}↑{% else %}↓{% endif %}</span>{% endif %}</a></th>
          <th class="tt-menu-col"></th>
        </tr></thead>
        <tbody>
        {% for customer in customers %}
          <tr data-customer-row data-href="{% url 'next-customer-detail' customer.pk %}" tabindex="0">
            <td><div class="tt-customer-name"><span class="tt-customer-kind">{% if customer.type == 'business' or customer.company %}▦{% else %}⌂{% endif %}</span><div><strong>{{ customer.display_name }}</strong>{% if customer.number %}<small>{{ customer.number }}</small>{% endif %}</div></div></td>
            <td><span>{{ customer.street|default:'–' }}</span><small>{% if customer.postal_code or customer.city %}{{ customer.postal_code }} {{ customer.city }}{% else %}–{% endif %}</small></td>
            <td class="tt-num">{{ customer.projects_count }}</td>
            <td>{{ customer.updated_at|date:'d.m.Y' }}</td>
            <td class="tt-menu-col">
              <details class="tt-row-menu" data-row-menu><summary aria-label="Aktionen">•••</summary><div><a href="{% url 'next-customer-detail' customer.pk %}">Öffnen</a><a href="{% url 'next-project-create' %}?customer={{ customer.pk }}">Projekt anlegen</a></div></details>
            </td>
          </tr>
        {% empty %}
          <tr><td colspan="5"><div class="nx-empty"><b>Keine Kunden gefunden.</b>Suche ändern oder einen neuen Kunden anlegen.</div></td></tr>
        {% endfor %}
        </tbody>
      </table>
    </div>
    <div class="tt-customer-pagination">
      <span>{{ total_count }} Einträge</span>
      <div>
        {% if has_prev %}<a class="nx-btn nx-btn-ghost" href="?keyword={{ keyword|urlencode }}&sortType={{ sort_type }}&sortOrder={{ sort_order }}&offset={{ prev_offset }}">← Zurück</a>{% else %}<span class="nx-btn nx-btn-ghost is-disabled">← Zurück</span>{% endif %}
        <span>{{ offset|add:'1' }}–{% if has_next %}{{ offset|add:page_size }}{% else %}{{ total_count }}{% endif %}</span>
        {% if has_next %}<a class="nx-btn nx-btn-ghost" href="?keyword={{ keyword|urlencode }}&sortType={{ sort_type }}&sortOrder={{ sort_order }}&offset={{ next_offset }}">Weiter →</a>{% else %}<span class="nx-btn nx-btn-ghost is-disabled">Weiter →</span>{% endif %}
      </div>
    </div>
  </section>

  <div class="tt-customer-modal" data-customer-modal hidden>
    <button type="button" class="tt-modal-backdrop" data-customer-modal-close aria-label="Schließen"></button>
    <section class="tt-customer-dialog" role="dialog" aria-modal="true" aria-labelledby="tt-create-customer-title">
      <form method="post" action="{% url 'next-customer-create' %}?modal=1" data-customer-modal-form>{% csrf_token %}<input type="hidden" name="modal" value="1">
        <header><h2 id="tt-create-customer-title">Kunde anlegen</h2><button type="button" data-customer-modal-close aria-label="Schließen">×</button></header>
        <div class="tt-customer-dialog-body">
          {% if create_form.non_field_errors %}<div class="tt-form-error">{{ create_form.non_field_errors }}</div>{% endif %}
          <div class="tt-type-radios">{{ create_form.type }}{{ create_form.type.errors }}</div>

          <div class="tt-field tt-company-only" data-company-only><label for="{{ create_form.company.id_for_label }}">Firmenname</label>{{ create_form.company }}{{ create_form.company.errors }}</div>
          <div class="tt-private-only tt-two-col" data-private-only>
            <div class="tt-field"><label for="{{ create_form.first_name.id_for_label }}">Vorname</label>{{ create_form.first_name }}{{ create_form.first_name.errors }}</div>
            <div class="tt-field"><label for="{{ create_form.last_name.id_for_label }}">Nachname</label>{{ create_form.last_name }}{{ create_form.last_name.errors }}</div>
          </div>

          <details class="tt-customer-details" open data-customer-details>
            <summary><span data-details-label>Details ausblenden</span><span>⌃</span></summary>
            <div class="tt-customer-details-body">
              <div class="tt-field"><label for="{{ create_form.notes.id_for_label }}">Beschreibung</label>{{ create_form.notes }}{{ create_form.notes.errors }}</div>
              <div class="tt-two-col">
                <div class="tt-field"><label for="{{ create_form.customer_number.id_for_label }}">Kundennummer <span title="Interne Kundennummer">ⓘ</span></label>{{ create_form.customer_number }}{{ create_form.customer_number.errors }}</div>
                <div class="tt-field"><label for="{{ create_form.debtor_number.id_for_label }}">Debitorennummer</label>{{ create_form.debtor_number }}{{ create_form.debtor_number.errors }}</div>
                <div class="tt-field"><label for="{{ create_form.routing_id.id_for_label }}">Routing-ID <span title="Leitweg-ID für E-Rechnungen">ⓘ</span></label>{{ create_form.routing_id }}{{ create_form.routing_id.errors }}</div>
                <div class="tt-field"><label for="{{ create_form.supplier_id.id_for_label }}">Lieferanten-ID <span title="Vom Kunden vergebene Lieferantenkennung">ⓘ</span></label>{{ create_form.supplier_id }}{{ create_form.supplier_id.errors }}</div>
                <div class="tt-field"><label for="{{ create_form.vat_id.id_for_label }}">USt-IdNr. <span title="Umsatzsteuer-Identifikationsnummer">ⓘ</span></label>{{ create_form.vat_id }}{{ create_form.vat_id.errors }}</div>
              </div>
            </div>
          </details>

          <h3>Rechnungsadresse</h3>
          <div class="tt-field"><label for="{{ create_form.street.id_for_label }}">Hausnummer, Straße</label>{{ create_form.street }}{{ create_form.street.errors }}</div>
          <div class="tt-two-col tt-address-grid">
            <div class="tt-field"><label for="{{ create_form.postal_code.id_for_label }}">PLZ</label>{{ create_form.postal_code }}{{ create_form.postal_code.errors }}</div>
            <div class="tt-field"><label for="{{ create_form.city.id_for_label }}">Ort</label>{{ create_form.city }}{{ create_form.city.errors }}</div>
          </div>
          <div class="tt-field"><label for="{{ create_form.country.id_for_label }}">Land</label>{{ create_form.country }}{{ create_form.country.errors }}</div>

          <h3>Kontakt</h3>
          <div class="tt-two-col">
            <div class="tt-field"><label for="{{ create_form.salutation.id_for_label }}">Anrede</label>{{ create_form.salutation }}{{ create_form.salutation.errors }}</div>
            <div class="tt-field tt-company-contact"><label for="{{ create_form.first_name.id_for_label }}">Vorname</label>{{ create_form.first_name }}{{ create_form.first_name.errors }}</div>
            <div class="tt-field tt-company-contact"><label for="{{ create_form.last_name.id_for_label }}">Nachname</label>{{ create_form.last_name }}{{ create_form.last_name.errors }}</div>
            <div class="tt-field"><label for="{{ create_form.email.id_for_label }}">E-Mail</label>{{ create_form.email }}{{ create_form.email.errors }}</div>
            <div class="tt-field"><label for="{{ create_form.phone.id_for_label }}">Telefon</label>{{ create_form.phone }}{{ create_form.phone.errors }}</div>
            <div class="tt-field"><label for="{{ create_form.mobile.id_for_label }}">Mobil</label>{{ create_form.mobile }}{{ create_form.mobile.errors }}</div>
          </div>
        </div>
        <footer><button class="nx-btn" type="button" data-customer-modal-close>Abbrechen</button><button class="nx-btn nx-btn-primary" type="submit">＋ Anlegen</button></footer>
      </form>
    </section>
  </div>
</div>
{% endblock %}
'''


SUPPLIERS_TEMPLATE = r'''{% extends 'rebuild/base.html' %}
{% block title %}Lieferanten · A+Bau{% endblock %}
{% block content %}
<div class="tt-customers-page">
  <div class="tt-customers-head"><div class="tt-title-line"><h1>Lieferanten</h1><span class="tt-help" title="Aus dem Leistungskatalog erkannte Lieferanten">?</span></div><form method="get" class="tt-customer-search"><span>⌕</span><input name="keyword" value="{{ keyword }}" placeholder="Suchen"></form></div>
  <section class="tt-customer-table-card"><div class="tt-customer-table-wrap"><table class="tt-customer-table"><thead><tr><th>Name</th><th class="tt-num">Katalogpositionen</th><th>Zuletzt geändert</th></tr></thead><tbody>
  {% for supplier in suppliers %}<tr><td><div class="tt-customer-name"><span class="tt-customer-kind">▦</span><strong>{{ supplier.supplier }}</strong></div></td><td class="tt-num">{{ supplier.items_count }}</td><td>{{ supplier.last_change|date:'d.m.Y' }}</td></tr>{% empty %}<tr><td colspan="3"><div class="nx-empty"><b>Keine Lieferanten gefunden.</b>Lieferanten werden aus dem vorhandenen Katalog zusammengeführt.</div></td></tr>{% endfor %}
  </tbody></table></div></section>
</div>
{% endblock %}
'''


DIRECT_CUSTOMER_FORM_TEMPLATE = r'''{% extends 'rebuild/base.html' %}
{% block title %}Neuer Kunde · A+Bau{% endblock %}
{% block content %}
<div class="nx-pagehead"><div><div class="nx-kicker">Kontakte</div><h1>Neuen Kunden anlegen</h1><p>Die gleichen Kundendaten wie im Schnell-Dialog, als vollständige Seite.</p></div></div>
<form class="nx-form" method="post">{% csrf_token %}<section class="nx-card nx-card-pad"><div class="nx-form-grid">{% for field in form %}<div class="nx-field {% if field.name == 'notes' or field.name == 'street' %}nx-field-full{% endif %}"><label for="{{ field.id_for_label }}">{{ field.label }}</label>{{ field }}{{ field.errors }}</div>{% endfor %}</div></section><details class="nx-card nx-card-pad nx-progressive"><summary>＋ Abweichenden Einsatzort hinzufügen</summary><div class="nx-form-grid nx-progressive-body">{% for field in location_form %}<div class="nx-field {% if field.name == 'access_notes' or field.name == 'street' %}nx-field-full{% endif %}"><label for="{{ field.id_for_label }}">{{ field.label }}</label>{{ field }}{{ field.errors }}</div>{% endfor %}</div></details><div class="nx-form-actions"><a class="nx-btn" href="{% url 'next-customers' %}">Abbrechen</a><button class="nx-btn nx-btn-primary" type="submit">Kunde anlegen</button></div></form>
{% endblock %}
'''


def install_templates() -> None:
    write("templates/rebuild/customers.html", CUSTOMERS_TEMPLATE)
    write("templates/rebuild/suppliers.html", SUPPLIERS_TEMPLATE)
    write("templates/rebuild/customer_form.html", DIRECT_CUSTOMER_FORM_TEMPLATE)


def patch_sidebar() -> None:
    path = "templates/rebuild/base.html"
    text = read(path)
    if "data-contacts-group" in text and "next-suppliers" in text:
        return
    pattern = re.compile(r'(?P<indent>[ \t]*)<a\b[^>]*href="\{% url [\'\"]next-customers[\'\"] %\}"[^>]*>.*?</a>', re.S)
    match = pattern.search(text)
    if not match:
        raise RuntimeError("Customer sidebar link anchor changed")
    indent = match.group("indent")
    group = f'''{indent}<div class="nx-nav-group nx-contacts-group" data-contacts-group>
{indent}  <button type="button" class="nx-nav-parent {{% if 'customer' in request.resolver_match.url_name or 'supplier' in request.resolver_match.url_name %}}is-active{{% endif %}}" data-contacts-toggle><span class="nx-ico">▤</span><span>Kontakte</span><span class="nx-nav-chevron">⌃</span></button>
{indent}  <div class="nx-nav-sub">
{indent}    <a class="{{% if 'customer' in request.resolver_match.url_name %}}is-active{{% endif %}}" href="{{% url 'next-customers' %}}"><span class="nx-sub-dot"></span>Kunden</a>
{indent}    <a class="{{% if 'supplier' in request.resolver_match.url_name %}}is-active{{% endif %}}" href="{{% url 'next-suppliers' %}}"><span class="nx-sub-dot"></span>Lieferanten</a>
{indent}  </div>
{indent}</div>'''
    text = text[: match.start()] + group + text[match.end() :]
    write(path, text)


CSS = r'''
/* A+Bau ToolTime customer contacts parity 20260821 */
.tt-customers-page{display:grid;gap:18px}.tt-customers-head{display:flex;align-items:center;justify-content:space-between;gap:18px}.tt-title-line{display:flex;align-items:center;gap:10px}.tt-title-line h1{margin:0;font-size:30px;letter-spacing:-.03em}.tt-help{width:20px;height:20px;border:1px solid #9fb0c0;border-radius:50%;display:grid;place-items:center;font-size:12px;font-weight:800;color:#516273}.tt-customer-tools{display:flex;align-items:center;gap:12px}.tt-customer-search{height:42px;min-width:280px;border:1px solid #d8e0e7;border-radius:9px;background:#fff;display:flex;align-items:center;gap:8px;padding:0 12px}.tt-customer-search:focus-within{border-color:#568fd0;box-shadow:0 0 0 3px rgba(41,121,204,.1)}.tt-customer-search input{border:0!important;box-shadow:none!important;outline:0;background:transparent;width:100%;height:100%;padding:0!important}.tt-new-customer{height:42px}.tt-customer-table-card{background:#fff;border:1px solid #dfe5eb;border-radius:10px;overflow:visible}.tt-customer-table-wrap{overflow:auto}.tt-customer-table{width:100%;border-collapse:collapse;min-width:820px}.tt-customer-table th{height:48px;padding:0 14px;text-align:left;border-bottom:1px solid #dfe5eb;font-size:12px;font-weight:700;color:#607080;white-space:nowrap}.tt-customer-table th a{color:inherit;text-decoration:none}.tt-customer-table td{padding:12px 14px;border-bottom:1px solid #edf1f4;vertical-align:middle;font-size:14px}.tt-customer-table tbody tr[data-customer-row]{cursor:pointer}.tt-customer-table tbody tr[data-customer-row]:hover{background:#f7fafc}.tt-customer-table tbody tr:last-child td{border-bottom:0}.tt-customer-table td small{display:block;color:#7b8996;margin-top:3px}.tt-customer-name{display:flex;align-items:center;gap:10px}.tt-customer-name strong{font-weight:750}.tt-customer-kind{width:22px;height:22px;display:grid;place-items:center;color:#708395;font-size:17px}.tt-num{text-align:center!important}.tt-menu-col{width:50px;text-align:right!important}.tt-row-menu{position:relative;display:inline-block}.tt-row-menu summary{list-style:none;cursor:pointer;font-weight:900;letter-spacing:2px;padding:7px;border-radius:6px}.tt-row-menu summary::-webkit-details-marker{display:none}.tt-row-menu[open] summary{background:#eef4f9}.tt-row-menu>div{position:absolute;right:0;top:38px;z-index:12;min-width:170px;background:#fff;border:1px solid #dce4ea;border-radius:8px;box-shadow:0 12px 30px rgba(17,33,48,.16);padding:6px}.tt-row-menu a{display:block;padding:9px 10px;border-radius:6px;color:#213142;text-decoration:none;white-space:nowrap}.tt-row-menu a:hover{background:#f2f6f9}.tt-customer-pagination{min-height:54px;padding:9px 14px;border-top:1px solid #edf1f4;display:flex;justify-content:space-between;align-items:center;color:#71808e;font-size:13px}.tt-customer-pagination>div{display:flex;align-items:center;gap:10px}.is-disabled{opacity:.45;pointer-events:none}.tt-customer-modal{position:fixed;inset:0;z-index:1000;display:grid;place-items:center;padding:24px}.tt-customer-modal[hidden]{display:none}.tt-modal-backdrop{position:absolute;inset:0;border:0;background:rgba(15,25,35,.42);backdrop-filter:blur(1px)}.tt-customer-dialog{position:relative;width:min(720px,calc(100vw - 32px));max-height:min(840px,calc(100vh - 48px));background:#fff;border-radius:14px;box-shadow:0 24px 70px rgba(10,24,38,.28);overflow:hidden}.tt-customer-dialog form{display:grid;grid-template-rows:auto minmax(0,1fr) auto;max-height:inherit}.tt-customer-dialog header{display:flex;align-items:center;justify-content:space-between;padding:22px 28px 14px}.tt-customer-dialog header h2{margin:0;font-size:20px}.tt-customer-dialog header button{width:34px;height:34px;border:0;background:transparent;border-radius:50%;font-size:26px;color:#61717f;cursor:pointer}.tt-customer-dialog header button:hover{background:#f1f4f6}.tt-customer-dialog-body{padding:8px 28px 28px;overflow:auto}.tt-customer-dialog footer{padding:14px 28px;border-top:1px solid #e6ebef;display:flex;justify-content:flex-end;gap:10px;background:#fff}.tt-type-radios{margin-bottom:18px}.tt-type-radios ul{display:flex;gap:22px;list-style:none;padding:0;margin:0}.tt-type-radios label{display:flex;align-items:center;gap:7px;font-weight:600;cursor:pointer}.tt-type-radios input{width:18px;height:18px;accent-color:#1674d1}.tt-field{display:grid;gap:6px;margin-bottom:15px}.tt-field label{font-size:12px;font-weight:700;color:#4e5e6c}.tt-field input,.tt-field select,.tt-field textarea{width:100%;border:1px solid #ccd6df;border-radius:7px;background:#fff;padding:10px 11px;min-height:42px;font:inherit;color:#253444}.tt-field textarea{min-height:86px;resize:vertical}.tt-field input:focus,.tt-field select:focus,.tt-field textarea:focus{outline:0;border-color:#3b83c8;box-shadow:0 0 0 3px rgba(31,117,199,.1)}.tt-field .errorlist,.tt-type-radios .errorlist{list-style:none;padding:0;margin:2px 0 0;color:#b42318;font-size:12px}.tt-two-col{display:grid;grid-template-columns:1fr 1fr;gap:14px}.tt-address-grid{grid-template-columns:160px 1fr}.tt-customer-details{border:0;margin:4px 0 18px}.tt-customer-details summary{list-style:none;display:flex;align-items:center;gap:8px;color:#1473cc;font-size:13px;font-weight:700;cursor:pointer;margin-bottom:14px}.tt-customer-details summary::-webkit-details-marker{display:none}.tt-customer-details:not([open]) summary span:last-child{transform:rotate(180deg)}.tt-customer-dialog-body h3{font-size:15px;margin:22px 0 12px}.tt-private-only[hidden],.tt-company-only[hidden],.tt-company-contact[hidden]{display:none!important}.tt-form-error{background:#fff1f0;color:#a51d15;border:1px solid #ffd2ce;border-radius:8px;padding:10px 12px;margin-bottom:12px}.nx-nav-group{display:grid}.nx-nav-parent{width:100%;border:0;background:transparent;color:inherit;font:inherit;text-align:left;display:grid;grid-template-columns:28px 1fr 20px;align-items:center;padding:10px 12px;border-radius:8px;cursor:pointer}.nx-nav-parent:hover,.nx-nav-parent.is-active{background:rgba(255,255,255,.07)}.nx-nav-chevron{transition:transform .2s}.nx-contacts-group.is-collapsed .nx-nav-chevron{transform:rotate(180deg)}.nx-nav-sub{display:grid;padding:2px 0 5px 38px}.nx-contacts-group.is-collapsed .nx-nav-sub{display:none}.nx-nav-sub a{display:flex!important;align-items:center;gap:9px!important;padding:8px 10px!important;font-size:13px!important}.nx-sub-dot{width:5px;height:5px;border-radius:50%;background:currentColor;opacity:.45}.nx-nav-sub a.is-active .nx-sub-dot{opacity:1}.tt-customer-modal-open{overflow:hidden}
@media(max-width:760px){.tt-customers-head{align-items:stretch;flex-direction:column}.tt-customer-tools{display:grid;grid-template-columns:1fr auto}.tt-customer-search{min-width:0}.tt-customer-dialog{width:100%;max-height:calc(100vh - 16px);border-radius:12px}.tt-customer-modal{padding:8px}.tt-customer-dialog header,.tt-customer-dialog footer{padding-left:18px;padding-right:18px}.tt-customer-dialog-body{padding-left:18px;padding-right:18px}.tt-two-col{grid-template-columns:1fr}.tt-address-grid{grid-template-columns:1fr}.tt-customer-pagination{align-items:flex-start;gap:8px;flex-direction:column}}
'''


JS = r'''
/* A+Bau ToolTime customer contacts parity 20260821 */
(() => {
  const page = document.querySelector('.tt-customers-page');
  const modal = document.querySelector('[data-customer-modal]');
  const openModal = () => {
    if (!modal) return;
    modal.hidden = false;
    document.documentElement.classList.add('tt-customer-modal-open');
    const first = modal.querySelector('input:not([type="hidden"]),select,textarea,button');
    window.setTimeout(() => first?.focus(), 30);
  };
  const closeModal = () => {
    if (!modal) return;
    modal.hidden = true;
    document.documentElement.classList.remove('tt-customer-modal-open');
  };
  document.querySelectorAll('[data-customer-modal-show]').forEach((button) => button.addEventListener('click', openModal));
  document.querySelectorAll('[data-customer-modal-close]').forEach((button) => button.addEventListener('click', closeModal));
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && modal && !modal.hidden) closeModal(); });
  if (page?.dataset.customerModalOpen === '1') openModal();

  const form = document.querySelector('[data-customer-modal-form]');
  const syncType = () => {
    if (!form) return;
    const value = form.querySelector('input[name="type"]:checked')?.value || 'business';
    const business = value === 'business';
    form.querySelectorAll('[data-company-only]').forEach((node) => { node.hidden = !business; });
    form.querySelectorAll('[data-private-only]').forEach((node) => { node.hidden = business; });
    form.querySelectorAll('.tt-company-contact').forEach((node) => { node.hidden = !business; });
  };
  form?.querySelectorAll('input[name="type"]').forEach((radio) => radio.addEventListener('change', syncType));
  syncType();

  const details = document.querySelector('[data-customer-details]');
  const syncDetails = () => {
    const label = details?.querySelector('[data-details-label]');
    if (label) label.textContent = details.open ? 'Details ausblenden' : 'Details anzeigen';
  };
  details?.addEventListener('toggle', syncDetails);
  syncDetails();

  document.querySelectorAll('[data-customer-row]').forEach((row) => {
    const go = () => { if (row.dataset.href) window.location.href = row.dataset.href; };
    row.addEventListener('click', (event) => {
      if (event.target.closest('a,button,summary,details,input,select,textarea,label')) return;
      go();
    });
    row.addEventListener('keydown', (event) => {
      if ((event.key === 'Enter' || event.key === ' ') && !event.target.closest('a,button,summary,details')) { event.preventDefault(); go(); }
    });
  });

  document.querySelectorAll('[data-row-menu]').forEach((menu) => {
    menu.addEventListener('toggle', () => {
      if (!menu.open) return;
      document.querySelectorAll('[data-row-menu][open]').forEach((other) => { if (other !== menu) other.removeAttribute('open'); });
    });
  });

  document.querySelectorAll('[data-contacts-group]').forEach((group) => {
    const toggle = group.querySelector('[data-contacts-toggle]');
    toggle?.addEventListener('click', () => group.classList.toggle('is-collapsed'));
  });
})();
'''


def patch_assets() -> None:
    css_path = "static/css/kayi-next.css"
    css = read(css_path)
    if ASSET_MARKER not in css:
        css = css.rstrip() + "\n\n" + CSS.strip() + "\n"
        write(css_path, css)
    js_path = "static/js/kayi-next.js"
    js = read(js_path)
    if ASSET_MARKER not in js:
        js = js.rstrip() + "\n\n" + JS.strip() + "\n"
        write(js_path, js)


def install_contract_test() -> None:
    test = r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimeCustomerContactsParityContract(SimpleTestCase):
    def test_customer_schema_and_migration(self):
        models = (ROOT / "erp/models.py").read_text(encoding="utf-8")
        migration = (ROOT / "erp/migrations/0011_tooltime_customer_contacts.py").read_text(encoding="utf-8")
        for needle in ("debtor_number = models.CharField", "routing_id = models.CharField", "supplier_id = models.CharField"):
            self.assertIn(needle, models)
        for needle in ("debtor_number", "routing_id", "supplier_id", "0010_ab_bau_commercial"):
            self.assertIn(needle, migration)

    def test_customer_list_is_tooltime_operational(self):
        views = (ROOT / "erp/rebuild_views.py").read_text(encoding="utf-8")
        template = (ROOT / "templates/rebuild/customers.html").read_text(encoding="utf-8")
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        for needle in ("projects_count=Count(\"projects\", distinct=True)", "sortType", "sortOrder", "offset", "def supplier_list"):
            self.assertIn(needle, views)
        for needle in ("data-customer-modal", "Debitorennummer", "Routing-ID", "Lieferanten-ID", "Projekte", "Zuletzt geändert", "data-row-menu"):
            self.assertIn(needle, template)
        self.assertIn('name="next-suppliers"', urls)
        self.assertIn("data-contacts-group", base)
        self.assertIn("Kontakte", base)
        self.assertIn("Lieferanten", base)

    def test_customer_interactions_are_real(self):
        js = (ROOT / "static/js/kayi-next.js").read_text(encoding="utf-8")
        css = (ROOT / "static/css/kayi-next.css").read_text(encoding="utf-8")
        self.assertIn("data-customer-modal-show", js)
        self.assertIn("data-customer-row", js)
        self.assertIn("data-contacts-toggle", js)
        self.assertIn("A+Bau ToolTime customer contacts parity 20260821", css)
'''
    write("tests/test_tooltime_customer_contacts_parity.py", test)


def guard() -> None:
    models = read("erp/models.py")
    views = read("erp/rebuild_views.py")
    urls = read("erp/rebuild_urls.py")
    customers = read("templates/rebuild/customers.html")
    suppliers = read("templates/rebuild/suppliers.html")
    base = read("templates/rebuild/base.html")
    css = read("static/css/kayi-next.css")
    js = read("static/js/kayi-next.js")
    migration = read(f"erp/migrations/{MIGRATION_NAME}.py")
    for needle in ("debtor_number = models.CharField", "routing_id = models.CharField", "supplier_id = models.CharField"):
        if needle not in models:
            raise RuntimeError(f"Customer model parity missing: {needle}")
    for needle in ("projects_count=Count(\"projects\", distinct=True)", "def supplier_list", "modal=modal"):
        if needle not in views:
            raise RuntimeError(f"Customer backend parity missing: {needle}")
    for needle in ("next-suppliers", "suppliers/"):
        if needle not in urls:
            raise RuntimeError(f"Contacts route missing: {needle}")
    for needle in ("data-customer-modal", "Debitorennummer", "Routing-ID", "Lieferanten-ID", "Zuletzt geändert", "data-row-menu"):
        if needle not in customers:
            raise RuntimeError(f"Customer UI parity missing: {needle}")
    if "Lieferanten" not in suppliers or "Katalogpositionen" not in suppliers:
        raise RuntimeError("Supplier list UI missing")
    for needle in ("data-contacts-group", "Kontakte", "next-suppliers"):
        if needle not in base:
            raise RuntimeError(f"Contacts navigation missing: {needle}")
    if ASSET_MARKER not in css or ASSET_MARKER not in js:
        raise RuntimeError("Customer parity assets missing")
    for needle in ("0010_ab_bau_commercial", "debtor_number", "routing_id", "supplier_id"):
        if needle not in migration:
            raise RuntimeError(f"Customer parity migration missing: {needle}")


patch_customer_model()
install_migration()
patch_views()
patch_urls()
install_templates()
patch_sidebar()
patch_assets()
install_contract_test()
guard()
print("A+Bau customer/contacts parity installed: ToolTime list, modal create, sorting, project counts, identifiers, row actions and supplier navigation are live.")
