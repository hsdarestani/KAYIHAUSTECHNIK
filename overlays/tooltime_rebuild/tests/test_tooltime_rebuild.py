from pathlib import Path

from django.test import SimpleTestCase
from django.urls import resolve, reverse


class ToolTimeParityRebuildTests(SimpleTestCase):
    def test_rebuild_routes_take_over_primary_product_flow(self):
        expected = {
            "/": "next-dashboard",
            "/customers/": "next-customers",
            "/projects/": "next-projects",
            "/appointments/": "next-appointments",
            "/field/": "next-field",
            "/time/": "next-time",
            "/tasks/": "next-tasks",
            "/expenses/": "next-expenses",
            "/employees/": "next-employees",
            "/quotes/": "next-quotes",
            "/invoices/": "next-invoices",
            "/migration/tooltime/": "next-tooltime-migration",
        }
        for path, name in expected.items():
            self.assertEqual(resolve(path).url_name, name, path)
            self.assertEqual(reverse(name), path)

    def test_rebuild_templates_and_assets_are_installed(self):
        root = Path(__file__).resolve().parents[1]
        required = [
            root / "templates/rebuild/base.html",
            root / "templates/rebuild/dashboard.html",
            root / "templates/rebuild/project_detail.html",
            root / "templates/rebuild/appointment_detail.html",
            root / "templates/rebuild/field_home.html",
            root / "templates/rebuild/document_editor.html",
            root / "templates/rebuild/tasks.html",
            root / "templates/rebuild/expenses.html",
            root / "templates/rebuild/employees.html",
            root / "templates/rebuild/migration.html",
            root / "static/css/kayi-next.css",
            root / "static/css/kayi-next-field.css",
            root / "static/js/kayi-next.js",
        ]
        for path in required:
            self.assertTrue(path.exists(), str(path))

    def test_field_workspace_keeps_voice_ai_signature_offline_and_3d_hooks(self):
        root = Path(__file__).resolve().parents[1]
        appointment = (root / "templates/rebuild/appointment_detail.html").read_text(encoding="utf-8")
        js = (root / "static/js/kayi-next.js").read_text(encoding="utf-8")
        project = (root / "templates/rebuild/project_detail.html").read_text(encoding="utf-8")
        for marker in ("data-voice", "data-ai-structure", "nx-signature", "data-documentation-form"):
            self.assertIn(marker, appointment)
        for marker in ("indexedDB", "kayi-next-offline", "SpeechRecognition", "flushQueue"):
            self.assertIn(marker, js)
        self.assertIn("Aufmaß & 3D", project)
        self.assertIn("{% url 'configurator' %}", project)

    def test_office_navigation_does_not_fall_back_to_legacy_for_daily_modules(self):
        root = Path(__file__).resolve().parents[1]
        base = (root / "templates/rebuild/base.html").read_text(encoding="utf-8")
        for name in ("next-customers", "next-projects", "next-appointments", "next-tasks", "next-expenses", "next-employees", "next-quotes", "next-invoices"):
            self.assertIn(name, base)

    def test_legacy_nine_step_wizard_is_not_primary_project_creation(self):
        root = Path(__file__).resolve().parents[1]
        form = (root / "templates/rebuild/project_form.html").read_text(encoding="utf-8")
        self.assertIn("Kein Wizard", form)
        self.assertNotIn("9-Schritte-Projektassistent", form)
