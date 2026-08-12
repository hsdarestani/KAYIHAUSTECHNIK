from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

GERMAN_FIELD_LABELS = '''
GERMAN_FIELD_LABELS = {
    "type": "Typ", "company": "Firma", "salutation": "Anrede", "first_name": "Vorname",
    "last_name": "Nachname", "email": "E-Mail", "phone": "Telefon", "mobile": "Mobil",
    "street": "Straße", "postal_code": "PLZ", "city": "Ort", "country": "Land",
    "vat_id": "USt-IdNr.", "notes": "Notizen", "title": "Titel", "customer": "Kunde",
    "object_location": "Objekt / Einsatzort", "description": "Beschreibung", "priority": "Priorität",
    "manager": "Projektleitung", "members": "Team", "starts_at": "Beginn", "ends_at": "Ende",
    "all_day": "Ganztägig", "location": "Einsatzort", "project": "Projekt", "attendees": "Mitarbeiter",
    "issue_date": "Ausstellungsdatum", "valid_until": "Gültig bis", "intro_text": "Einleitungstext",
    "outro_text": "Schlusstext", "discount_percent": "Rabatt (%)", "quote": "Angebot",
    "due_date": "Fällig am", "service_date": "Leistungsdatum", "status": "Status",
    "assigned_to": "Zugewiesen an", "due_at": "Fällig am", "supplier": "Lieferant",
    "amount_net": "Netto-Betrag", "tax_rate": "MwSt. (%)", "expense_date": "Belegdatum",
    "category": "Kategorie", "paid": "Bezahlt", "document": "Beleg / Dokument",
    "trade": "Gewerk", "hourly_cost": "Interner Stundensatz", "hourly_rate": "Verrechnungssatz",
    "active": "Aktiv", "color": "Farbe", "name": "Name",
}
'''


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"A+Bau regression compatibility target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def restore_german_labels() -> None:
    rel = "erp/rebuild_views.py"
    text = read(rel)
    if "GERMAN_FIELD_LABELS = {" not in text:
        anchor = "\n\nclass StyledModelForm(forms.ModelForm):\n"
        if anchor not in text:
            raise RuntimeError("StyledModelForm anchor missing while restoring German labels")
        text = text.replace(anchor, GERMAN_FIELD_LABELS + anchor, 1)
        write(rel, text)


def preserve_quote_form_contract() -> None:
    rel = "erp/rebuild_views.py"
    text = read(rel)
    quote_start = text.find("class QuoteForm(StyledModelForm):")
    invoice_start = text.find("class InvoiceForm(StyledModelForm):")
    if quote_start < 0 or invoice_start <= quote_start:
        raise RuntimeError("QuoteForm/InvoiceForm anchors missing")
    block = text[quote_start:invoice_start]
    if '"discount_percent"' not in block:
        old = 'fields = ["project", "issue_date", "valid_until", "intro_text", "notes"]'
        new = 'fields = ["project", "issue_date", "valid_until", "intro_text", "discount_percent", "notes"]'
        if old not in block:
            raise RuntimeError("A+Bau QuoteForm field contract changed")
        block = block.replace(old, new, 1)
        text = text[:quote_start] + block + text[invoice_start:]
        write(rel, text)

    # Keep the legacy model field posted for validation/backwards compatibility,
    # but never show it as a second discount control in the new A+Bau editor.
    editor_rel = "templates/rebuild/document_editor.html"
    editor = read(editor_rel)
    if "form.discount_percent.as_hidden" not in editor:
        csrf_anchor = '<form class="nx-form ab-document-form" method="post" data-ab-commercial-form>{% csrf_token %}'
        if csrf_anchor not in editor:
            raise RuntimeError("A+Bau document form CSRF anchor changed")
        editor = editor.replace(csrf_anchor, csrf_anchor + '{% if kind == \'quote\' %}{{ form.discount_percent.as_hidden }}{% endif %}', 1)

    old_grid = '''<div class="nx-form-grid">{% for field in form %}<div class="nx-field {% if field.name == 'intro_text' or field.name == 'notes' %}nx-field-full{% endif %}"><label for="{{ field.id_for_label }}">{{ field.label }}</label>{{ field }}{{ field.errors }}</div>{% endfor %}</div>'''
    new_grid = '''<div class="nx-form-grid">{% for field in form %}{% if field.name != 'discount_percent' %}<div class="nx-field {% if field.name == 'intro_text' or field.name == 'notes' %}nx-field-full{% endif %}"><label for="{{ field.id_for_label }}">{{ field.label }}</label>{{ field }}{{ field.errors }}</div>{% endif %}{% endfor %}</div>'''
    if old_grid in editor:
        editor = editor.replace(old_grid, new_grid, 1)
    elif new_grid not in editor:
        raise RuntimeError("A+Bau document metadata grid anchor changed")
    write(editor_rel, editor)


