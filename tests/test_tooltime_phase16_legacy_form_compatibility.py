from django.test import SimpleTestCase

from erp.models import CalendarEvent


class ToolTimePhase16LegacyFormCompatibilityTests(SimpleTestCase):
    def test_recurrence_bookkeeping_is_internal_model_metadata(self):
        for name in ("recurrence_series", "recurrence_rule", "recurrence_index"):
            self.assertFalse(CalendarEvent._meta.get_field(name).editable, name)
