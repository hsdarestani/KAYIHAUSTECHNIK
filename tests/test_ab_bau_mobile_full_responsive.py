from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]

class ABBauMobileFullResponsiveTests(SimpleTestCase):
    def test_global_mobile_hardening_covers_layouts_tables_modals_calendar_3d_and_field(self):
        css = (ROOT / "static/css/ab-bau-mobile-responsive.css").read_text(encoding="utf-8")
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        self.assertIn("ab-bau-mobile-responsive.css?v=20260822-6", base)
        for marker in (
            "A+BAU MOBILE FULL RESPONSIVE 2026-08-22",
            "grid-template-columns:minmax(0,1fr)!important",
            "overflow-x:auto!important",
            "calc(100vw - 24px)",
            ".fc .fc-toolbar",
            ".nx-calendar-toolbar",
            ".nx-calendar-views",
            ".nx-calendar-navigation",
            "[data-rp-canvas]",
            ".field-actions",
            "[role=tablist]",
            ".tt-customers-head",
            ".tt-customer-table-card",
            ".tt-customer-table-wrap",
            ".tt-customer-table",
            ".tt-new-customer",
            ":has(> .tt-new-customer)",
            "calc(100vw - 48px)",
            ".invoice-template-select",
            ":has(> .invoice-template-select)",
        ):
            self.assertIn(marker, css)

    def test_mobile_browser_audit_is_part_of_source(self):
        smoke = (ROOT / "scripts/mobile_browser_smoke.py").read_text(encoding="utf-8")
        for marker in (
            "VIEWPORTS = ((390, 844), (430, 932))",
            "audit_mobile_menu",
            "audit_calendar_modes",
            "audit_room_planner",
            "audit_field_surface",
            "document horizontal overflow",
        ):
            self.assertIn(marker, smoke)
