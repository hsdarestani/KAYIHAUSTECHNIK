from __future__ import annotations

from copy import deepcopy

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import Client, TestCase
from django.urls import reverse

from erp.models import CalendarEvent, Customer, Document, Employee, Organization, Project, UserProfile
from erp.services.numbering import next_number


class ManagerReviewTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="A+Bau Review")
        self.admin = User.objects.create_user("review-admin", password="secure-pass")
        self.admin.profile.organization = self.org
        self.admin.profile.role = UserProfile.Role.ADMIN
        self.admin.profile.save()
        self.admin_employee = Employee.objects.create(organization=self.org, user=self.admin, employee_number="RV-001", first_name="Rita", last_name="Review")
        self.tech = User.objects.create_user("review-tech", password="secure-pass")
        self.tech.profile.organization = self.org
        self.tech.profile.role = UserProfile.Role.TECHNICIAN
        self.tech.profile.is_mobile_worker = True
        self.tech.profile.save()
        self.tech_employee = Employee.objects.create(organization=self.org, user=self.tech, employee_number="RV-002", first_name="Tom", last_name="Technik")
        self.customer = Customer.objects.create(organization=self.org, number=next_number(self.org, "customer"), company="Prüfkunde GmbH")
        self.project = Project.objects.create(organization=self.org, number=next_number(self.org, "project"), title="Vor-Ort Reparatur", customer=self.customer, manager=self.admin_employee, status="review")
        self.event = CalendarEvent.objects.create(organization=self.org, project=self.project, title="Reparatur", type="site", starts_at="2026-08-10T10:00:00+00:00", ends_at="2026-08-10T11:00:00+00:00", created_by=self.admin)
        self.event.attendees.add(self.tech_employee)
        self.authorization = Document(
            organization=self.org,
            project=self.project,
            customer=self.customer,
            uploaded_by=self.tech,
            title="Auftragsfreigabe",
            category="contract",
            mime_type="application/pdf",
            size=8,
            metadata={
                "kind": "field_authorization",
                "event_id": self.event.pk,
                "status": "signed",
                "snapshot_sha256": "a" * 64,
                "snapshot": {
                    "pricing_mode": "fixed",
                    "issue": "Heizkörper bleibt kalt",
                    "scope": "Thermostatventil prüfen und ersetzen",
                    "items": [
                        {"description": "Thermostatventil", "quantity": "1.00", "unit": "Stk.", "unit_price": "120.00", "tax_rate": "19.00", "net": "120.00", "tax": "22.80", "gross": "142.80"},
                        {"description": "Funktionsprüfung", "quantity": "1.00", "unit": "Psch.", "unit_price": "45.00", "tax_rate": "19.00", "net": "45.00", "tax": "8.55", "gross": "53.55"},
                    ],
                    "totals": {"net": "165.00", "tax": "31.35", "gross": "196.35"},
                },
            },
        )
        self.authorization.file.save("authorization.pdf", ContentFile(b"%PDF-1.4"), save=False)
        self.authorization.save()
        self.completion = Document(
            organization=self.org,
            project=self.project,
            customer=self.customer,
            uploaded_by=self.tech,
            title="Einsatzabschluss",
            category="report",
            mime_type="application/pdf",
            size=8,
            metadata={
                "kind": "field_completion",
                "event_id": self.event.pk,
                "status": "pending_review",
                "billing_ready": False,
                "snapshot_sha256": "b" * 64,
                "snapshot": {"report": "Ventil ersetzt.", "services": "Thermostatventil ersetzt; Funktion geprüft", "material": "1 Thermostatventil"},
            },
        )
        self.completion.file.save("completion.pdf", ContentFile(b"%PDF-1.4"), save=False)
        self.completion.save()
        self.before_photo = Document(organization=self.org, project=self.project, customer=self.customer, uploaded_by=self.tech, title="Vorher", category="photo", mime_type="image/png", size=4, metadata={"event_id": self.event.pk, "phase": "before"})
        self.before_photo.file.save("before.png", ContentFile(b"PNG1"), save=False); self.before_photo.save()
        self.after_photo = Document(organization=self.org, project=self.project, customer=self.customer, uploaded_by=self.tech, title="Nachher", category="photo", mime_type="image/png", size=4, metadata={"event_id": self.event.pk, "phase": "after"})
        self.after_photo.file.save("after.png", ContentFile(b"PNG2"), save=False); self.after_photo.save()
        self.client = Client()

    def test_office_sees_pending_and_opens_full_editor(self):
        self.client.login(username="review-admin", password="secure-pass")
        response = self.client.get(reverse("field-review-queue"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Prüfen & bearbeiten")
        response = self.client.get(reverse("field-review-detail", args=[self.completion.pk]))
        self.assertEqual(response.status_code, 200)
        for needle in ("Abrechnungspositionen", "Einkauf €", "Aufschlag %", "Verkauf €", "Nachweise & Fotos", "Vorher", "Nachher"):
            self.assertContains(response, needle)

    def test_office_can_edit_positions_and_approve_without_changing_signed_original(self):
        self.client.login(username="review-admin", password="secure-pass")
        original_snapshot = deepcopy(self.authorization.metadata["snapshot"])
        response = self.client.post(reverse("field-review-detail", args=[self.completion.pk]), {
            "action": "approve",
            "report": "Bürobericht geprüft.",
            "services": "Ventil ersetzt und Anlage geprüft.",
            "material": "1 Thermostatventil",
            "item_description": ["Thermostatventil", "Anfahrt"],
            "item_quantity": ["1", "1"],
            "item_unit": ["Stk.", "Psch."],
            "item_position_type": ["material", "other"],
            "item_purchase_price": ["70", "0"],
            "item_markup_percent": ["71.43", "0"],
            "item_price": ["120", "35"],
            "item_tax": ["19", "19"],
            "note": "Geprüft.",
        })
        self.assertEqual(response.status_code, 302)
        self.completion.refresh_from_db(); self.authorization.refresh_from_db()
        self.assertEqual(self.completion.metadata["status"], "approved")
        self.assertTrue(self.completion.metadata["billing_ready"])
        review = self.completion.metadata["billing_review"]
        self.assertEqual(len(review["items"]), 2)
        self.assertEqual(review["items"][1]["description"], "Anfahrt")
        self.assertEqual(review["totals"]["net"], "155.00")
        self.assertEqual(review["totals"]["cost"], "70.00")
        self.assertEqual(self.authorization.metadata["snapshot"], original_snapshot)
        self.assertEqual(self.completion.metadata["snapshot"]["report"], "Ventil ersetzt.")

    def test_saving_after_approval_reopens_billing_until_approved_again(self):
        self.client.login(username="review-admin", password="secure-pass")
        self.completion.metadata = {**self.completion.metadata, "status": "approved", "billing_ready": True}
        self.completion.save(update_fields=["metadata", "updated_at"])
        response = self.client.post(reverse("field-review-detail", args=[self.completion.pk]), {
            "action": "save",
            "report": "Noch einmal geprüft",
            "services": "Ventil ersetzt",
            "material": "1 Ventil",
            "item_description": ["Thermostatventil"],
            "item_quantity": ["1"],
            "item_unit": ["Stk."],
            "item_position_type": ["material"],
            "item_purchase_price": ["70"],
            "item_markup_percent": ["71.43"],
            "item_price": ["120"],
            "item_tax": ["19"],
        })
        self.assertEqual(response.status_code, 302)
        self.completion.refresh_from_db()
        self.assertEqual(self.completion.metadata["status"], "pending_review")
        self.assertFalse(self.completion.metadata["billing_ready"])

    def test_office_can_still_return_only_when_technician_input_is_needed(self):
        self.client.login(username="review-admin", password="secure-pass")
        response = self.client.post(reverse("field-review-detail", args=[self.completion.pk]), {
            "action": "return",
            "note": "Bitte Nachher-Foto ergänzen.",
            "report": "Ventil ersetzt",
            "services": "Ventil ersetzt",
            "material": "1 Ventil",
            "item_description": ["Thermostatventil"],
            "item_quantity": ["1"],
            "item_unit": ["Stk."],
            "item_position_type": ["material"],
            "item_purchase_price": ["70"],
            "item_markup_percent": ["71.43"],
            "item_price": ["120"],
            "item_tax": ["19"],
        })
        self.assertEqual(response.status_code, 302)
        self.completion.refresh_from_db()
        self.assertEqual(self.completion.metadata["status"], "changes_requested")
        self.assertFalse(self.completion.metadata["billing_ready"])
        self.assertEqual(self.completion.metadata["review_note"], "Bitte Nachher-Foto ergänzen.")
        self.assertIn("billing_review", self.completion.metadata)

    def test_technician_cannot_review_or_edit(self):
        self.client.login(username="review-tech", password="secure-pass")
        self.assertEqual(self.client.get(reverse("field-review-queue")).status_code, 403)
        self.assertEqual(self.client.get(reverse("field-review-detail", args=[self.completion.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("field-review-approve", args=[self.completion.pk])).status_code, 403)

    def test_completion_contract_routes_new_jobs_to_review(self):
        from pathlib import Path
        field = Path("erp/field_authorization_views.py").read_text(encoding="utf-8")
        template = Path("templates/rebuild/appointment_detail.html").read_text(encoding="utf-8")
        self.assertIn('"status": "pending_review"', field)
        self.assertIn('"billing_ready": False', field)
        self.assertIn("Wartet auf Bürofreigabe", template)
        self.assertIn("Änderung angefordert", template)
