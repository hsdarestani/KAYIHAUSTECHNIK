from __future__ import annotations

import re
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME CUSTOMER DIRECT FORM COMPAT 2026-08-21"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Customer direct-form compatibility target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    (ROOT / rel).write_text(text, encoding="utf-8")


# Customer/contacts parity deliberately keeps the ToolTime list/modal UX, but the
# direct route must retain older operational contracts: company/name fields are
# progressive (not server-required), a blank collapsed Einsatzort must never block
# save, and ?next=project returns to project creation with the new customer selected.
views_path = "erp/rebuild_views.py"
views = read(views_path)
customer_form_pattern = re.compile(
    r"class CustomerForm\(StyledModelForm\):(?P<body>.*?)(?=\n\nclass ObjectLocationForm\(StyledModelForm\):)",
    re.S,
)
match = customer_form_pattern.search(views)
if not match:
    raise RuntimeError("Final CustomerForm compatibility anchor changed")
form_block = match.group(0)
form_block = re.sub(
    r"\n    def clean\(self\):\n        cleaned = super\(\)\.clean\(\)\n        customer_type = cleaned\.get\(\"type\"\)\n        if customer_type == \"business\" and not str\(cleaned\.get\(\"company\"\) or \"\"\)\.strip\(\):\n            self\.add_error\(\"company\", \"Bitte den Firmennamen angeben\.\"\)\n        if customer_type == \"private\" and not \(str\(cleaned\.get\(\"first_name\"\) or \"\"\)\.strip\(\) or str\(cleaned\.get\(\"last_name\"\) or \"\"\)\.strip\(\)\):\n            self\.add_error\(\"last_name\", \"Bitte mindestens einen Namen angeben\.\"\)\n        return cleaned\n?",
    "",
    form_block,
    count=1,
)
views = views[: match.start()] + form_block + views[match.end() :]

customer_create_pattern = re.compile(
    r'@login_required\n@require_http_methods\(\["GET", "POST"\]\)\ndef customer_create\(request\):.*?(?=\n\n@login_required\n@require_http_methods\(\["GET", "POST"\]\)\ndef customer_detail)',
    re.S,
)
customer_create = '''@login_required
@require_http_methods(["GET", "POST"])
def customer_create(request):
    org = _org(request)
    modal = request.GET.get("modal") == "1" or request.POST.get("modal") == "1"
    next_target = (request.POST.get("next") if request.method == "POST" else request.GET.get("next")) or ""
    next_target = next_target if next_target in {"project"} else ""
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
            location_requested = bool(str(request.POST.get("site-street") or "").strip())
            location_valid = (not location_requested) or location_form.is_valid()
            if location_valid:
                with transaction.atomic():
                    customer = form.save(commit=False)
                    customer.organization = org
                    customer.number = requested_number
                    customer.save()
                    if location_requested:
                        location = location_form.save(commit=False)
                        location.organization = org
                        location.customer = customer
                        location.save()
                messages.success(request, "Kunde wurde angelegt.")
                if next_target == "project":
                    return redirect(f"/projects/new/?customer={customer.pk}")
                return redirect("next-customer-detail", pk=customer.pk)

    if modal:
        context = _customer_list_context(
            request,
            org,
            create_form=form,
            create_location_form=location_form,
            modal_open=True,
        )
        return render(request, "rebuild/customers.html", context)
    return render(request, "rebuild/customer_form.html", {
        "form": form,
        "location_form": location_form,
        "mode": "create",
        "next_target": next_target,
    })
'''
views, count = customer_create_pattern.subn(customer_create.rstrip(), views, count=1)
if count != 1:
    raise RuntimeError("Final customer_create compatibility anchor changed")
write(views_path, views)


