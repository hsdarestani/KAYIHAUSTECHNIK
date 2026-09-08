import re
from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ABBauLogoFrameTests(SimpleTestCase):
    def test_sidebar_contains_only_large_logo_image(self):
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        match = re.search(r'<a class="nx-brand ab-brand".*?</a>', base, flags=re.S)
        self.assertIsNotNone(match)
        brand = match.group(0)
        self.assertIn("ab-brand-logo-only", brand)
        self.assertIn("data-ab-brand-image", brand)
        self.assertIn("brand/ab-bau-logo.png", brand)
        self.assertIn("20260812-logo-2", brand)
        self.assertIn("width:188px!important", brand)
        self.assertNotIn("<strong>", brand)
        self.assertNotIn("<small>", brand)
        self.assertEqual(brand.count("<img"), 1)

    def test_sidebar_logo_has_no_frame_or_panel(self):
        css = (ROOT / "static/css/kayi-next.css").read_text(encoding="utf-8")
        self.assertIn("A+BAU LOGO ONLY SIDEBAR 2026-08-12", css)
        self.assertIn("width:188px!important", css)
        self.assertIn("border:0!important", css)
        self.assertIn("background:transparent!important", css)
        self.assertIn("box-shadow:none!important", css)
        self.assertIn("border-radius:0!important", css)
        self.assertIn("object-fit:contain!important", css)
