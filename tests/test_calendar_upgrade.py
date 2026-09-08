from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class CalendarUpgradeContractTests(SimpleTestCase):
    def test_calendar_multiview_contract(self):
        template = (ROOT / "templates/rebuild/appointments.html").read_text(encoding="utf-8")
        views = (ROOT / "erp/rebuild_views.py").read_text(encoding="utf-8")
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        js = (ROOT / "static/js/kayi-calendar.js").read_text(encoding="utf-8")
        for marker in ("Tag", "Woche", "Monat", "Liste", "Mitarbeiter", "Projekt", "data-calendar-view"):
            self.assertIn(marker, template)
        self.assertIn("def appointment_move", views)
        self.assertIn("attendees__pk", views)
        self.assertIn("next-appointment-move", urls)
        self.assertIn("data-calendar-drop-date", template)
        self.assertIn("X-CSRFToken", js)
        self.assertIn("window.location.reload", js)