TEMPLATE = r'''{% extends 'rebuild/base.html' %}
{% block title %}Neuer Kunde · A+Bau{% endblock %}
{% block content %}
<div class="tt-create-shell tt-customer-create" data-tt-customer-create>
  <div class="tt-create-head"><div><a class="tt-back" href="{% if next_target == 'project' %}{% url 'next-project-create' %}{% else %}{% url 'next-customers' %}{% endif %}">← Zurück</a><h1>Neuer Kunde</h1><p>Die Schnellanlage ist auch direkt erreichbar; auf der Kundenliste öffnet sie sich als Dialog.</p></div></div>
  <form method="post" class="tt-create-form" data-customer-form novalidate>{% csrf_token %}
    {% if next_target %}<input type="hidden" name="next" value="{{ next_target }}">{% endif %}
    {% if form.errors or location_form.errors %}<div class="tt-form-alert" role="alert"><strong>Bitte prüfen Sie die markierten Felder.</strong>{% if form.non_field_errors %} {{ form.non_field_errors }}{% endif %}{% if location_form.non_field_errors %} {{ location_form.non_field_errors }}{% endif %}</div>{% endif %}
    <section class="tt-create-card">
      <h2>Kundendaten</h2>
      <div class="tt-grid tt-grid-2">
        <div class="tt-field tt-span-2"><label for="{{ form.type.id_for_label }}">Kundentyp</label>{{ form.type }}{{ form.type.errors }}</div>
        <div class="tt-field tt-span-2"><label for="{{ form.company.id_for_label }}">Firmenname</label>{{ form.company }}{{ form.company.errors }}</div>
        <div class="tt-field"><label for="{{ form.first_name.id_for_label }}">Vorname</label>{{ form.first_name }}{{ form.first_name.errors }}</div>
        <div class="tt-field"><label for="{{ form.last_name.id_for_label }}">Nachname</label>{{ form.last_name }}{{ form.last_name.errors }}</div>
        <div class="tt-field"><label for="{{ form.email.id_for_label }}">E-Mail</label>{{ form.email }}{{ form.email.errors }}</div>
        <div class="tt-field"><label for="{{ form.phone.id_for_label }}">Telefon</label>{{ form.phone }}{{ form.phone.errors }}</div>
        <div class="tt-field"><label for="{{ form.mobile.id_for_label }}">Mobil</label>{{ form.mobile }}{{ form.mobile.errors }}</div>
      </div>
    </section>
    <section class="tt-create-card">
      <h2>Rechnungsadresse</h2>
      <div class="tt-grid tt-grid-2">
        <div class="tt-field tt-span-2"><label for="{{ form.street.id_for_label }}">Straße und Hausnummer</label>{{ form.street }}{{ form.street.errors }}</div>
        <div class="tt-field"><label for="{{ form.postal_code.id_for_label }}">PLZ</label>{{ form.postal_code }}{{ form.postal_code.errors }}</div>
        <div class="tt-field"><label for="{{ form.city.id_for_label }}">Ort</label>{{ form.city }}{{ form.city.errors }}</div>
        <div class="tt-field tt-span-2"><label for="{{ form.country.id_for_label }}">Land</label>{{ form.country }}{{ form.country.errors }}</div>
      </div>
    </section>
    <details class="tt-create-card tt-details" data-more-details {% if form.salutation.errors or form.vat_id.errors or form.notes.errors or form.customer_number.errors or form.debtor_number.errors or form.routing_id.errors or form.supplier_id.errors %}open{% endif %}>
      <summary><span>Weitere Angaben</span><span class="tt-chevron">⌄</span></summary>
      <div class="tt-details-body tt-grid tt-grid-2">
        <div class="tt-field"><label for="{{ form.salutation.id_for_label }}">Anrede</label>{{ form.salutation }}{{ form.salutation.errors }}</div>
        <div class="tt-field"><label for="{{ form.customer_number.id_for_label }}">Kundennummer</label>{{ form.customer_number }}{{ form.customer_number.errors }}</div>
        <div class="tt-field"><label for="{{ form.debtor_number.id_for_label }}">Debitorennummer</label>{{ form.debtor_number }}{{ form.debtor_number.errors }}</div>
        <div class="tt-field"><label for="{{ form.routing_id.id_for_label }}">Routing-ID</label>{{ form.routing_id }}{{ form.routing_id.errors }}</div>
        <div class="tt-field"><label for="{{ form.supplier_id.id_for_label }}">Lieferanten-ID</label>{{ form.supplier_id }}{{ form.supplier_id.errors }}</div>
        <div class="tt-field"><label for="{{ form.vat_id.id_for_label }}">USt-IdNr.</label>{{ form.vat_id }}{{ form.vat_id.errors }}</div>
        <div class="tt-field tt-span-2"><label for="{{ form.notes.id_for_label }}">Beschreibung</label>{{ form.notes }}{{ form.notes.errors }}</div>
      </div>
    </details>
    <details class="tt-create-card tt-details tt-location-details" data-location-details {% if location_form.errors %}open{% endif %}>
      <summary><span>Abweichenden Ausführungsort hinzufügen</span><span class="tt-chevron">⌄</span></summary>
      <div class="tt-details-body tt-grid tt-grid-2">{% for field in location_form %}<div class="tt-field {% if field.name == 'access_notes' or field.name == 'street' %}tt-span-2{% endif %}"><label for="{{ field.id_for_label }}">{{ field.label }}</label>{{ field }}{{ field.errors }}</div>{% endfor %}</div>
    </details>
    <div class="tt-create-actions"><a class="nx-btn" href="{% if next_target == 'project' %}{% url 'next-project-create' %}{% else %}{% url 'next-customers' %}{% endif %}">Abbrechen</a><button class="nx-btn nx-btn-primary" type="submit">＋ Erstellen</button></div>
  </form>
</div>
{% endblock %}
'''

path = ROOT / "templates" / "rebuild" / "customer_form.html"
path.write_text(TEMPLATE, encoding="utf-8")
text = path.read_text(encoding="utf-8")
for needle in ("data-more-details", "data-location-details", "Weitere Angaben", "novalidate", "Bitte prüfen Sie die markierten Felder.", "customer_number", "debtor_number", "routing_id", "supplier_id", "＋ Erstellen"):
    if needle not in text:
        raise RuntimeError(f"Direct customer ToolTime compatibility missing: {needle}")
final_views = read(views_path)
for needle in ('next_target == "project"', 'return redirect(f"/projects/new/?customer={customer.pk}")', "location_requested"):
    if needle not in final_views:
        raise RuntimeError(f"Direct customer save compatibility missing: {needle}")
print("A+Bau direct customer route kept compatible with ToolTime progressive-detail and save contracts.")

# This script is invoked only after the complete appointment parity chain. Move
# the temporary customer-field migration behind the final appointment migration
# so Django sees a single deterministic leaf during makemigrations --check.
runpy.run_path(str(ROOT / "scripts" / "tooltime_customer_migration_closeout.py"), run_name="__main__")
