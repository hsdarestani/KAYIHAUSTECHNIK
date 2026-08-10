from __future__ import annotations

import base64
import shutil
import tempfile
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import resolve, reverse

from erp.models import CalendarEvent, Customer, Document, Employee, Organization, Project, RoomMeasurement, RoomModelRevision, TimeEntry, UserProfile
from erp.services.numbering import next_number


PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6n4sAAAAASUVORK5CYII=")
SIGNATURE = "data:image/png;base64," + base64.b64encode(PNG + b"signature-padding-for-kayi-field-authorization").decode("ascii")


class FieldAuthorizationTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix="kayi-field-auth-")
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        self.org = Organization.objects.create(name="KAYI Field Authorization")
        self.user = User.objects.create_user("field-admin", password="secure-pass", email="field@example.com", first_name="Fiona", last_name="Feld")
        self.user.profile.organization = self.org
        self.user.profile.role = UserProfile.Role.ADMIN
        self.user.profile.save()
        self.employee = Employee.objects.create(organization=self.org, user=self.user, employee_number="FA-001", first_name="Fiona", last_name="Feld", email=self.user.email)
        self.customer = Customer.objects.create(organization=self.org, number=next_number(self.org, "customer"), company="Musterkunde GmbH", mobile="01710000000", street="Testweg 1", postal_code="60311", city="Frankfurt")
        self.project = Project.objects.create(organization=self.org, number=next_number(self.org, "project"), title="Heizkörper Reparatur", customer=self.customer, manager=self.employee, status="confirmed")
        self.project.members.add(self.employee)
        self.event = CalendarEvent.objects.create(organization=self.org, project=self.project, title="Heizkörper prüfen", type="site", starts_at="2026-08-10T10:00:00+00:00", ends_at="2026-08-10T12:00:00+00:00", location="Testweg 1, Frankfurt", notes="Heizkörper bleibt kalt", created_by=self.user)
        self.event.attendees.add(self.employee)
        self.measurement = RoomMeasurement.objects.create(organization=self.org, project=self.project, name="Wohnzimmer", method="manual", status="review", length_m=Decimal("4.0"), width_m=Decimal("3.2"), height_m=Decimal("2.6"), created_by=self.user)
        self.revision = RoomModelRevision.objects.create(organization=self.org, project=self.project, measurement=self.measurement, revision=1, label="Vor Arbeit", state={"schema_version": 3, "room": {"length_m": "4.000", "width_m": "3.200", "height_m": "2.600", "wall_thickness_m": "0.120"}, "openings": [], "objects": [{"id": "rad", "kind": "radiator", "label": "Heizkörper", "x_m": "0.2", "z_m": "1.5", "width_m": "0.9", "depth_m": "0.12", "height_m": "0.75", "enabled": True}]}, created_by=self.user)
        self.client = Client(); self.client.login(username="field-admin", password="secure-pass")

    def tearDown(self):
        self.override.disable(); shutil.rmtree(self.media_root, ignore_errors=True)

    def auth_post(self, *, before_photo=False):
        data = {
            "issue": "Heizkörper bleibt kalt; Thermostat reagiert nicht.",
            "scope": "Thermostatventil prüfen und bei Defekt ersetzen; Anlage entlüften und Funktion prüfen.",
            "pricing_mode": "fixed",
            "item_description": ["Thermostatventil ersetzen", "Funktionsprüfung"],
            "item_quantity": ["1", "1"],
            "item_unit": ["Stk.", "Psch."],
            "item_price": ["120.00", "45.00"],
            "item_tax": ["19", "19"],
            "room_revision_id": str(self.revision.pk),
            "signer_name": "Max Mustermann",
            "signature_data": SIGNATURE,
            "consent": "on",
        }
        if before_photo:
            data["before_photos"] = SimpleUploadedFile("vorher.png", PNG, content_type="image/png")
        return data

    def create_signed_auth(self):
        with patch("erp.field_authorization_views.html_to_pdf_bytes", return_value=b"%PDF-1.4 signed-auth"):
            response = self.client.post(reverse("field-authorization-sign", args=[self.event.pk]), data=self.auth_post(before_photo=True))
        self.assertEqual(response.status_code, 200, response.content)
        return Document.objects.get(metadata__kind="field_authorization", metadata__event_id=self.event.pk)

    def test_primary_appointment_and_time_routes_are_replaced(self):
        detail = reverse("next-appointment-detail", args=[self.event.pk])
        time = reverse("next-time-toggle", args=[self.event.pk])
        self.assertEqual(resolve(detail).func.__name__, "field_job_detail")
        self.assertEqual(resolve(time).func.__name__, "gated_time_toggle")
        self.assertEqual(reverse("field-quick-job"), "/field/jobs/new/")

    def test_field_page_keeps_flow_simple_and_locks_start_before_signature(self):
        response = self.client.get(reverse("next-appointment-detail", args=[self.event.pk]))
        self.assertContains(response, "Auftrag aufnehmen & freigeben")
        self.assertContains(response, "Vorher-Fotos & Raum")
        self.assertContains(response, "Kundenfreigabe")
        self.assertContains(response, "Erst Freigabe unterschreiben")
        self.assertContains(response, "Raummodell v1")

    def test_time_tracking_is_enforced_by_signed_authorization(self):
        response = self.client.post(reverse("next-time-toggle", args=[self.event.pk]))
        self.assertEqual(response.status_code, 409)
        self.assertTrue(response.json()["requires_authorization"])
        authorization = self.create_signed_auth()
        response = self.client.post(reverse("next-time-toggle", args=[self.event.pk]))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["authorization_id"], authorization.pk)
        self.assertTrue(TimeEntry.objects.filter(project=self.project, ended_at__isnull=True).exists())

    def test_signature_creates_immutable_pdf_snapshot_before_photo_and_room_revision(self):
        authorization = self.create_signed_auth()
        self.assertEqual(authorization.category, "contract")
        self.assertEqual(authorization.mime_type, "application/pdf")
        snapshot = authorization.metadata["snapshot"]
        self.assertEqual(snapshot["pricing_mode"], "fixed")
        self.assertEqual(snapshot["totals"]["gross"], "196.35")
        self.assertEqual(snapshot["room_revision"]["id"], self.revision.pk)
        self.assertEqual(snapshot["signer"]["name"], "Max Mustermann")
        self.assertEqual(len(authorization.metadata["snapshot_sha256"]), 64)
        self.assertTrue(Document.objects.filter(project=self.project, metadata__phase="before", category="photo").exists())
        self.assertTrue(Document.objects.filter(project=self.project, metadata__kind="field_authorization_signature").exists())
        pdf_response = self.client.get(reverse("field-authorization-pdf", args=[self.event.pk]))
        self.assertEqual(pdf_response.status_code, 200)
        self.assertEqual(pdf_response["Content-Type"], "application/pdf")

    def test_new_scope_creates_new_authorization_version_without_overwriting_old(self):
        first = self.create_signed_auth()
        data = self.auth_post(); data["scope"] = "Zusätzlich Rücklaufverschraubung ersetzen."; data["item_price"] = ["140.00", "45.00"]
        with patch("erp.field_authorization_views.html_to_pdf_bytes", return_value=b"%PDF-1.4 v2"):
            response = self.client.post(reverse("field-authorization-sign", args=[self.event.pk]), data=data)
        self.assertEqual(response.status_code, 200, response.content)
        docs = list(Document.objects.filter(metadata__kind="field_authorization", metadata__event_id=self.event.pk).order_by("created_at", "pk"))
        self.assertEqual(len(docs), 2)
        self.assertEqual(docs[0].pk, first.pk)
        self.assertEqual(docs[0].metadata["authorization_version"], 1)
        self.assertEqual(docs[1].metadata["authorization_version"], 2)
        self.assertNotEqual(docs[0].metadata["snapshot_sha256"], docs[1].metadata["snapshot_sha256"])

    def test_completion_generates_before_after_case_pdf_and_stops_running_timer(self):
        authorization = self.create_signed_auth()
        TimeEntry.objects.create(organization=self.org, employee=self.employee, project=self.project, started_at="2026-08-10T10:05:00+00:00", description="running")
        after = SimpleUploadedFile("nachher.png", PNG, content_type="image/png")
        with patch("erp.field_authorization_views.html_to_pdf_bytes", return_value=b"%PDF-1.4 completion"):
            response = self.client.post(reverse("field-complete-job", args=[self.event.pk]), data={"report_text": "Ventil ersetzt, Anlage entlüftet und geprüft.", "services": "Thermostatventil ersetzt; Funktion geprüft", "material": "1 Thermostatventil", "after_photos": after, "customer_reviewed": "1", "completion_signature_data": SIGNATURE})
        self.assertEqual(response.status_code, 200, response.content)
        completion = Document.objects.get(metadata__kind="field_completion", metadata__event_id=self.event.pk)
        self.assertEqual(completion.metadata["authorization_document_id"], authorization.pk)
        self.assertEqual(completion.mime_type, "application/pdf")
        self.assertTrue(Document.objects.filter(metadata__phase="after", category="photo").exists())
        self.assertTrue(Document.objects.filter(metadata__kind="field_completion_signature", metadata__event_id=self.event.pk).exists())
        self.assertFalse(TimeEntry.objects.filter(project=self.project, ended_at__isnull=True).exists())
        self.assertEqual(self.client.get(reverse("field-completion-pdf", args=[self.event.pk])).status_code, 200)

    def test_room_plan_preview_is_generated_from_same_saved_3d_revision(self):
        response = self.client.get(reverse("field-room-plan-preview", args=[self.event.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/svg+xml")
        body = response.content.decode("utf-8")
        self.assertIn("Aktueller Raumplan · v1", body)
        self.assertIn("Heizkörper", body)

    def test_quick_job_can_reuse_existing_customer(self):
        response = self.client.post(reverse("field-quick-job"), data={"customer_mode": "existing", "customer_id": self.customer.pk, "title": "Spontaner Wasserschaden", "issue": "Wasser unter Spüle"})
        self.assertEqual(response.status_code, 302)
        created = Project.objects.exclude(pk=self.project.pk).get(customer=self.customer)
        event = CalendarEvent.objects.get(project=created)
        self.assertEqual(created.status, "confirmed")
        self.assertTrue(created.members.filter(pk=self.employee.pk).exists())
        self.assertTrue(event.attendees.filter(pk=self.employee.pk).exists())
        self.assertIn(f"/appointments/{event.pk}/", response["Location"])

    def test_technician_cannot_open_unassigned_customer_job(self):
        outsider_user = User.objects.create_user("field-tech", password="secure-pass", email="tech@example.com")
        outsider_user.profile.organization = self.org; outsider_user.profile.role = UserProfile.Role.TECHNICIAN; outsider_user.profile.is_mobile_worker = True; outsider_user.profile.save()
        Employee.objects.create(organization=self.org, user=outsider_user, employee_number="FA-002", first_name="Tina", last_name="Tech", email=outsider_user.email)
        self.client.logout(); self.client.login(username="field-tech", password="secure-pass")
        self.assertEqual(self.client.get(reverse("next-appointment-detail", args=[self.event.pk])).status_code, 404)
