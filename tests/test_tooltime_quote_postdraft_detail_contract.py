from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimeQuotePostDraftDetailContractTests(SimpleTestCase):
    def test_quote_route_uses_workspace_dispatcher(self):
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        self.assertIn('tooltime_parity.quote_workspace, name="next-quote-edit"', urls)
        self.assertIn('def quote_workspace(request, pk):', views)
        self.assertIn('is_editable_draft', views)
        self.assertIn('return quote_editor(request, pk)', views)
        self.assertIn('rebuild/quote_detail.html', views)

    def test_postdraft_surface_is_document_not_editor(self):
        detail = (ROOT / "templates/rebuild/quote_detail.html").read_text(encoding="utf-8")
        for marker in ("PDF-Vorschau", "Positionen", "Zahlungsbedingungen", "Kunde & Projekt", "In Rechnung übernehmen", "Per E-Mail senden"):
            self.assertIn(marker, detail)
        self.assertNotIn('name="item_description"', detail)
        self.assertNotIn('tt-document-form', detail)

    def test_pdf_supports_dedicated_inline_preview_without_changing_download_contract(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        detail = (ROOT / "templates/rebuild/quote_detail.html").read_text(encoding="utf-8")
        self.assertIn('request.GET.get("preview")', views)
        self.assertIn('next-quote-preview', detail)
        self.assertNotIn("next-quote-pdf' quote.pk %}?preview=1", detail)
        self.assertIn('PDF herunterladen', detail)

    def test_financial_and_lifecycle_actions_remain_server_backed(self):
        detail = (ROOT / "templates/rebuild/quote_detail.html").read_text(encoding="utf-8")
        for route in ("next-quote-status", "next-quote-to-invoice", "next-quote-send-email", "next-quote-pdf"):
            self.assertIn(route, detail)
        for value in ("net", "tax", "gross", "payment_due_days", "early_percent"):
            self.assertIn(f'"{value}"', (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8"))
