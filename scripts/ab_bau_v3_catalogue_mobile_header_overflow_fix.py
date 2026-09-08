from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU V3 CATALOGUE MOBILE HEADER OVERFLOW FIX 2026-09-08"
CSS_REL = "static/css/ab-bau-v3-finance-mobile-pdf-hotfix.css"
TEST_REL = "tests/test_ab_bau_v3_catalogue_mobile_header_overflow_fix.py"

MOBILE_FIX = r"""

/* A+BAU V3 CATALOGUE MOBILE HEADER OVERFLOW FIX 2026-09-08
   The mobile catalogue is rendered as labelled cards and has its own sort control.
   Keep the desktop semantic table header intact, but remove the table header from
   mobile layout so its intrinsic TH widths cannot escape the phone viewport. */
@media(max-width:860px){
  body.ab-apex .ttc-table thead{display:none!important}
}
"""


def install_css() -> None:
    path = ROOT / CSS_REL
    if not path.exists():
        raise RuntimeError(f"Catalogue mobile overflow target missing: {CSS_REL}")
    text = path.read_text(encoding="utf-8")
    if MARKER not in text:
        text = text.rstrip() + MOBILE_FIX + "\n"
        path.write_text(text, encoding="utf-8")


def install_test() -> None:
    path = ROOT / TEST_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ABauV3CatalogueMobileHeaderOverflowFixTests(SimpleTestCase):
    def test_mobile_catalogue_header_does_not_participate_in_layout(self):
        css = (ROOT / "static/css/ab-bau-v3-finance-mobile-pdf-hotfix.css").read_text(encoding="utf-8")
        self.assertIn("A+BAU V3 CATALOGUE MOBILE HEADER OVERFLOW FIX 2026-09-08", css)
        self.assertIn("body.ab-apex .ttc-table thead{display:none!important}", css)

    def test_desktop_catalogue_header_contract_still_exists(self):
        template = (ROOT / "templates/rebuild/catalogue.html").read_text(encoding="utf-8")
        self.assertIn("<thead>", template)
        self.assertIn("<th>Artikelnummer</th>", template)
''',
        encoding="utf-8",
    )


def guard() -> None:
    css = (ROOT / CSS_REL).read_text(encoding="utf-8")
    if MARKER not in css or "body.ab-apex .ttc-table thead{display:none!important}" not in css:
        raise RuntimeError("Catalogue mobile header overflow guard failed")


def main() -> None:
    install_css()
    install_test()
    guard()
    print(f"{MARKER}: mobile catalogue table header removed from layout; desktop header preserved.")


if __name__ == "__main__":
    main()
