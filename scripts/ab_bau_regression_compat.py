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
    if "GERMAN_FIELD_LABELS = {" not in views or '"issue_date": "Ausstellungsdatum"' not in views:
        raise RuntimeError("German form-label compatibility is missing")
    if "kayi-next.js' %}?v=20260811-99" not in base:
        raise RuntimeError("Stable A+Bau JS cache contract is missing")
    if "data-add-item" not in editor or "data-ab-add-item" not in editor:
        raise RuntimeError("Document editor legacy/new add-position contract is incomplete")
    if "0010_ab_bau_commercial.py" not in tests or "0009_ab_bau_commercial.py" in tests:
        raise RuntimeError("A+Bau migration regression test is not aligned to 0010")


restore_german_labels()
preserve_cache_contract()
preserve_document_editor_contract()
align_generated_test_with_migration_chain()
guard()
print("A+Bau regression compatibility installed: German labels, cache contract, editor marker and migration test aligned.")
