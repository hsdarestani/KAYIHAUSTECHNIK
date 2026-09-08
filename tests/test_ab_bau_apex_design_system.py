from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]

class ABauApexDesignSystemTests(SimpleTestCase):
    def test_apex_is_loaded_from_main_shell(self):
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        for marker in ("ab-apex", "ab-bau-apex.css?v=20260908-2", "ab-bau-apex.js?v=20260908-1", "ab-mobile-dock", "ab-mobile-wordmark", "data-ab-open-menu"):
            self.assertIn(marker, base)

    def test_apex_unifies_old_tooltime_and_mobile_surfaces(self):
        css = (ROOT / "static/css/ab-bau-apex.css").read_text(encoding="utf-8")
        for marker in ("A+BAU APEX DESIGN SYSTEM 2026-09-08", "--apex-gold:#c7a34b", ".ab-apex .nx-sidebar", ".tt-customer-page", ".tt-project-page", ".tt-document-page", ".tt-invoice-page", ".settings-sidebar", ".nx-job-address", ".ab-mobile-dock", "env(safe-area-inset-bottom)", "prefers-reduced-motion", ".rp-viewport"):
            self.assertIn(marker, css)

    def test_runtime_supports_mobile_dock(self):
        js = (ROOT / "static/js/ab-bau-apex.js").read_text(encoding="utf-8")
        for marker in ("A+BAU_APEX_RUNTIME_2026_09_08", "[data-ab-open-menu]", "is-scrolled", "abApexReady"):
            self.assertIn(marker, js)

    def test_apex_runs_from_the_final_document_compatibility_hook(self):
        compat = (ROOT / "scripts/tooltime_document_workspace_regression_compat.py").read_text(encoding="utf-8")
        self.assertIn("ab_bau_apex_design_system.py", compat)
        self.assertIn("exec(compile(apex_path.read_text", compat)

# Browser-smoke wording guard: the redesigned dashboard no longer exposes ToolTime clone copy.
assert 'Von ToolTime wechseln' not in (ROOT / 'templates/rebuild/dashboard.html').read_text(encoding='utf-8')
assert 'Daten importieren' in (ROOT / 'templates/rebuild/dashboard.html').read_text(encoding='utf-8')
