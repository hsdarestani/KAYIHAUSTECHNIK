from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ABV3CatalogueTextLayoutParityTests(unittest.TestCase):
    def test_catalogue_editor_keeps_real_persisted_fields(self):
        html = (ROOT / "templates/rebuild/catalogue_edit.html").read_text(encoding="utf-8")
        self.assertIn("data-ab-v3-catalogue-editor", html)
        for name in ("code", "type", "name", "description", "unit", "tax_rate", "purchase_price", "sales_price"):
            self.assertIn(f'name="{name}"', html)
        for marker in ("data-ab-quantity", "data-ab-markup", "data-ab-markup-value", "data-ab-total"):
            self.assertIn(marker, html)

    def test_text_layout_keeps_complete_manager_without_legacy_duplicate(self):
        html = (ROOT / "templates/rebuild/tooltime_settings.html").read_text(encoding="utf-8")
        self.assertIn("data-ab-v3-layout-form", html)
        self.assertIn("data-ab-v3-layout-preview", html)
        self.assertIn("data-tooltime-text-template-manager", html)
        self.assertNotIn('<div class="tt-template-settings">', html)
        for name in ("logo_show", "logo_position", "logo_size", "sender_line_show", "footer_show", "footer_mode"):
            self.assertIn(f'name="{name}"', html)

    def test_parity_assets_are_installed(self):
        css = (ROOT / "static/css/ab-v3-catalogue-text-layout.css").read_text(encoding="utf-8")
        js = (ROOT / "static/js/ab-v3-catalogue-text-layout.js").read_text(encoding="utf-8")
        self.assertIn("A+BAU V3 CATALOGUE + TEXT LAYOUT PARITY", css)
        self.assertIn("data-ab-v3-article-form", js)
        self.assertIn("data-ab-v3-layout-form", js)


if __name__ == "__main__":
    unittest.main()
