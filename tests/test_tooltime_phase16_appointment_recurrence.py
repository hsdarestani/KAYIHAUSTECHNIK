from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from erp import rebuild_views
from erp.models import CalendarEvent, Customer, Organization, UserProfile


class ToolTimePhase16AppointmentRecurrenceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="KAYI phase16")
        self.user = User.objects.create_user("phase16-office", password="safe-test-password")
        UserProfile.objects.update_or_create(
            user=self.user,
            defaults={"organization": self.org, "role": UserProfile.Role.ADMIN, "is_mobile_worker": False},
        )
        self.client = Client()
        self.assertTrue(self.client.login(username="phase16-office", password="safe-test-password"))
        self.customer = Customer.objects.create(
            organization=self.org,
            number="K-P16-1",
            type="business",
            company="Serienkunde",
            street="Serienweg 16",
            postal_code="60316",
            city="Frankfurt",
        )

    def _payload(self, title, start, *, rule="none", count=4):
        form = rebuild_views.AppointmentForm(organization=self.org)
        end = start + timedelta(hours=1)
        data = {
            "title": title,
            "starts_at": start.strftime("%Y-%m-%dT%H:%M"),
            "ends_at": end.strftime("%Y-%m-%dT%H:%M"),
            "customer_filter": str(self.customer.pk),
            "repeat_rule": rule,
            "repeat_count": str(count),
        }
        for name, field in form.fields.items():
            if name in data or not field.required:
                continue
            choices = list(getattr(field, "choices", []) or [])
            usable = [value for value, _label in choices if str(value) != ""]
            data[name] = str(usable[0]) if usable else "Test"
        return data

    def test_daily_series_creates_persistent_occurrences_with_one_series_id(self):
        start = timezone.localtime().replace(second=0, microsecond=0) + timedelta(days=1)
        response = self.client.post(
            reverse("next-appointment-create"),
            self._payload("Tägliche Serie", start, rule="daily", count=3),
        )
        self.assertEqual(response.status_code, 302)
        events = list(CalendarEvent.objects.filter(organization=self.org, title="Tägliche Serie").order_by("recurrence_index"))
        self.assertEqual(len(events), 3)
        self.assertIsNotNone(events[0].recurrence_series)
        self.assertEqual(len({event.recurrence_series for event in events}), 1)
        self.assertEqual([event.recurrence_index for event in events], [0, 1, 2])
        self.assertEqual({event.recurrence_rule for event in events}, {"daily"})
        self.assertEqual({event.customer_id for event in events}, {self.customer.pk})
        dates = [timezone.localtime(event.starts_at).date() for event in events]
        self.assertEqual((dates[1] - dates[0]).days, 1)
        self.assertEqual((dates[2] - dates[1]).days, 1)

    def test_monthly_series_clamps_end_of_month_without_date_drift(self):
        start = timezone.make_aware(datetime(2027, 1, 31, 10, 0), timezone.get_current_timezone())
        response = self.client.post(
            reverse("next-appointment-create"),
            self._payload("Monatsserie", start, rule="monthly", count=3),
        )
        self.assertEqual(response.status_code, 302)
        events = list(CalendarEvent.objects.filter(organization=self.org, title="Monatsserie").order_by("recurrence_index"))
        self.assertEqual(len(events), 3)
        dates = [timezone.localtime(event.starts_at).date().isoformat() for event in events]
        self.assertEqual(dates, ["2027-01-31", "2027-02-28", "2027-03-31"])

    def test_no_repeat_stays_single_persistent_event(self):
        start = timezone.localtime().replace(second=0, microsecond=0) + timedelta(days=2)
        response = self.client.post(
            reverse("next-appointment-create"),
            self._payload("Einzeltermin", start, rule="none", count=12),
        )
        self.assertEqual(response.status_code, 302)
        event = CalendarEvent.objects.get(organization=self.org, title="Einzeltermin")
        self.assertEqual(event.recurrence_rule, "none")
        self.assertIsNone(event.recurrence_series)
        self.assertEqual(event.recurrence_index, 0)

    def test_create_form_exposes_real_recurrence_controls(self):
        response = self.client.get(reverse("next-appointment-create"))
        self.assertEqual(response.status_code, 200)
        for marker in ("Täglich", "Wöchentlich", "Monatlich", "Anzahl Termine", "max=\"52\""):
            self.assertContains(response, marker)
