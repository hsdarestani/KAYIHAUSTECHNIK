from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME CUSTOMER DIRECT FORM COMPAT 2026-08-21"

TEMPLATE = r'''{% extends 'rebuild/base.html' %}
{% block title %}Neuer Kunde · A+Bau{% endblock %}
{% block content %}
<div class="tt-create-shell tt-customer-create" data-tt-customer-create>
  <div class="tt-create-head"><div><a class="tt-back" href="{% url 'next-customers' %}">← Zurück</a><h1>Neuer Kunde</h1><p>Die Schnellanlage ist auch direkt erreichbar; auf der Kundenliste öffnet sie sich als Dialog.</p></div></div>
  <form method="post" class="tt-create-form" data-customer-form>{% csrf_token %}
    {% if form.non_field_errors %}<div class="tt-form-alert">{{ form.non_field_errors }}</div>{% endif %}
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
      <summary><span>Details einblenden</span><span class="tt-chevron">⌄</span></summary>
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
    <div class="tt-create-actions"><a class="nx-btn" href="{% url 'next-customers' %}">Abbrechen</a><button class="nx-btn nx-btn-primary" type="submit">＋ Erstellen</button></div>
  </form>
</div>
{% endblock %}
'''

path = ROOT / "templates" / "rebuild" / "customer_form.html"
path.write_text(TEMPLATE, encoding="utf-8")
text = path.read_text(encoding="utf-8")
for needle in (MARKER.split(" 2026")[0],):
    pass
for needle in ("data-more-details", "data-location-details", "Details einblenden", "customer_number", "debtor_number", "routing_id", "supplier_id", "＋ Erstellen"):
    if needle not in text:
        raise RuntimeError(f"Direct customer ToolTime compatibility missing: {needle}")
print("A+Bau direct customer route kept compatible with ToolTime progressive-detail browser contract.")

# This script is invoked only after the complete appointment parity chain. Move
# the temporary customer-field migration behind the final appointment migration
# so Django sees a single deterministic leaf during makemigrations --check.
runpy.run_path(str(ROOT / "scripts" / "tooltime_customer_migration_closeout.py"), run_name="__main__")
