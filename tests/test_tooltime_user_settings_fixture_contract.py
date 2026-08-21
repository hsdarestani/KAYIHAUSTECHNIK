import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ToolTimeUserSettingsFixtureContractTests(unittest.TestCase):
    def test_captured_values_are_fixture_backed(self):
        payload = json.loads((ROOT / "reference_data" / "tooltime_user_settings.json").read_text(encoding="utf-8"))
        cfg = payload["commercial_profile"]
        self.assertEqual(cfg["numbering"]["quote"], {"prefix": "A-", "start": 220})
        self.assertEqual(cfg["numbering"]["invoice"], {"prefix": "R-", "start": 145})
        self.assertEqual(cfg["numbering"]["credit"], {"prefix": "GS-2026", "start": 1000})
        self.assertEqual(cfg["communication"]["reply_email"], "info@kayi-haustechnik.de")
        self.assertTrue(cfg["layout"]["show_logo"])
        self.assertEqual(cfg["layout"]["logo_position"], "right")
        self.assertEqual(cfg["layout"]["logo_size"], "large")
        self.assertTrue(cfg["layout"]["show_footer"])
        self.assertEqual(cfg["payment_terms"]["mode"], "immediately")
        self.assertEqual(cfg["payment_terms"]["invoice_text"], "Zahlbar sofort ohne Abzug ab Rechnungsdatum.")
        self.assertTrue(cfg["quote_defaults"]["intro_text"].startswith("Herzlichen Dank für Ihre Anfrage"))
        self.assertIn("Widerrufsbelehrung", cfg["quote_defaults"]["closing_text"])
        self.assertIn("Auftragsbestätigung", cfg["quote_defaults"]["closing_text"])
        self.assertEqual(cfg["dunning"]["first"], {"days": 7, "fee": "3.00"})
        self.assertEqual(cfg["dunning"]["second"], {"days": 7, "fee": "3.00"})
        self.assertEqual(
            [row["label"] for row in cfg["appointments"]["types"]],
            ["Besichtigung", "Ausführung", "Beratung", "Abnahme", "Wartung", "Notfall", "Intern"],
        )

    def test_importer_targets_persisted_org_settings_and_preserves_edits(self):
        source = (ROOT / "scripts" / "tooltime_user_settings_import.py").read_text(encoding="utf-8")
        compile(source, str(ROOT / "scripts" / "tooltime_user_settings_import.py"), "exec")
        self.assertIn('profile.settings = merged', source)
        self.assertIn('merge_missing', source)
        self.assertIn('ToolTimeTextTemplate.objects.get_or_create', source)
        self.assertIn('Any non-empty tenant text', source)
        self.assertNotIn('templates/rebuild/tooltime_settings.html', source)

    def test_all_document_texts_are_database_seeded(self):
        payload = json.loads((ROOT / "reference_data" / "tooltime_user_settings.json").read_text(encoding="utf-8"))
        rows = {(row["document_kind"], row["text_kind"]): row for row in payload["text_templates"]}
        self.assertEqual(set(rows), {("quote", "intro"), ("quote", "closing"), ("invoice", "intro"), ("invoice", "closing")})
        self.assertTrue(rows[("quote", "intro")]["body"].startswith("Herzlichen Dank für Ihre Anfrage"))
        self.assertIn("Widerrufsbelehrung", rows[("quote", "closing")]["body"])
        self.assertEqual(rows[("invoice", "intro")]["body"], "nachfolgend berechnen wir Ihnen wie vorab besprochen:")
        self.assertTrue(rows[("invoice", "closing")]["body"].startswith("Vielen Dank für Ihren Auftrag!"))

    def test_production_deploy_applies_fixture_to_real_tenant(self):
        deploy = (ROOT / "deploy" / "server-deploy-ab-bau.sh").read_text(encoding="utf-8")
        self.assertIn("python3 scripts/tooltime_user_settings_import.py", deploy)
        self.assertIn("apply_tooltime_user_settings --organization 'A+Bau'", deploy)
        self.assertIn("dc run --rm web python manage.py migrate --noinput", (ROOT / "deploy" / "server-deploy.sh").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
