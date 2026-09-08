from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from erp import rebuild_views
from erp.models import CalendarEvent, Organization, UserProfile


class ToolTimePhase10AppointmentRuntimeTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="KAYI appointment phase10 runtime")
        self.user = User.objects.create_user("appointment-phase10-admin", password="safe-test-password")
        self.user.profile.organization = self.org
        self.user.profile.role = UserProfile.Role.ADMIN
        self.user.profile.save()
        self.client = Client()
        self.assertTrue(self.client.login(username="appointment-phase10-admin", password="safe-test-password"))

    def test_empty_get_renders_without_querydict_key_lookup_failure(self):
        response = self.client.get(reverse("next-appointment-create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-appointment-create")
        self.assertContains(response, "Kunde oder Projekt auswählen")
        self.assertContains(response, 'data-initial-customer=""')
        self.assertContains(response, 'for="id_all_day"')

    def test_empty_post_is_bound_and_surfaces_validation_errors(self):
        response = self.client.post(reverse("next-appointment-create"), {})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Termin konnte nicht gespeichert werden.")

    def test_unknown_preselection_is_ignored_without_crashing(self):
        response = self.client.get(reverse("next-appointment-create"), {"customer": "99999999", "project": "99999999"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-initial-customer=""')
        self.assertContains(response, 'data-initial-project=""')

    def test_valid_minimal_post_creates_real_calendar_event(self):
        form = rebuild_views.AppointmentForm(organization=self.org)
        start = timezone.localtime().replace(second=0, microsecond=0) + timedelta(hours=1)
        end = start + timedelta(hours=1)
        data = {
            "title": "Phase 10 echter Termin",
            "starts_at": start.strftime("%Y-%m-%dT%H:%M"),
            "ends_at": end.strftime("%Y-%m-%dT%H:%M"),
        }
        for name, field in form.fields.items():
            if not field.required or name in data:
                continue
            choices = list(getattr(field, "choices", []) or [])
            usable = [value for value, _label in choices if str(value) != ""]
            if usable:
                data[name] = str(usable[0])
            else:
                data[name] = "Test"

        response = self.client.post(reverse("next-appointment-create"), data)
        self.assertEqual(response.status_code, 302)
        event = CalendarEvent.objects.get(organization=self.org, title="Phase 10 echter Termin")
        self.assertEqual(event.created_by, self.user)
