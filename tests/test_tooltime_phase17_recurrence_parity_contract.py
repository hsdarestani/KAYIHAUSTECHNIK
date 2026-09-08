from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase17RecurrenceParityContractTests(SimpleTestCase):
    def test_interval_choices_delete_route_and_detail_actions_are_real(self):
        model = (ROOT / "erp/models.py").read_text(encoding="utf-8")
        migration = (ROOT / "erp/migrations/0021_calendar_event_recurrence.py").read_text(encoding="utf-8")
        views = (ROOT / "erp/rebuild_views.py").read_text(encoding="utf-8")
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        form = (ROOT / "templates/rebuild/appointment_form.html").read_text(encoding="utf-8")
        detail = (ROOT / "templates/rebuild/appointment_detail.html").read_text(encoding="utf-8")
        for marker in ("weekdays", "biweekly", "half_yearly", "yearly"):
            self.assertIn(marker, model)
            self.assertIn(marker, migration)
            self.assertIn(marker, views)
            self.assertIn(marker, form)
        self.assertIn("def appointment_delete(request, pk):", views)
        self.assertIn('scope == "following"', views)
        self.assertIn("recurrence_index__gte=event.recurrence_index", views)
        self.assertIn("next-appointment-delete", urls)
        self.assertIn("next-appointment-delete", detail)
        self.assertIn("Diesen und alle folgenden Serientermine löschen", detail)
