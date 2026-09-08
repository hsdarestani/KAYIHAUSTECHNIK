from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ABauV3Phase1Tests(SimpleTestCase):
    def test_shell_is_structurally_upgraded_without_losing_capabilities(self):
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        for marker in ("ab-v3", "ab-v3-workspace-chip", "ab-v3-create", 'data-ab-v3-command aria-hidden=', "ab-bau-v3.css?v=20260908-2", "ab-bau-v3.js?v=20260908-2"):
            self.assertIn(marker, base)
        for route in ("next-dashboard", "next-appointments", "next-projects", "next-customers", "next-tasks", "next-quotes", "next-invoices", "next-expenses", "next-time", "next-employees", "next-field", "next-tooltime-migration", "next-settings"):
            self.assertIn(route, base)

    def test_dashboard_is_a_new_operations_cockpit_not_the_old_card_grid(self):
        dashboard = (ROOT / "templates/rebuild/dashboard.html").read_text(encoding="utf-8")
        for marker in ("data-ab-v3-dashboard", "ab-v3-dashboard-hero", "ab-v3-ops-grid", "ab-v3-focus", "ab-v3-pipeline", "ab-v3-command-deck", "Daten importieren"):
            self.assertIn(marker, dashboard)
        self.assertNotIn("Was steht an?", dashboard)
        self.assertNotIn("nx-grid nx-grid-4", dashboard)
        self.assertNotIn("Von ToolTime wechseln", dashboard)

    def test_dashboard_preserves_operational_server_data(self):
        dashboard = (ROOT / "templates/rebuild/dashboard.html").read_text(encoding="utf-8")
        for value in ("active_projects", "open_quotes", "overdue", "appointments", "recent_projects"):
            self.assertIn(value, dashboard)
        for route in ("next-appointment-detail", "next-project-detail", "next-quote-create", "next-invoice-create"):
            self.assertIn(route, dashboard)

    def test_v3_assets_cover_desktop_mobile_and_keyboard_command_flow(self):
        css = (ROOT / "static/css/ab-bau-v3.css").read_text(encoding="utf-8")
        js = (ROOT / "static/js/ab-bau-v3.js").read_text(encoding="utf-8")
        for marker in ("A+BAU V3", "ab-v3-dashboard-hero", "ab-v3-command-backdrop", "ab-v3-mobile-fab", "safe-area-inset-bottom", "@media(max-width:640px)"):
            self.assertIn(marker, css)
        for marker in ("A_BAU_V3_PHASE1_2026_09_08", "data-ab-v3-command-open", "event.metaKey", "event.ctrlKey", "abV3Ready"):
            self.assertIn(marker, js)
