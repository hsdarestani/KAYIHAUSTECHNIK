from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimeAppointmentFieldBridgeContractTests(SimpleTestCase):
    def test_real_field_completion_is_connected_to_structured_appointment_services(self):
        views = (ROOT / "erp/field_authorization_views.py").read_text(encoding="utf-8")
        template = (ROOT / "templates/rebuild/appointment_detail.html").read_text(encoding="utf-8")
        for marker in (
            "_appointment_apply_field_services(event, request)",
            '"service_items": _appointment_service_snapshot(event)',
            '"service_groups": event.service_groups.prefetch_related',
            '"appointment_catalog": m.CatalogItem.objects.filter',
        ):
            self.assertIn(marker, views)
        for marker in (
            "data-field-services",
            'name="document_service_quantity"',
            'name="document_service_unit"',
            'name="document_service_description"',
            "Preise werden vor Ort nicht angezeigt",
        ):
            self.assertIn(marker, template)
        self.assertNotIn("Einkaufspreis", template)
        self.assertNotIn("Verkaufspreis", template)
