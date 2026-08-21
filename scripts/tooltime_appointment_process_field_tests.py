from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME APPOINTMENT FIELD BRIDGE TESTS 2026-08-21"


def run(module) -> None:
    rel = "tests/test_field_authorization.py"
    text = module.read(rel)
    method = r'''
    def test_completion_updates_structured_appointment_services_without_price_leakage(self):
        from erp.models import AppointmentServiceGroup, AppointmentServiceItem, CatalogItem

        authorization = self.create_signed_auth()
        catalog = CatalogItem.objects.create(
            organization=self.org,
            code="FIELD-L-1",
            name="Montage vor Ort",
            description="Montageleistung",
            kind="service",
            unit="Std.",
            purchase_price=Decimal("40.00"),
            sales_price=Decimal("80.00"),
            tax_rate=Decimal("19.00"),
            active=True,
        )
        group = AppointmentServiceGroup.objects.create(
            organization=self.org, event=self.event, title="Geplante Leistungen", position=1
        )
        item = AppointmentServiceItem.objects.create(
            organization=self.org,
            event=self.event,
            group=group,
            catalog_item=catalog,
            position=1,
            kind="labour",
            code=catalog.code,
            description="Montage geplant",
            quantity=Decimal("1.000"),
            unit="Std.",
            purchase_price=Decimal("40.00"),
            unit_price=Decimal("80.00"),
            tax_rate=Decimal("19.00"),
        )
        payload = {
            "report_text": "Montage durchgeführt und geprüft.",
            "services": "Zusatznotiz zur Leistung",
            "material": "Kein Zusatzmaterial",
            "customer_reviewed": "1",
            "completion_signature_data": SIGNATURE,
            "document_service_id": [str(item.pk)],
            "document_service_kind": ["labour"],
            "document_service_quantity": ["2.5"],
            "document_service_unit": ["Std."],
            "document_service_description": ["Montage final durchgeführt"],
            "document_service_catalog_id": [str(catalog.pk)],
        }
        with patch("erp.field_authorization_views.html_to_pdf_bytes", return_value=b"%PDF-1.4 completion-services"):
            response = self.client.post(reverse("field-complete-job", args=[self.event.pk]), data=payload)
        self.assertEqual(response.status_code, 200, response.content)
        item.refresh_from_db()
        self.assertEqual(item.description, "Montage final durchgeführt")
        self.assertEqual(item.quantity, Decimal("2.500"))
        self.assertEqual(item.purchase_price, Decimal("40.00"))
        self.assertEqual(item.unit_price, Decimal("80.00"))
        completion = Document.objects.get(metadata__kind="field_completion", metadata__event_id=self.event.pk)
        self.assertEqual(completion.metadata["authorization_document_id"], authorization.pk)
        snapshot_items = completion.metadata["snapshot"]["service_items"]
        self.assertEqual(snapshot_items[0]["description"], "Montage final durchgeführt")
        self.assertEqual(snapshot_items[0]["quantity"], "2.500")

'''
    if "test_completion_updates_structured_appointment_services_without_price_leakage" not in text:
        anchor = "    def test_room_plan_preview_is_generated_from_same_saved_3d_revision(self):\n"
        if anchor not in text:
            raise RuntimeError("Appointment field bridge tests: insertion anchor fehlt")
        text = text.replace(anchor, method + anchor, 1)
    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")

    contract_rel = "tests/test_tooltime_appointment_field_bridge_contract.py"
    contract = r'''from pathlib import Path
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
'''
    module.write(contract_rel, contract)
    compile(contract, str(ROOT / contract_rel), "exec")
    print(f"{MARKER}: signed field completion persistence and no-price UI contract are covered.")
