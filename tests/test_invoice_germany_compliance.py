from pathlib import Path
from django.test import SimpleTestCase

R = Path(__file__).resolve().parents[1]


class GermanInvoiceComplianceAssemblyTests(SimpleTestCase):
    def test_sidecar_models_cover_numbering_freeze_audit_retention(self):
        text = (R / "erp/invoice_compliance.py").read_text(encoding="utf-8")
        for marker in ("InvoiceNumberSequence", "InvoiceComplianceRecord", "InvoiceAuditEvent", "snapshot_sha256", "retention_until", "original_pdf_document", "original_xml_document"):
            self.assertIn(marker, text)

    def test_invoice_number_is_only_allocated_by_finalize_service(self):
        views = (R / "erp/rebuild_views.py").read_text(encoding="utf-8")
        service = (R / "erp/services/invoice_compliance_service.py").read_text(encoding="utf-8")
        invoice_block = views[views.index("def invoice_editor"):views.index("def invoice_payment")]
        self.assertNotIn('_unique_number(m.Invoice', invoice_block)
        self.assertIn("allocate_number(invoice)", service)
        self.assertIn("select_for_update", service)

    def test_finalized_invoice_is_immutable_in_editor(self):
        views = (R / "erp/rebuild_views.py").read_text(encoding="utf-8")
        self.assertIn("Finalisierte Rechnungen sind unveränderbar", views)
        self.assertIn("is_finalized(invoice)", views)

    def test_mandatory_invoice_fields_are_backend_validated(self):
        service = (R / "erp/services/invoice_compliance_service.py").read_text(encoding="utf-8")
        for marker in ("Leistungserbringers", "Leistungsempfängers", "Steuernummer oder USt-IdNr.", "Ausstellungsdatum", "Leistungsdatum", "Steuersatz", "Fälligkeitsdatum"):
            self.assertIn(marker, service)

    def test_xrechnung_is_structured_and_never_self_declared_valid(self):
        service = (R / "erp/services/invoice_compliance_service.py").read_text(encoding="utf-8")
        self.assertIn("XRECHNUNG_CUSTOMIZATION_ID", service)
        self.assertIn("XRECHNUNG_VALIDATOR_URL", service)
        self.assertIn('"not_validated"', service)
        self.assertIn("HTTPError", service)
        self.assertNotIn('return {"status": "valid"', service.split("def validate_xrechnung",1)[1].split("def _transition_end",1)[0].split("if not url:",1)[0])

    def test_invoice_ui_has_real_finalize_not_send_bypass(self):
        template = (R / "templates/rebuild/document_editor.html").read_text(encoding="utf-8")
        self.assertIn('value="finalize"', template)
        self.assertIn("Korrektur erstellen", template)
        self.assertIn("Storno erstellen", template)
        self.assertIn("Original-PDF", template)

    def test_compliance_settings_expose_legal_company_data(self):
        template = (R / "templates/rebuild/invoice_compliance_settings.html").read_text(encoding="utf-8")
        for marker in ("Steuernummer", "USt-IdNr.", "Registergericht", "Geschäftsführer", "IBAN", "Rechnungsnummer Prefix"):
            self.assertIn(marker, template)
