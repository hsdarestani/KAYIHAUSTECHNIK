from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase16AppointmentRecurrenceContractTests(SimpleTestCase):
    def test_recurrence_is_persistent_and_migration_is_linear(self):
        model = (ROOT / "erp/models.py").read_text(encoding="utf-8")
        migration = (ROOT / "erp/migrations/0021_calendar_event_recurrence.py").read_text(encoding="utf-8")
        views = (ROOT / "erp/rebuild_views.py").read_text(encoding="utf-8")
        template = (ROOT / "templates/rebuild/appointment_form.html").read_text(encoding="utf-8")
        for marker in ("recurrence_series = models.UUIDField", "recurrence_rule = models.CharField", "recurrence_index = models.PositiveIntegerField"):
            self.assertIn(marker, model)
        self.assertIn('(\"erp\", \"0020_calendar_event_customer\")', migration)
        for marker in ("_appointment_recurrence_request", "_appointment_recurrence_shift", "uuid.uuid4()", "occurrence.attendees.set(attendees)"):
            self.assertIn(marker, views)
        for marker in ('value="daily"', 'value="weekly"', 'value="monthly"', "data-repeat-count", "Maximal 52 Termine"):
            self.assertIn(marker, template)
