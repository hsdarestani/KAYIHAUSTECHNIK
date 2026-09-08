from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from erp.models import CalendarEvent, Organization, UserProfile


class ToolTimePhase12AppointmentMapTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="KAYI appointment phase12")
        self.other_org = Organization.objects.create(name="KAYI appointment phase12 foreign")
        self.user = User.objects.create_user("appointment-phase12-admin", password="safe-test-password")
        UserProfile.objects.update_or_create(
            user=self.user,
            defaults={"organization": self.org, "role": UserProfile.Role.ADMIN, "is_mobile_worker": False},
        )
        self.client = Client()
        self.assertTrue(self.client.login(username="appointment-phase12-admin", password="safe-test-password"))
        start = timezone.localtime().replace(second=0, microsecond=0) + timedelta(hours=2)
        self.event = CalendarEvent.objects.create(
            organization=self.org,
            title="Kundendienst Sachsenhausen",
            location="Schweizer Straße 10, 60594 Frankfurt am Main",
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            created_by=self.user,
        )
        CalendarEvent.objects.create(
            organization=self.other_org,
            title="Fremder Karten-Termin",
            location="Berlin Alexanderplatz",
            starts_at=start,
            ends_at=start + timedelta(hours=1),
        )
        self.anchor = timezone.localtime(self.event.starts_at).date().isoformat()

    def test_map_view_lists_only_organization_scoped_addressed_events(self):
        response = self.client.get(reverse("next-appointments"), {"view": "map", "date": self.anchor})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-calendar-view="map"')
        self.assertContains(response, "Kundendienst Sachsenhausen")
        self.assertContains(response, "Schweizer Straße 10, 60594 Frankfurt am Main")
        self.assertNotContains(response, "Fremder Karten-Termin")
        self.assertContains(response, "Die externe Karte wird erst nach deiner Auswahl geladen.")

    def test_calendar_list_and_map_views_coexist(self):
        for view in ("day", "week", "month", "map", "list"):
            response = self.client.get(reverse("next-appointments"), {"view": view, "date": self.anchor})
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, f'data-calendar-view="{view}"')