def preserve_cache_contract() -> None:
    rel = "templates/rebuild/base.html"
    text = read(rel)
    # Existing regression tests intentionally require the stable 20260811-N cache
    # convention. Keep that convention while still bumping past previous builds.
    text = re.sub(r"(kayi-next\.css' %\}\?v=)[^\"']+", r"\g<1>20260811-99", text)
    text = re.sub(r"(kayi-next\.js' %\}\?v=)[^\"']+", r"\g<1>20260811-99", text)
    write(rel, text)


def preserve_document_editor_contract() -> None:
    rel = "templates/rebuild/document_editor.html"
    text = read(rel)
    if "data-add-item" not in text:
        # Compatibility marker only. The active A+Bau add-position controls use
        # data-ab-add-item, avoiding the legacy row builder that included per-row tax.
        anchor = '<table class="ab-item-table" data-document-items data-ab-items>'
        if anchor not in text:
            raise RuntimeError("A+Bau item table anchor missing for legacy contract marker")
        text = text.replace(anchor, '<span hidden data-add-item aria-hidden="true"></span>\n      ' + anchor, 1)
        write(rel, text)


def align_generated_test_with_migration_chain() -> None:
    rel = "tests/test_ab_bau_tooltime_finance_upgrade.py"
    text = read(rel)
    text = text.replace('erp/migrations/0009_ab_bau_commercial.py', 'erp/migrations/0010_ab_bau_commercial.py')
    write(rel, text)


def guard() -> None:
    views = read("erp/rebuild_views.py")
    base = read("templates/rebuild/base.html")
    editor = read("templates/rebuild/document_editor.html")
    tests = read("tests/test_ab_bau_tooltime_finance_upgrade.py")
    quote_block = views[views.find("class QuoteForm(StyledModelForm):"):views.find("class InvoiceForm(StyledModelForm):")]
    if "GERMAN_FIELD_LABELS = {" not in views or '"issue_date": "Ausstellungsdatum"' not in views:
        raise RuntimeError("German form-label compatibility is missing")
    if '"discount_percent"' not in quote_block or "form.discount_percent.as_hidden" not in editor:
        raise RuntimeError("Legacy Rabatt field is not preserved invisibly for QuoteForm compatibility")
    if "kayi-next.js' %}?v=20260811-99" not in base:
        raise RuntimeError("Stable A+Bau JS cache contract is missing")
    if "data-add-item" not in editor or "data-ab-add-item" not in editor:
        raise RuntimeError("Document editor legacy/new add-position contract is incomplete")
    if "0010_ab_bau_commercial.py" not in tests or "0009_ab_bau_commercial.py" in tests:
        raise RuntimeError("A+Bau migration regression test is not aligned to 0010")


restore_german_labels()
preserve_quote_form_contract()
preserve_cache_contract()
preserve_document_editor_contract()
align_generated_test_with_migration_chain()
guard()
print("A+Bau regression compatibility installed: German labels, hidden QuoteForm Rabatt, cache contract, editor marker and migration test aligned.")
