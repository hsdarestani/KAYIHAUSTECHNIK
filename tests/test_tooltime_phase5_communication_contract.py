from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase5CommunicationContractTests(SimpleTestCase):
    def test_delivery_model_and_migration_are_persistent(self):
        models = (ROOT / "erp/tooltime_parity_finance.py").read_text(encoding="utf-8")
        migration = (ROOT / "erp/migrations/0017_tooltime_phase5_communication.py").read_text(encoding="utf-8")
        self.assertIn("class ToolTimeDocumentDelivery", models)
        self.assertIn('("erp", "0016_tooltime_phase3_editor")', migration)
        self.assertIn('status = models.CharField', models)
        self.assertIn('error_message = models.CharField', models)

    def test_pdf_preview_exists_but_real_email_is_post_finalization_only(self):
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        for name in ("next-quote-pdf", "next-quote-send-email", "next-invoice-send-email"):
            self.assertIn(f'name="{name}"', urls)
        self.assertIn("Angebote können erst nach dem Fertigstellen versendet werden.", views)
        self.assertIn("Der Versand ist erst nach dem Fertigstellen des Angebots verfügbar.", views)
        self.assertIn("_phase5_quote_pdf_bytes(quote, require_finalized=False)", views)
        self.assertIn("HttpResponse(payload, content_type=\"application/pdf\")", views)
        self.assertIn("ENTWURF · Angebotsvorschau", views)
        self.assertIn("Steuernummer/USt.-ID:", views)
        self.assertIn("Dokumenthinweis:", views)
        self.assertIn("Kundennummer:", views)
        self.assertIn("Preisgrundlage:", views)

    def test_invoice_email_uses_canonical_frozen_pdf(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        self.assertIn("compliance.original_pdf_document", views)
        self.assertIn("original_pdf_document_id", views)
        self.assertIn('"invoice.emailed"', views)
        self.assertNotIn("_phase5_quote_pdf_bytes(document)\n        pdf_document = compliance", views)

    def test_fake_mail_backends_cannot_record_success(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        for backend in ("console", "locmem", "dummy", "filebased"):
            self.assertIn(f'"{backend}"', views)
        self.assertIn("message.send(fail_silently=False)", views)
        self.assertIn('delivery.status = "sent"', views)
        self.assertIn("Es wurde kein Versandserfolg gespeichert", views)

    def test_german_communication_ui_is_real(self):
        partial = (ROOT / "templates/rebuild/_tooltime_communication.html").read_text(encoding="utf-8")
        editor = (ROOT / "templates/rebuild/document_editor.html").read_text(encoding="utf-8")
        js = (ROOT / "static/js/tooltime-parity-communication.js").read_text(encoding="utf-8")
        for phrase in ("PDF & Versand", "Per E-Mail senden", "Empfänger", "Betreff", "E-Mail jetzt senden", "Versandverlauf"):
            self.assertIn(phrase, partial)
        self.assertIn("_tooltime_communication.html", editor)
        self.assertIn("data-document-email-open", partial)
        self.assertIn("data-document-email-modal", js)
