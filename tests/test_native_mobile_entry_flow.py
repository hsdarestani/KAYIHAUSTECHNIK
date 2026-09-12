from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class NativeMobileEntryFlowTests(SimpleTestCase):
    def test_authenticated_entry_is_dashboard_and_store_builds_bundle(self):
        app = (ROOT / "design/native/full-app/app.js").read_text(encoding="utf-8")
        workflow = (ROOT / ".github/workflows/store-release.yml").read_text(encoding="utf-8")
        self.assertIn("route: 'home'", app)
        self.assertIn("if (state.token && state.user) bootstrap(); else renderLogin();", app)
        self.assertEqual(workflow.count("npm run build"), 2)
        self.assertEqual(workflow.count("prepare_native_store_shell.py"), 2)

    def test_scanner_is_project_scoped_and_not_global_navigation(self):
        app = (ROOT / "design/native/full-app/app.js").read_text(encoding="utf-8")
        more = app[app.index("function renderMore"):app.index("function renderProfile")]
        quick = app[app.index("function quickActions"):app.index("function renderProjects")]
        scanner = app[app.index("function renderScanner"):app.index("function renderEmployees")]
        self.assertNotIn("'scanner'", more)
        self.assertNotIn("'scanner'", quick)
        self.assertIn("state.selectedProjectId", scanner)
        self.assertIn("Projekt → Werkzeuge", scanner)

    def test_mobile_modules_logout_and_web_more_are_present(self):
        app = (ROOT / "design/native/full-app/app.js").read_text(encoding="utf-8")
        installer = (ROOT / "scripts/install_mobile_more_logout.py").read_text(encoding="utf-8")
        for marker in ("renderEmployees", "renderSettings", "Abmelden", "sessionStorage.clear()", "key.startsWith('ab.')"):
            self.assertIn(marker, app)
        self.assertIn("data-mobile-more", installer)
        self.assertIn("{% url 'logout' %}", installer)

    def test_native_back_navigation_uses_history(self):
        app = (ROOT / "design/native/full-app/app.js").read_text(encoding="utf-8")
        self.assertIn("history.pushState", app)
        self.assertIn("window.addEventListener('popstate'", app)
        self.assertIn("navigate('scanner')", app)
