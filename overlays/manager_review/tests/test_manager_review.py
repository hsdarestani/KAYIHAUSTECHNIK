from __future__ import annotations

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import Client, TestCase
from django.urls import reverse

from erp.models import CalendarEvent, Customer, Document, Employee, Organization, Project, UserProfile
from erp.services.numbering import next_number


class ManagerReviewTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="KAYI Review")
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
        self.completion = Document(organization=self.org, project=self.project, customer=self.customer, uploaded_by=self.tech, title="Einsatzabschluss", category="report", mime_type="application/pdf", size=8, metadata={"kind": "field_completion", "event_id": self.event.pk, "status": "pending_review", "billing_ready": False})
        self.completion.file.save("completion.pdf", ContentFile(b"%PDF-1.4"), save=False)
        self.completion.save()
        self.client = Client()

    def test_office_sees_pending_and_can_approve(self):
        self.client.login(username="review-admin", password="secure-pass")
        response = self.client.get(reverse("field-review-queue"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Einsatzprüfung")
        self.assertContains(response, "Vor-Ort Reparatur")
        response = self.client.post(reverse("field-review-approve", args=[self.completion.pk]), {"note": "Geprüft."})
        self.assertEqual(response.status_code, 302)
        self.completion.refresh_from_db()
        self.assertEqual(self.completion.metadata["status"], "approved")
        self.assertTrue(self.completion.metadata["billing_ready"])
        self.assertEqual(self.completion.metadata["reviewed_by_id"], self.admin.pk)

    def test_office_can_request_changes_and_technician_cannot_review(self):
        self.client.login(username="review-admin", password="secure-pass")
        self.client.post(reverse("field-review-changes", args=[self.completion.pk]), {"note": "Bitte Nachher-Foto ergänzen."})
        self.completion.refresh_from_db()
        self.assertEqual(self.completion.metadata["status"], "changes_requested")
        self.assertFalse(self.completion.metadata["billing_ready"])
        self.assertEqual(self.completion.metadata["review_note"], "Bitte Nachher-Foto ergänzen.")
        self.client.logout(); self.client.login(username="review-tech", password="secure-pass")
        self.assertEqual(self.client.get(reverse("field-review-queue")).status_code, 403)
        self.assertEqual(self.client.post(reverse("field-review-approve", args=[self.completion.pk])).status_code, 403)

    def test_completion_contract_routes_new_jobs_to_review(self):
        from pathlib import Path
        field = Path("erp/field_authorization_views.py").read_text(encoding="utf-8")
        template = Path("templates/rebuild/appointment_detail.html").read_text(encoding="utf-8")
        self.assertIn('"status": "pending_review"', field)
        self.assertIn('"billing_ready": False', field)
        self.assertIn("Wartet auf Bürofreigabe", template)
        self.assertIn("Änderung angefordert", template)
