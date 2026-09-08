from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ProjectFormLayoutPolishTests(SimpleTestCase):
    def test_project_form_has_balanced_scoped_layout(self):
        template = (ROOT / "templates/rebuild/project_form.html").read_text(encoding="utf-8")
        css_candidates = [ROOT / "static/css/kayi-readability.css", ROOT / "static/css/kayi-next.css"]
        css = "\n".join(path.read_text(encoding="utf-8") for path in css_candidates if path.exists())
        for marker in ("nx-project-pagehead", "nx-project-form", "nx-project-card", "nx-project-card-head"):
            self.assertIn(marker, template)
        self.assertIn("＋ Kunde anlegen", template)
        self.assertEqual(template.count("＋ Kunde anlegen"), 1)
        self.assertIn("A+Bau PROJECT FORM LAYOUT 2026-08-11", css)
        self.assertIn("align-items: start", css)
        self.assertIn(".nx-field:nth-child(1)", css)
        self.assertIn(".nx-field:nth-child(4)", css)
        self.assertIn(".nx-field:nth-child(7)", css)
        self.assertIn("@media (max-width: 600px)", css)
