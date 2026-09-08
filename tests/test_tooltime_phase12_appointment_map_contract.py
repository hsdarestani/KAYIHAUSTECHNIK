from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase12AppointmentMapContractTests(SimpleTestCase):
    def test_map_is_real_on_demand_view_without_fake_coordinates_or_api_key(self):
        backend = (ROOT / "erp/rebuild_views.py").read_text(encoding="utf-8")
        template = (ROOT / "templates/rebuild/appointments.html").read_text(encoding="utf-8")
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        javascript = (ROOT / "static/js/tooltime-phase12-appointment-map.js").read_text(encoding="utf-8")
        css = (ROOT / "static/css/tooltime-phase12-appointment-map.css").read_text(encoding="utf-8")

        for marker in ('"map"', "map_events", "ui_map_address", "query_filter", "customer_filter"):
            self.assertIn(marker, backend)
        for marker in ("data-appointment-map", "data-map-select", "data-map-frame", "Karte", "data-list-view", "data-calendar-drop-date"):
            self.assertIn(marker, template)
        for marker in ("data-appointment-subnav", "?view=week", "?view=map", "?view=list"):
            self.assertIn(marker, base)
        self.assertIn("encodeURIComponent(address)", javascript)
        self.assertIn("output=embed", javascript)
        self.assertIn("maps/search/?api=1", javascript)
        self.assertNotIn("AIza", javascript)
        self.assertNotIn("data-latitude", template.lower())
        self.assertNotIn("data-longitude", template.lower())
        self.assertIn("@media(max-width:760px)", css)
        self.assertIn("dragstart", (ROOT / "static/js/kayi-calendar.js").read_text(encoding="utf-8"))
