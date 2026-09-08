from pathlib import Path

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from erp.models import CalendarEvent, Customer, Document, Employee, Organization, Project, UserProfile
from erp.services.numbering import next_number

ROOT = Path(__file__).resolve().parents[1]


class ABBauTimeEmployeeResolutionTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="A+Bau time fallback")
        self.user = User.objects.create_user("owner-without-employee", password="pass123", email="owner@example.com", first_name="Olaf", last_name="Owner")
        self.user.profile.organization = self.org
        self.user.profile.role = UserProfile.Role.ADMIN
        self.user.profile.save()
        self.customer = Customer.objects.create(organization=self.org, number=next_number(self.org, "customer"), company="Zeitkunde")
        self.project = Project.objects.create(organization=self.org, number=next_number(self.org, "project"), title="Zeitprojekt", customer=self.customer, status="confirmed")
        self.event = CalendarEvent.objects.create(organization=self.org, project=self.project, title="Einsatz", type="site", starts_at="2026-08-12T10:00:00+00:00", ends_at="2026-08-12T11:00:00+00:00", created_by=self.user)
        # A signed authorization is enough for the gated timer. The timer must not
        # fail merely because this older owner account has no Employee row yet.
        Document.objects.create(organization=self.org, project=self.project, customer=self.customer, title="Freigabe", category="contract", mime_type="application/pdf", metadata={"kind":"field_authorization","event_id":self.event.pk,"status":"signed"})
        self.client = Client(); self.client.login(username="owner-without-employee", password="pass123")

    def test_owner_without_employee_is_provisioned_for_time_tracking(self):
        response = self.client.post(reverse("next-time-toggle", args=[self.event.pk]))
        self.assertEqual(response.status_code, 200, response.content)
        employee = Employee.objects.get(organization=self.org, user=self.user)
        self.assertTrue(employee.active)
        self.assertEqual(response.json()["state"], "running")


class ABBauProjectTeamPickerContractTests(TestCase):
    def test_project_team_uses_clear_card_picker(self):
        js = (ROOT / "static/js/kayi-next.js").read_text(encoding="utf-8")
        css = (ROOT / "static/css/kayi-next.css").read_text(encoding="utf-8")
        for marker in ("A+BAU PROJECT TEAM PICKER", "Mitarbeiter auswählen", "Noch niemand ausgewählt", "ab-team-card"):
            self.assertIn(marker, js)
        self.assertIn("A+BAU TIME EMPLOYEE + TEAM PICKER", css)
        self.assertIn(".ab-team-list", css)
