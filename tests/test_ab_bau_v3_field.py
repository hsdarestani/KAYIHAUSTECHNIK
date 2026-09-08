from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import importlib.util
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]

class ABauV3FieldTests(SimpleTestCase):
    def test_field_home_is_structurally_upgraded_without_deleting_tooltime_capabilities(self):
        template = (ROOT / "templates/rebuild/field_home.html").read_text(encoding="utf-8")
        for marker in (
            "data-ab-v3-field", "data-ab-v3-field-deck", "data-ab-v3-next-job",
            "Field Deck", "Nächster Einsatz", "nx-mobile-tabs", "nx-job-card",
            "planned", "overdue", "documented", "next-appointment-detail", "next-time",
            "Projekt aufnehmen", "Vor Ort in einem Ablauf", "Signierte PDF",
        ):
            self.assertIn(marker, template)

    def test_v3_keeps_upstream_field_workflow_instead_of_reimplementing_it(self):
        spec = importlib.util.spec_from_file_location(
            "v3_field_installer", ROOT / "scripts/ab_bau_v3_phase1_field.py"
        )
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        # Exercise the actual transformation, including unknown future field hooks.
        upstream_body = (
            '<nav class="nx-mobile-tabs">Vor Ort in einem Ablauf</nav>'
            '<a class="nx-job-card" href="/field/appointments/42/">Einsatz</a>'
            '<form method="post" action="/field/capture/" data-future-field-hook>'
            '{% csrf_token %}<button>Projekt aufnehmen</button>'
            '<input name="signature" value="signed-scope"></form>'
            '<script src="/static/js/field-voice.js"></script></div>'
        )
        upstream = '<div class="nx-field-shell" data-existing-root>' + upstream_body
        with TemporaryDirectory() as directory:
            field = Path(directory) / "field_home.html"
            field.write_text(upstream, encoding="utf-8")
            with patch.object(installer, "FIELD", field):
                installer.install_field_template()
                upgraded = field.read_text(encoding="utf-8")
                self.assertTrue(upgraded.endswith(upstream_body))
                self.assertIn("data-existing-root", upgraded)
                self.assertEqual(upgraded.count("data-ab-v3-field-deck"), 1)
                installer.install_field_template()
                self.assertEqual(field.read_text(encoding="utf-8"), upgraded)

                incomplete = '<div class="nx-field-shell">Missing workflows</div>'
                field.write_text(incomplete, encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "missing upstream contracts"):
                    installer.install_field_template()
                self.assertEqual(field.read_text(encoding="utf-8"), incomplete)

    def test_field_visuals_are_mobile_first(self):
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        css = (ROOT / "static/css/ab-bau-v3-field.css").read_text(encoding="utf-8")
        self.assertIn("ab-bau-v3-field.css?v=20260908-3", base)
        for marker in ("A+BAU V3", ".ab-v3-field-hero", ".ab-v3-next-job", ".ab-v3-field-flow-label", "safe-area-inset-bottom"):
            self.assertIn(marker, css)
