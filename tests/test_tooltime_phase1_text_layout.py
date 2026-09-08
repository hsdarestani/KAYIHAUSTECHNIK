from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase1TextLayoutContractTests(SimpleTestCase):
    def test_phase1_routes_and_real_crud_exist(self):
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        for needle in ("next-text-template-create", "next-text-template-update", "next-text-template-delete", "next-text-template-standard", "next-text-template-move", "next-layout-preview"):
            self.assertIn(needle, urls)
        for needle in ("def text_template_create", "def text_template_update", "def text_template_delete", "Die Standardvorlage kann nicht gelöscht werden", "def layout_preview"):
            self.assertIn(needle, views)

    def test_phase1_settings_contains_tooltime_template_manager(self):
        template = (ROOT / "templates/rebuild/tooltime_settings.html").read_text(encoding="utf-8")
        for needle in ("Textvorlagen", "Neue Vorlage", "Als Standard festlegen", "Dokumentvorschau", "data-tooltime-text-template-manager"):
            self.assertIn(needle, template)

    def test_phase1_document_editor_can_apply_templates(self):
        template = (ROOT / "templates/rebuild/document_editor.html").read_text(encoding="utf-8")
        self.assertIn("data-template-library", template)
        self.assertIn("tt.templates", template)
        self.assertIn("document_salutation", template)
        self.assertIn("closing_text", template)

    def test_phase1_layout_contract_survives(self):
        completion = (ROOT / "scripts/tooltime_parity_finance_completion.py").read_text(encoding="utf-8")
        # Existing completion layer owns upload validation and custom footer persistence.
        for needle in ("logo_file", "letterhead_file", "footer_heading_", "footer_lines_", "footer_align_"):
            self.assertIn(needle, completion)
