from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase18RecurrenceEditScopeContractTests(SimpleTestCase):
    def test_series_edit_scope_is_persisted_by_real_backend(self):
        views = (ROOT / "erp/rebuild_views.py").read_text(encoding="utf-8")
        form = (ROOT / "templates/rebuild/appointment_form.html").read_text(encoding="utf-8")
        for marker in (
            'series_scope = (request.POST.get("series_scope") or "single")',
            'series_scope in {"following", "all"}',
            'recurrence_index__gte=original_index',
            'start_delta = updated.starts_at - original_start',
            'occurrence.attendees.set(attendees)',
        ):
            self.assertIn(marker, views)
        for marker in (
            'name="series_scope"',
            'value="single"',
            'value="following"',
            'value="all"',
            "Nur diesen Termin",
            "Diesen und alle folgenden Termine",
            "Alle Termine der Serie",
        ):
            self.assertIn(marker, form)
