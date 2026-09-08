from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase19CustomRecurrenceContractTests(SimpleTestCase):
    def test_custom_recurrence_is_persistent_and_linear(self):
        model = (ROOT / "erp/models.py").read_text(encoding="utf-8")
        migration = (ROOT / "erp/migrations/0022_calendar_event_custom_recurrence.py").read_text(encoding="utf-8")
        views = (ROOT / "erp/rebuild_views.py").read_text(encoding="utf-8")
        form = (ROOT / "templates/rebuild/appointment_form.html").read_text(encoding="utf-8")
        for marker in ("recurrence_interval", "recurrence_unit", "recurrence_until", '("custom", "Benutzerdefiniert")'):
            self.assertIn(marker, model)
        self.assertIn('(\"erp\", \"0021_calendar_event_recurrence\")', migration)
        for marker in (
            "_appointment_recurrence_indices",
            'rule == "custom"',
            "repeat_interval",
            "repeat_unit",
            "repeat_until",
            "dt.date.fromisoformat",
        ):
            self.assertIn(marker, views)
        for marker in ('value="custom"', 'name="repeat_interval"', 'name="repeat_unit"', 'name="repeat_end_mode"', 'name="repeat_until"'):
            self.assertIn(marker, form)
