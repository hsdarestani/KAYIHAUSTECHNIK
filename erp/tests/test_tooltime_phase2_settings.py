from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[2]


class ToolTimePhase2SourceContractTests(SimpleTestCase):
    def test_phase2_settings_are_real_and_german(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text()
        template = (ROOT / "templates/rebuild/tooltime_settings.html").read_text()
        service = (ROOT / "erp/services/tooltime_parity_finance.py").read_text()
        for needle in ("_phase2_number_preview", "_assign_datev_accounts", "_import_datev_csv", "phase2_legal_documents", "phase2_documents", "phase2_tax"):
            self.assertIn(needle, views)
        for needle in ("Nächste Angebotsnummer", "Nächste Rechnungsnummer", "Debitoren- und Kreditorennummern", "Aus DATEV importieren", "Standardmäßig an Angebote anhängen", "E-Mail-Benachrichtigung senden", "Benutzerdefiniert", "DATEV-Konto SKR 03"):
            self.assertIn(needle, template)
        self.assertIn("default_legal_attachment_ids", service)
        self.assertIn("quote_default", service)

    def test_datev_model_and_migration_exist(self):
        models = (ROOT / "erp/tooltime_parity_finance.py").read_text()
        migration = ROOT / "erp/migrations/0015_tooltime_phase2_settings.py"
        self.assertIn("class ToolTimeDatevAccount", models)
        self.assertTrue(migration.exists())
        self.assertIn("default_attachment_ids", migration.read_text())
