from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimeAppointmentSidebarNavFixTests(SimpleTestCase):
    def test_sidebar_has_one_live_calendar_map_list_group(self):
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        self.assertEqual(base.count("data-appointment-subnav"), 1)
        self.assertEqual(base.count("?view=week"), 1)
        self.assertEqual(base.count("?view=map"), 1)
        self.assertEqual(base.count("?view=list"), 1)
        self.assertNotIn('<div class="tt-appt-subnav">', base)
        self.assertNotIn("Kartenansicht folgt auf Basis persistierter Geodaten", base)

    def test_submenu_is_present_on_all_appointment_pages_and_active_state_is_safe(self):
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        self.assertIn("data-appointment-nav-group", base)
        self.assertIn("request.resolver_match.url_name == 'next-appointments' and calendar_view == 'map'", base)
        self.assertNotIn("{% if request.resolver_match.url_name == 'next-appointments' %}<div class=\"tt-appointment-subnav\"", base)

    def test_active_map_label_is_visible_on_dark_sidebar(self):
        css = (ROOT / "static/css/tooltime-phase12-appointment-map.css").read_text(encoding="utf-8")
        self.assertIn("A+BAU TOOLTIME APPOINTMENT SIDEBAR NAV FIX 2026-08-21", css)
        self.assertIn(".nx-sidebar .tt-appointment-subnav a.is-active", css)
        self.assertIn("color:#fff!important", css)
        self.assertIn(".nx-sidebar .tt-appt-subnav{display:none!important}", css)
