from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase11AppointmentTemplateTests(SimpleTestCase):
    def test_tooltime_filters_are_layered_over_advanced_calendar(self):
        template = (ROOT / "templates/rebuild/appointments.html").read_text(encoding="utf-8")
        backend = (ROOT / "erp/rebuild_views.py").read_text(encoding="utf-8")
        calendar_js = (ROOT / "static/js/kayi-calendar.js").read_text(encoding="utf-8")
        css = (ROOT / "static/css/tooltime-phase11-appointments.css").read_text(encoding="utf-8")

        for marker in (
            "data-appointment-overview", "data-appointment-filters", "data-list-view",
            'name="q"', 'name="customer"', "Tag", "Woche", "Monat", "Liste",
            "data-calendar-drop-date", "next-appointment-move",
        ):
            self.assertIn(marker, template)
        for marker in ("query_filter", "customer_filter", "allowed_views", "appointment_move"):
            self.assertIn(marker, backend)
        for view_name in ('"day"', '"week"', '"month"', '"list"'):
            self.assertIn(view_name, backend)
        self.assertIn("dragstart", calendar_js)
        self.assertIn("fetch(url", calendar_js)
        self.assertIn("@media(max-width:760px)", css)
        self.assertIn("scroll-snap-type", css)
