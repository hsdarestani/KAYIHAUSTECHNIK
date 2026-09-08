from datetime import timedelta
from pathlib import Path

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from erp.models import CalendarEvent, Customer, Employee, Organization, Project

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase14AppointmentDetailPolishTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="A+Bau phase14")
        self.office = User.objects.create_user("phase14-office", password="safe-test-password")
        self.office.profile.organization = self.org
        self.office.profile.role = "office"
        self.office.profile.is_mobile_worker = False
        self.office.profile.save()
        self.customer = Customer.objects.create(
            organization=self.org,
            number="K-P14-1",
            type="private",
            first_name="Mira",
            last_name="Kunde",
            street="Mainzer Landstraße 14",
            postal_code="60329",
            city="Frankfurt",
        )
        self.project = Project.objects.create(
            organization=self.org,
            number="P-P14-1",
            title="Badmodernisierung",
            customer=self.customer,
            status="planning",
            priority="normal",
        )
        self.employee = Employee.objects.create(
            organization=self.org,
            employee_number="E-P14-1",
            first_name="Max",
            last_name="Monteur",
            active=True,
        )
        start = timezone.now().replace(second=0, microsecond=0) + timedelta(days=1)
        self.event = CalendarEvent.objects.create(
            organization=self.org,
            project=self.project,
            title="Besichtigung Bad",
            type="inspection",
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            location="Mainzer Landstraße 14, 60329 Frankfurt",
            notes="Zugang über Innenhof.",
            created_by=self.office,
        )
        self.event.attendees.add(self.employee)
        self.client = Client()
        self.assertTrue(self.client.login(username="phase14-office", password="safe-test-password"))

    def test_office_detail_shows_compact_schedule_summary(self):
        response = self.client.get(reverse("next-appointment-detail", args=[self.event.pk]))
        self.assertEqual(response.status_code, 200)
        for marker in (
            "Terminübersicht",
            "Planung &amp; Zuordnung",
            "Terminart",
            "Besichtigung",
            "Max Monteur",
            "P-P14-1",
            "Mira Kunde",
            "Mainzer Landstraße 14, 60329 Frankfurt",
            "Zugang über Innenhof.",
        ):
            self.assertContains(response, marker)
        self.assertContains(response, reverse("next-appointment-edit", args=[self.event.pk]))

    def test_field_detail_does_not_get_duplicate_office_summary(self):
        technician = User.objects.create_user("phase14-tech", password="safe-test-password")
        technician.profile.organization = self.org
        technician.profile.role = "technician"
        technician.profile.is_mobile_worker = True
        technician.profile.save()
        technician_employee = Employee.objects.create(
            organization=self.org,
            employee_number="E-P14-T",
            first_name="Tina",
            last_name="Technik",
            active=True,
            user=technician,
        )
        self.event.attendees.add(technician_employee)
        client = Client()
        self.assertTrue(client.login(username="phase14-tech", password="safe-test-password"))
        response = client.get(reverse("next-appointment-detail", args=[self.event.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Planung &amp; Zuordnung")
        self.assertNotContains(response, "Planung bearbeiten")


class ToolTimePhase14AppointmentDetailPolishContractTests(TestCase):
    def test_detail_summary_is_responsive_and_keeps_field_workflow_markers(self):
        template = (ROOT / "templates/rebuild/appointment_detail.html").read_text(encoding="utf-8")
        css = (ROOT / "static/css/tooltime-phase14-appointment-detail.css").read_text(encoding="utf-8")
        for marker in (
            "tt-appt-detail-summary",
            "Terminübersicht",
            "event.get_type_display",
            "event.attendees.all",
            "next-appointment-edit",
            "Auftrag aufnehmen & freigeben",
            "Abschluss & Vorher/Nachher",
        ):
            self.assertIn(marker, template)
        for marker in (".tt-appt-detail-facts", "@media(max-width:650px)", "grid-template-columns:1fr"):
            self.assertIn(marker, css)
