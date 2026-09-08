from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase3EditorContractTests(SimpleTestCase):
    def test_phase3_models_and_migration_are_installed(self):
        finance = (ROOT / "erp/tooltime_parity_finance.py").read_text(encoding="utf-8")
        commercial = (ROOT / "erp/ab_bau_commercial.py").read_text(encoding="utf-8")
        migration = (ROOT / "erp/migrations/0016_tooltime_phase3_editor.py").read_text(encoding="utf-8")
        self.assertIn("customer = models.ForeignKey", finance)
        self.assertIn("class ToolTimeMixedSubitem", finance)
        self.assertIn("show_subitems_in_pdf", commercial)
        self.assertIn("ToolTimeMixedSubitem", migration)

    def test_editor_has_real_customer_project_and_mixed_position_controls(self):
        editor = (ROOT / "templates/rebuild/document_editor.html").read_text(encoding="utf-8")
        position = (ROOT / "templates/rebuild/_tooltime_position.html").read_text(encoding="utf-8")
        self.assertIn('name="customer_id"', editor)
        self.assertIn("Kein Projekt · nur Kunde", editor)
        self.assertIn('data-group-action="copy"', editor)
        self.assertIn("In Rechnung übernehmen", editor)
        self.assertIn('name="item_subitems_json"', position)
        self.assertIn('name="item_sales_price"', position)
        self.assertNotIn('name="item_quantity" type="number" min="0"', position)

    def test_editor_runtime_routes_and_persistence_exist(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        service = (ROOT / "erp/services/tooltime_parity_finance.py").read_text(encoding="utf-8")
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        rebuild = (ROOT / "erp/rebuild_views.py").read_text(encoding="utf-8")
        self.assertIn("def _phase3_prepare_direct_customer", views)
        self.assertIn("def quote_status", views)
        self.assertIn("def quote_to_invoice", views)
        self.assertIn("next-quote-to-invoice", urls)
        self.assertIn("meta.customer =", service)
        self.assertIn("m.ToolTimeMixedSubitem.objects.create", rebuild)
        self.assertIn("quantity = _money", rebuild)
