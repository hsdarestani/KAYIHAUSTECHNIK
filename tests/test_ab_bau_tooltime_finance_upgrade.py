from pathlib import Path
from django.test import SimpleTestCase

R = Path(__file__).resolve().parents[1]


class ABBauCommercialUpgradeTests(SimpleTestCase):
    def test_document_editor_uses_tooltime_style_commercial_fields(self):
        t = (R / "templates/rebuild/document_editor.html").read_text(encoding="utf-8")
        for marker in ("item_type", "item_purchase_price", "item_markup_percent", "item_service_model", "document_tax_code", "discount_value", "item_unit"):
            self.assertIn(marker, t)
        self.assertNotIn('name="item_tax"', t)
        self.assertIn("Alternativposition", t)
        self.assertIn("Eventualposition", t)

    def test_finance_dashboard_and_project_finance_exist(self):
        u = (R / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        v = (R / "erp/rebuild_views.py").read_text(encoding="utf-8")
        p = (R / "templates/rebuild/project_detail.html").read_text(encoding="utf-8")
        self.assertIn('path("finanzen/"', u)
        self.assertIn("def finance_dashboard", v)
        self.assertIn('data-tab="finance"', p)
        self.assertIn("_project_financials", v)

    def test_time_toggle_handles_non_json_without_json_parse_crash(self):
        js = (R / "static/js/kayi-next.js").read_text(encoding="utf-8")
        self.assertIn("const raw = await response.text()", js)
        self.assertIn("JSON.parse(raw)", js)
        self.assertIn("keine gültige Serverantwort", js)

    def test_brand_is_a_plus_bau_and_german(self):
        base = (R / "templates/rebuild/base.html").read_text(encoding="utf-8")
        self.assertIn("A+Bau", base)
        self.assertIn("ab-brand-logo-only", base)
        self.assertNotIn("Alles organisiert. Alles im Griff.", base)
        self.assertIn("Finanzen", base)
        self.assertNotIn(">KAYI<", base)

    def test_commercial_sidecar_models_are_installed(self):
        m = (R / "erp/ab_bau_commercial.py").read_text(encoding="utf-8")
        migration = (R / "erp/migrations/0010_ab_bau_commercial.py").read_text(encoding="utf-8")
        self.assertIn("class CommercialDocumentSettings", m)
        self.assertIn("class CommercialItemMeta", m)
        self.assertIn("purchase_price", migration)
