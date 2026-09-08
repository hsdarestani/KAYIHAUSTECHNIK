from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from erp import rebuild_views
from erp.models import CalendarEvent, Customer, Organization, UserProfile


class ToolTimePhase17RecurrenceParityTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="KAYI phase17")
        self.user = User.objects.create_user("phase17-office", password="safe-test-password")
        UserProfile.objects.update_or_create(
            user=self.user,
            defaults={"organization": self.org, "role": UserProfile.Role.ADMIN, "is_mobile_worker": False},
        )
        self.client = Client()
        self.assertTrue(self.client.login(username="phase17-office", password="safe-test-password"))
        self.customer = Customer.objects.create(
            organization=self.org,
            number="K-P17-1",
            type="business",
            company="Serienkunde Phase17",
            street="Serienweg 17",
            postal_code="60317",
            city="Frankfurt",
        )

    def _payload(self, title, start, *, rule, count):
        form = rebuild_views.AppointmentForm(organization=self.org)
        data = {
            "title": title,
            "starts_at": start.strftime("%Y-%m-%dT%H:%M"),
            "ends_at": (start + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
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

    def test_weekday_series_skips_weekend(self):
        start = timezone.make_aware(datetime(2026, 8, 21, 10, 0), timezone.get_current_timezone())  # Friday
        response = self.client.post(
            reverse("next-appointment-create"),
            self._payload("Werktagsserie", start, rule="weekdays", count=3),
        )
        self.assertEqual(response.status_code, 302)
        events = list(CalendarEvent.objects.filter(title="Werktagsserie").order_by("recurrence_index"))
        self.assertEqual([timezone.localtime(event.starts_at).date().isoformat() for event in events], [
            "2026-08-21", "2026-08-24", "2026-08-25",
        ])

    def test_biweekly_half_yearly_and_yearly_rules_are_persisted(self):
        start = timezone.make_aware(datetime(2026, 8, 21, 10, 0), timezone.get_current_timezone())
        expectations = {
            "biweekly": "2026-09-04",
            "half_yearly": "2027-02-21",
            "yearly": "2027-08-21",
        }
        for rule, second_date in expectations.items():
            title = f"Serie {rule}"
            response = self.client.post(
                reverse("next-appointment-create"),
                self._payload(title, start, rule=rule, count=2),
            )
            self.assertEqual(response.status_code, 302)
            events = list(CalendarEvent.objects.filter(title=title).order_by("recurrence_index"))
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0].recurrence_rule, rule)
            self.assertEqual(timezone.localtime(events[1].starts_at).date().isoformat(), second_date)

    def test_single_delete_keeps_other_series_occurrences(self):
        start = timezone.localtime().replace(second=0, microsecond=0) + timedelta(days=1)
        self.client.post(reverse("next-appointment-create"), self._payload("Delete single", start, rule="daily", count=3))
        events = list(CalendarEvent.objects.filter(title="Delete single").order_by("recurrence_index"))
        response = self.client.post(reverse("next-appointment-delete", args=[events[1].pk]), {"scope": "single"})
        self.assertEqual(response.status_code, 302)
        remaining = list(
            CalendarEvent.objects.filter(title="Delete single").order_by("recurrence_index").values_list("recurrence_index", flat=True)
        )
        self.assertEqual(remaining, [0, 2])

    def test_delete_following_removes_selected_and_later_occurrences(self):
        start = timezone.localtime().replace(second=0, microsecond=0) + timedelta(days=2)
        self.client.post(reverse("next-appointment-create"), self._payload("Delete following", start, rule="daily", count=4))
        events = list(CalendarEvent.objects.filter(title="Delete following").order_by("recurrence_index"))
        response = self.client.post(reverse("next-appointment-delete", args=[events[1].pk]), {"scope": "following"})
        self.assertEqual(response.status_code, 302)
        remaining = list(
            CalendarEvent.objects.filter(title="Delete following").order_by("recurrence_index").values_list("recurrence_index", flat=True)
        )
        self.assertEqual(remaining, [0])

    def test_create_form_exposes_tooltime_interval_set(self):
        response = self.client.get(reverse("next-appointment-create"))
        self.assertEqual(response.status_code, 200)
        for marker in ("Werktags", "Alle zwei Wochen", "Halbjährlich", "Jährlich"):
            self.assertContains(response, marker)
