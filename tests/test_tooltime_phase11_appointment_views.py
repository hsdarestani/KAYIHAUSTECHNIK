from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from erp.models import CalendarEvent, Organization, UserProfile


class ToolTimePhase11AppointmentViewTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="KAYI appointment phase11")
        self.other_org = Organization.objects.create(name="KAYI appointment phase11 other")
        self.user = User.objects.create_user("appointment-phase11-admin", password="safe-test-password")
        UserProfile.objects.update_or_create(
            user=self.user,
            defaults={"organization": self.org, "role": UserProfile.Role.ADMIN, "is_mobile_worker": False},
        )
        self.client = Client()
        self.assertTrue(self.client.login(username="appointment-phase11-admin", password="safe-test-password"))
        start = timezone.localtime().replace(second=0, microsecond=0) + timedelta(hours=2)
        self.event = CalendarEvent.objects.create(
            organization=self.org,
            title="Wartung Wärmepumpe",
            location="Frankfurt",
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            created_by=self.user,
        )
        CalendarEvent.objects.create(
            organization=self.other_org,
            title="Fremder Mandant Termin",
            starts_at=start,
            ends_at=start + timedelta(hours=1),
        )
        self.anchor = timezone.localtime(self.event.starts_at).date().isoformat()

    def test_existing_multiview_calendar_is_preserved(self):
        for view in ("day", "week", "month", "list"):
            response = self.client.get(reverse("next-appointments"), {"view": view, "date": self.anchor})
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, f'data-calendar-view="{view}"')
            self.assertContains(response, "Wartung Wärmepumpe")

    def test_search_is_organization_scoped(self):
        own = self.client.get(reverse("next-appointments"), {"view": "list", "date": self.anchor, "q": "Wärmepumpe"})
        self.assertContains(own, "Wartung Wärmepumpe")
        foreign = self.client.get(reverse("next-appointments"), {"view": "list", "date": self.anchor, "q": "Fremder Mandant"})
        self.assertNotContains(foreign, "Fremder Mandant Termin")

    def test_invalid_view_falls_back_to_week(self):
        response = self.client.get(reverse("next-appointments"), {"view": "unknown", "date": self.anchor})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-calendar-view="week"')
