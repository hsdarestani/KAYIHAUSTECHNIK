from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from erp import rebuild_views
from erp.models import CalendarEvent, Customer, Organization, UserProfile


class ToolTimePhase18RecurrenceEditScopeTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="KAYI phase18")
        self.user = User.objects.create_user("phase18-office", password="safe-test-password")
        UserProfile.objects.update_or_create(
            user=self.user,
            defaults={"organization": self.org, "role": UserProfile.Role.ADMIN, "is_mobile_worker": False},
        )
        self.client = Client()
        self.assertTrue(self.client.login(username="phase18-office", password="safe-test-password"))
        self.customer = Customer.objects.create(
            organization=self.org,
            number="K-P18-1",
            type="business",
            company="Serienkunde Phase18",
            street="Serienweg 18",
            postal_code="60318",
            city="Frankfurt",
        )

    def _payload(self, title, start, *, repeat_rule="none", repeat_count=1, series_scope="single"):
        form = rebuild_views.AppointmentForm(organization=self.org)
        data = {
            "title": title,
            "starts_at": start.strftime("%Y-%m-%dT%H:%M"),
            "ends_at": (start + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
            "customer_filter": str(self.customer.pk),
            "repeat_rule": repeat_rule,
            "repeat_count": str(repeat_count),
            "series_scope": series_scope,
        }
        for name, field in form.fields.items():
            if name in data or not field.required:
                continue
            choices = list(getattr(field, "choices", []) or [])
            usable = [value for value, _label in choices if str(value) != ""]
            data[name] = str(usable[0]) if usable else "Test"
        return data

    def _create_series(self, title):
        start = timezone.localtime().replace(second=0, microsecond=0) + timedelta(days=1)
        response = self.client.post(
            reverse("next-appointment-create"),
            self._payload(title, start, repeat_rule="daily", repeat_count=3),
        )
        self.assertEqual(response.status_code, 302)
        return list(CalendarEvent.objects.filter(title=title).order_by("recurrence_index"))

    def test_edit_form_offers_all_three_tooltime_scopes(self):
        events = self._create_series("Scope form")
        response = self.client.get(reverse("next-appointment-edit", args=[events[1].pk]))
        self.assertEqual(response.status_code, 200)
        for marker in ("Nur diesen Termin", "Diesen und alle folgenden Termine", "Alle Termine der Serie"):
            self.assertContains(response, marker)

    def test_single_scope_changes_only_selected_occurrence(self):
        events = self._create_series("Scope single")
        selected = events[1]
        start = timezone.localtime(selected.starts_at) + timedelta(hours=1)
        response = self.client.post(
            reverse("next-appointment-edit", args=[selected.pk]),
            self._payload("Nur dieser geändert", start, series_scope="single"),
        )
        self.assertEqual(response.status_code, 302)
        titles = list(
            CalendarEvent.objects.filter(recurrence_series=selected.recurrence_series)
            .order_by("recurrence_index").values_list("title", flat=True)
        )
        self.assertEqual(titles, ["Scope single", "Nur dieser geändert", "Scope single"])

    def test_following_scope_changes_selected_and_later_occurrences(self):
        events = self._create_series("Scope following")
        selected = events[1]
        original_first_start = events[0].starts_at
        original_last_start = events[2].starts_at
        start = timezone.localtime(selected.starts_at) + timedelta(hours=2)
        response = self.client.post(
            reverse("next-appointment-edit", args=[selected.pk]),
            self._payload("Ab hier geändert", start, series_scope="following"),
        )
        self.assertEqual(response.status_code, 302)
        rows = list(
            CalendarEvent.objects.filter(recurrence_series=selected.recurrence_series).order_by("recurrence_index")
        )
        self.assertEqual([event.title for event in rows], ["Scope following", "Ab hier geändert", "Ab hier geändert"])
        self.assertEqual(rows[0].starts_at, original_first_start)
        self.assertEqual(rows[2].starts_at, original_last_start + timedelta(hours=2))

    def test_all_scope_changes_every_occurrence(self):
        events = self._create_series("Scope all")
        selected = events[1]
        start = timezone.localtime(selected.starts_at) + timedelta(minutes=30)
        response = self.client.post(
            reverse("next-appointment-edit", args=[selected.pk]),
            self._payload("Alle geändert", start, series_scope="all"),
        )
        self.assertEqual(response.status_code, 302)
        rows = list(
            CalendarEvent.objects.filter(recurrence_series=selected.recurrence_series).order_by("recurrence_index")
        )
        self.assertEqual([event.title for event in rows], ["Alle geändert", "Alle geändert", "Alle geändert"])
        self.assertEqual(rows[0].starts_at, events[0].starts_at + timedelta(minutes=30))
        self.assertEqual(rows[2].starts_at, events[2].starts_at + timedelta(minutes=30))
