from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimeDocumentWorkspaceFinalContractTests(SimpleTestCase):
    def test_dedicated_inline_preview_routes_exist(self):
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        self.assertIn('name="next-quote-preview"', urls)
        self.assertIn('name="next-invoice-preview"', urls)
        self.assertIn('def quote_preview(request, pk):', views)
        self.assertIn('def invoice_preview(request, pk):', views)
        self.assertIn('@xframe_options_sameorigin', views)
        self.assertIn('Content-Disposition"] = f\'inline;', views)

    def test_quote_detail_uses_preview_endpoint_not_download_query_hack(self):
        detail = (ROOT / "templates/rebuild/quote_detail.html").read_text(encoding="utf-8")
        self.assertIn("next-quote-preview", detail)
        self.assertNotIn("next-quote-pdf' quote.pk %}?preview=1", detail)

    def test_invoice_route_dispatches_draft_vs_finalized(self):
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        self.assertIn('tooltime_parity.invoice_workspace, name="next-invoice-edit"', urls)
        self.assertIn('compliance_state == "draft"', views)
        self.assertIn('return invoice_editor(request, pk)', views)
        self.assertIn('rebuild/invoice_detail.html', views)

    def test_final_invoice_is_document_workspace_not_editor(self):
        detail = (ROOT / "templates/rebuild/invoice_detail.html").read_text(encoding="utf-8")
        for phrase in ("Offener Betrag", "Finale Rechnung", "Kunde & Projekt", "Rechnungsdetails", "Zahlung erfassen", "Rechnung senden"):
            self.assertIn(phrase, detail)
        for route in ("next-invoice-preview", "invoice-compliance-pdf", "next-invoice-payment", "next-invoice-send-email"):
            self.assertIn(route, detail)
        self.assertNotIn('name="item_description"', detail)
        self.assertNotIn('tt-document-form', detail)

    def test_invoice_draft_editor_gets_tooltime_presentation_without_replacing_fields(self):
        editor = (ROOT / "templates/rebuild/document_editor.html").read_text(encoding="utf-8")
        css = (ROOT / "static/css/tooltime-document-workspace.css").read_text(encoding="utf-8")
        self.assertIn("tti-invoice-draft-form", editor)
        self.assertIn("tooltime-document-workspace.css", editor)
        self.assertIn(".tti-invoice-draft-form", css)
        self.assertIn(".ttdw-layout", css)
