import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_tooltime_user_settings_are_fixture_backed_and_edit_safe():
    fixture = ROOT / "erp" / "fixtures" / "tooltime_user_settings.json"
    command = ROOT / "erp" / "management" / "commands" / "apply_tooltime_user_settings.py"
    assert fixture.exists()
    assert command.exists()
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    cfg = payload["commercial_profile"]
    assert cfg["numbering"]["invoice"] == {"prefix": "R-", "start": 145}
    assert cfg["numbering"]["quote"] == {"prefix": "A-", "start": 220}
    assert cfg["quote_defaults"]["intro_text"].startswith("Herzlichen Dank für Ihre Anfrage")
    assert cfg["invoice_defaults"]["payment_text"] == "Zahlbar sofort ohne Abzug ab Rechnungsdatum."
    source = command.read_text(encoding="utf-8")
    assert "merge_missing" in source
    assert "profile.settings = merged" in source
    assert "ToolTimeTextTemplate.objects.get_or_create" in source
    assert "Any non-empty tenant text" in source


def test_all_four_standard_text_templates_are_seeded():
    payload = json.loads((ROOT / "erp" / "fixtures" / "tooltime_user_settings.json").read_text(encoding="utf-8"))
    rows = {(row["document_kind"], row["text_kind"]): row for row in payload["text_templates"]}
    assert set(rows) == {("quote", "intro"), ("quote", "closing"), ("invoice", "intro"), ("invoice", "closing")}
    assert rows[("quote", "intro")]["body"].startswith("Herzlichen Dank für Ihre Anfrage")
    assert "Widerrufsbelehrung" in rows[("quote", "closing")]["body"]
    assert "Auftragsbestätigung" in rows[("quote", "closing")]["body"]
    assert rows[("invoice", "intro")]["body"] == "nachfolgend berechnen wir Ihnen wie vorab besprochen:"
    assert rows[("invoice", "closing")]["body"].startswith("Vielen Dank für Ihren Auftrag!")
