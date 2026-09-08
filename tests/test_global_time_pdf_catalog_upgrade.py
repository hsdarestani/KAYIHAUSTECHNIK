from pathlib import Path
from django.test import SimpleTestCase

R = Path(__file__).resolve().parents[1]


class GlobalTimePdfCatalogUpgradeTests(SimpleTestCase):
    def test_global_time_grid_is_ten_minutes(self):
        js = (R / "static/js/kayi-next.js").read_text(encoding="utf-8")
        self.assertIn("KAYI 10-MINUTE TIME GRID 2026-08-20", js)
        self.assertIn("STEP_SECONDS = 600", js)

    def test_document_positions_have_live_price_typeahead_and_three_sources(self):
        template = (R / "templates/rebuild/document_editor.html").read_text(encoding="utf-8")
        js = (R / "static/js/kayi-next.js").read_text(encoding="utf-8")
        for marker in ("data-live-catalog-family", "data-live-price-input", "Eigene / Privat-Preisliste", "Referenz / B&amp;O"):
            self.assertIn(marker, template)
        self.assertIn("KAYI DIRECT POSITION LIVE PRICING 2026-08-20", js)
        self.assertTrue((R / "erp/live_pricing_views.py").exists())

    def test_pdf_identity_helper_exists(self):
        helper = (R / "erp/services/business_pdf_identity.py").read_text(encoding="utf-8")
        for marker in ("Angebotsnummer", "Rechnungsnummer", "Steuernr.", "USt-IdNr.", "Geschäftsführung"):
            self.assertIn(marker, helper)
