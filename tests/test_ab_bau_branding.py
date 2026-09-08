from pathlib import Path
import io
import re
import tokenize

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]
OLD = re.compile(r"(?<![A-Za-z0-9_])KAYI(?![A-Za-z0-9_])")


class ABauBrandingTests(SimpleTestCase):
    def test_templates_have_no_visible_old_brand(self):
        offenders = []
        for path in (ROOT / "templates").rglob("*.html"):
            text = path.read_text(encoding="utf-8")
            if OLD.search(text):
                offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])

    def test_python_user_facing_strings_have_no_old_brand(self):
        offenders = []
        for path in (ROOT / "erp").rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            try:
                tokens = tokenize.generate_tokens(io.StringIO(text).readline)
                for token in tokens:
                    if token.type == tokenize.STRING and OLD.search(token.string) and "X-KAYI-Inbound-Token" not in token.string and "X-KAYI-INBOUND-TOKEN" not in token.string:
                        offenders.append(str(path.relative_to(ROOT)))
                        break
            except tokenize.TokenError:
                continue
        self.assertEqual(offenders, [])

    def test_room_ai_uses_ab_bau_brand(self):
        path = ROOT / "erp" / "services" / "room_ai.py"
        if path.exists():
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("KAYI-Renovierungsplaner", text)
            self.assertIn("A+Bau-Renovierungsplaner", text)
