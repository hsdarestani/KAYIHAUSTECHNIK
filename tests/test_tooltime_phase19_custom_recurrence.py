from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from erp import rebuild_views
from erp.models import CalendarEvent, Customer, Organization, UserProfile


class ToolTimePhase19CustomRecurrenceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="KAYI phase19")
        self.user = User.objects.create_user("phase19-office", password="safe-test-password")
        UserProfile.objects.update_or_create(
            user=self.user,
            defaults={"organization": self.org, "role": UserProfile.Role.ADMIN, "is_mobile_worker": False},
        )
        self.client = Client()
        self.assertTrue(self.client.login(username="phase19-office", password="safe-test-password"))
        self.customer = Customer.objects.create(
            organization=self.org,
            number="K-P19-1",
            type="business",
            company="Custom Serie Phase19",
            street="Rhythmusweg 19",
            postal_code="60319",
            city="Frankfurt",
        )

    def _payload(self, title, start, **extra):
        form = rebuild_views.AppointmentForm(organization=self.org)
        data = {
            "title": title,
            "starts_at": start.strftime("%Y-%m-%dT%H:%M"),
            "ends_at": (start + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
            "customer_filter": str(self.customer.pk),
            "repeat_rule": "custom",
            "repeat_count": "3",
            "repeat_interval": "2",
            "repeat_unit": "week",
            "repeat_end_mode": "count",
            "repeat_until": "",
        }
        data.update(extra)
        for name, field in form.fields.items():
            if name in data or not field.required:
                continue
            choices = list(getattr(field, "choices", []) or [])
            usable = [value for value, _label in choices if str(value) != ""]
            data[name] = str(usable[0]) if usable else "Test"
        return data

    def test_custom_every_two_weeks_by_count(self):
        start = timezone.make_aware(datetime(2026, 8, 21, 10, 0), timezone.get_current_timezone())
        response = self.client.post(reverse("next-appointment-create"), self._payload("Alle zwei Wochen custom", start))
        self.assertEqual(response.status_code, 302)
        events = list(CalendarEvent.objects.filter(title="Alle zwei Wochen custom").order_by("recurrence_index"))
        self.assertEqual([timezone.localtime(event.starts_at).date().isoformat() for event in events], [
            "2026-08-21", "2026-09-04", "2026-09-18",
        ])
        self.assertEqual({event.recurrence_rule for event in events}, {"custom"})
        self.assertEqual({event.recurrence_interval for event in events}, {2})
        self.assertEqual({event.recurrence_unit for event in events}, {"week"})

    def test_custom_daily_until_date_is_inclusive(self):
        start = timezone.make_aware(datetime(2026, 8, 21, 10, 0), timezone.get_current_timezone())
        payload = self._payload(
            "Bis Datum custom",
            start,
            repeat_interval="1",
            repeat_unit="day",
            repeat_end_mode="date",
            repeat_until="2026-08-24",
        )
        response = self.client.post(reverse("next-appointment-create"), payload)
        self.assertEqual(response.status_code, 302)
        events = list(CalendarEvent.objects.filter(title="Bis Datum custom").order_by("recurrence_index"))
        self.assertEqual([timezone.localtime(event.starts_at).date().isoformat() for event in events], [
            "2026-08-21", "2026-08-22", "2026-08-23", "2026-08-24",
        ])
        self.assertEqual(events[0].recurrence_until.isoformat(), "2026-08-24")

    def test_custom_weekday_interval_skips_weekends(self):
        start = timezone.make_aware(datetime(2026, 8, 21, 10, 0), timezone.get_current_timezone())
        payload = self._payload(
            "Werktag custom",
            start,
            repeat_interval="2",
            repeat_unit="weekday",
            repeat_count="3",
        )
        response = self.client.post(reverse("next-appointment-create"), payload)
        self.assertEqual(response.status_code, 302)
        events = list(CalendarEvent.objects.filter(title="Werktag custom").order_by("recurrence_index"))
        self.assertEqual([timezone.localtime(event.starts_at).date().isoformat() for event in events], [
            "2026-08-21", "2026-08-25", "2026-08-27",
        ])

    def test_form_exposes_custom_rhythm_and_end_modes(self):
        response = self.client.get(reverse("next-appointment-create"))
        self.assertEqual(response.status_code, 200)
        for marker in ("Benutzerdefiniert", "Rhythmus", "Serie endet", "Nach Anzahl", "An einem Datum", "Enddatum"):
            self.assertContains(response, marker)
