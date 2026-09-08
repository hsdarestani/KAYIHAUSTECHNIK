from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimeAppointmentProcessParityContractTests(SimpleTestCase):
    def test_tooltime_appointment_process_contract_is_present(self):
        models = (ROOT / "erp/models.py").read_text(encoding="utf-8")
        views = (ROOT / "erp/rebuild_views.py").read_text(encoding="utf-8")
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        form = (ROOT / "templates/rebuild/appointment_form.html").read_text(encoding="utf-8")
        detail = (ROOT / "templates/rebuild/appointment_detail.html").read_text(encoding="utf-8")
        editor = (ROOT / "templates/rebuild/document_editor.html").read_text(encoding="utf-8")
        for marker in (
            "class AppointmentServiceGroup", "class AppointmentServiceItem",
            "source_quote = models.ForeignKey", "source_event = models.ForeignKey",
            "work_report = models.TextField",
        ):
            self.assertIn(marker, models)
        for marker in (
            "def appointment_from_quote", "def appointment_to_quote", "def appointment_to_invoice",
            "_appointment_copy_services_to_document", "_appointment_apply_field_services",
        ):
            self.assertIn(marker, views)
        for marker in ("next-quote-to-appointment", "next-appointment-to-quote", "next-appointment-to-invoice"):
            self.assertIn(marker, urls)
        for marker in (
            "Terminname", "Mitarbeiter hinzufügen", "Leistungsgruppe hinzufügen", "Position hinzufügen",
            'name="work_report"', "service_purchase_price", "service_unit_price",
        ):
            self.assertIn(marker, form)
        for marker in ("Angebot erstellen", "Rechnung erstellen", "document_service_quantity"):
            self.assertIn(marker, detail)
        self.assertNotIn("Verkaufspreis", detail)
        self.assertIn("data-quote-to-appointment", editor)
