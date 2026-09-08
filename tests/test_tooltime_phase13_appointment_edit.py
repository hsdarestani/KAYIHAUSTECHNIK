from datetime import timedelta
from pathlib import Path

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import resolve, reverse
from django.utils import timezone

from erp.models import CalendarEvent, Customer, Employee, Organization, Project

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase13AppointmentEditTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="KAYI phase13 office")
        self.other_org = Organization.objects.create(name="KAYI phase13 other")
        self.office = User.objects.create_user("phase13-office", password="safe-test-password")
        self.office.profile.organization = self.org
        self.office.profile.role = "office"
        self.office.profile.is_mobile_worker = False
        self.office.profile.save()
        self.client = Client()
        self.assertTrue(self.client.login(username="phase13-office", password="safe-test-password"))

        self.customer = Customer.objects.create(
            organization=self.org,
            number="K-P13-1",
            type="private",
            first_name="Ada",
            last_name="Termin",
            street="Testweg 13",
            postal_code="60313",
            city="Frankfurt",
        )
        self.project = Project.objects.create(
            organization=self.org,
            number="P-P13-1",
            title="Phase 13 Projekt",
            customer=self.customer,
            status="planning",
            priority="normal",
        )
        self.employee = Employee.objects.create(
            organization=self.org,
            employee_number="E-P13-1",
            first_name="Office",
            last_name="Team",
            active=True,
        )
        start = timezone.now().replace(second=0, microsecond=0) + timedelta(hours=2)
        self.event = CalendarEvent.objects.create(
            organization=self.org,
            project=self.project,
            title="Alter Termin",
            type="appointment",
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            location="Testweg 13, 60313 Frankfurt",
            notes="Alt",
            created_by=self.office,
        )

    def _post_data(self, **overrides):
        start = timezone.localtime(self.event.starts_at) + timedelta(hours=1)
        end = timezone.localtime(self.event.ends_at) + timedelta(hours=1)
        data = {
            "title": "Aktualisierter Termin",
            "type": "site",
            "starts_at": start.strftime("%Y-%m-%dT%H:%M"),
            "ends_at": end.strftime("%Y-%m-%dT%H:%M"),
            "location": "Neue Adresse 13",
            "notes": "Neu geplant",
            "project": str(self.project.pk),
            "customer_filter": str(self.customer.pk),
            "attendees": [str(self.employee.pk)],
        }
        data.update(overrides)
        return data

    def test_edit_route_is_primary_rebuild_route(self):
        path = reverse("next-appointment-edit", args=[self.event.pk])
        self.assertEqual(path, f"/appointments/{self.event.pk}/edit/")
        self.assertEqual(resolve(path).url_name, "next-appointment-edit")

    def test_office_get_reuses_tooltime_form_with_existing_selection(self):
        response = self.client.get(reverse("next-appointment-edit", args=[self.event.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Termin bearbeiten")
        self.assertContains(response, 'data-appointment-mode="edit"')
        self.assertContains(response, f'data-initial-project="{self.project.pk}"')
        self.assertContains(response, f'data-initial-customer="{self.customer.pk}"')
        self.assertContains(response, "Alter Termin")
        self.assertContains(response, "Einsatzdokumentation öffnen")

    def test_office_post_updates_real_event_and_team_without_rewriting_author(self):
        response = self.client.post(
            reverse("next-appointment-edit", args=[self.event.pk]),
            self._post_data(),
        )
        self.assertEqual(response.status_code, 302)
        self.event.refresh_from_db()
        self.assertEqual(self.event.title, "Aktualisierter Termin")
        self.assertEqual(self.event.type, "site")
        self.assertEqual(self.event.location, "Neue Adresse 13")
        self.assertEqual(self.event.notes, "Neu geplant")
        self.assertEqual(self.event.created_by, self.office)
        self.assertEqual(list(self.event.attendees.values_list("pk", flat=True)), [self.employee.pk])

    def test_cross_organization_event_cannot_be_edited(self):
        other_customer = Customer.objects.create(
            organization=self.other_org,
            number="K-P13-X",
            type="private",
            first_name="Andere",
            last_name="Firma",
        )
        other_project = Project.objects.create(
            organization=self.other_org,
            number="P-P13-X",
            title="Fremdprojekt",
            customer=other_customer,
            status="planning",
            priority="normal",
        )
        foreign = CalendarEvent.objects.create(
            organization=self.other_org,
            project=other_project,
            title="Fremder Termin",
            starts_at=timezone.now(),
            ends_at=timezone.now() + timedelta(hours=1),
        )
        response = self.client.get(reverse("next-appointment-edit", args=[foreign.pk]))
        self.assertEqual(response.status_code, 404)

    def test_field_user_is_redirected_to_operational_detail_instead_of_scheduler_edit(self):
        technician = User.objects.create_user("phase13-tech", password="safe-test-password")
        technician.profile.organization = self.org
        technician.profile.role = "technician"
        technician.profile.is_mobile_worker = True
        technician.profile.save()
        technician_employee = Employee.objects.create(
            organization=self.org,
            employee_number="E-P13-T",
            first_name="Field",
            last_name="Tech",
            active=True,
            user=technician,
        )
        self.event.attendees.add(technician_employee)
        tech_client = Client()
        self.assertTrue(tech_client.login(username="phase13-tech", password="safe-test-password"))
        response = tech_client.get(reverse("next-appointment-edit", args=[self.event.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("next-appointment-detail", args=[self.event.pk]))
        detail = tech_client.get(reverse("next-appointment-detail", args=[self.event.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertNotContains(detail, "Termin bearbeiten")

    def test_detail_exposes_edit_action_to_office_only(self):
        response = self.client.get(reverse("next-appointment-detail", args=[self.event.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Termin bearbeiten")
        self.assertContains(response, reverse("next-appointment-edit", args=[self.event.pk]))


class ToolTimePhase13AppointmentEditContractTests(TestCase):
    def test_templates_and_backend_keep_field_documentation_separate_from_scheduler_edit(self):
        form = (ROOT / "templates/rebuild/appointment_form.html").read_text(encoding="utf-8")
        detail = (ROOT / "templates/rebuild/appointment_detail.html").read_text(encoding="utf-8")
        views = (ROOT / "erp/rebuild_views.py").read_text(encoding="utf-8")
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        for marker in (
            "data-appointment-mode",
            "Termin bearbeiten",
            "Einsatzdokumentation öffnen",
        ):
            self.assertIn(marker, form)
        self.assertIn("request.user.profile.role != 'technician'", detail)
        self.assertIn("next-appointment-edit", detail)
        self.assertIn("def appointment_edit(request, pk):", views)
        self.assertIn("updated.created_by = event.created_by or request.user", views)
        self.assertIn("next-appointment-edit", urls)
