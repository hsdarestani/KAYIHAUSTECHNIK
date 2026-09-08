from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU V3 QUOTES NEW MENU OVERFLOW FIX 2026-09-08"
CSS_REL = "static/css/ab-bau-v3-finance-mobile-pdf-hotfix.css"
TEST_REL = "tests/test_ab_bau_v3_quotes_new_menu_overflow_fix.py"

CSS_FIX = r"""

/* A+BAU V3 QUOTES NEW MENU OVERFLOW FIX 2026-09-08
   The Neues Angebot dropdown is taller than the commercial hero. The hero used
   overflow:hidden for decoration, which clipped the open menu at its bottom edge.
   Keep the dropdown above the following filters/table and anchor it to the trigger. */
body.ab-apex .ttq-topbar{
  overflow:visible!important;
  z-index:30!important;
}
body.ab-apex .ttq-top-actions,
body.ab-apex .ttq-new-menu{
  position:relative!important;
  z-index:40!important;
}
body.ab-apex .ttq-menu-card{
  position:absolute!important;
  top:calc(100% + 10px)!important;
  right:0!important;
  left:auto!important;
  z-index:60!important;
  min-width:220px!important;
  max-width:min(320px,calc(100vw - 32px))!important;
}
@media(max-width:860px){
  body.ab-apex .ttq-menu-card{
    width:min(320px,calc(100vw - 36px))!important;
    max-width:calc(100vw - 36px)!important;
  }
}
"""


def install_css() -> None:
    path = ROOT / CSS_REL
    if not path.exists():
        raise RuntimeError(f"Quotes menu overflow target missing: {CSS_REL}")
    text = path.read_text(encoding="utf-8")
    if MARKER not in text:
        path.write_text(text.rstrip() + CSS_FIX + "\n", encoding="utf-8")


def install_test() -> None:
    path = ROOT / TEST_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ABauV3QuotesNewMenuOverflowFixTests(SimpleTestCase):
    def test_new_quote_menu_can_escape_hero_and_stay_above_following_content(self):
        css = (ROOT / "static/css/ab-bau-v3-finance-mobile-pdf-hotfix.css").read_text(encoding="utf-8")
        self.assertIn("A+BAU V3 QUOTES NEW MENU OVERFLOW FIX 2026-09-08", css)
        self.assertIn("body.ab-apex .ttq-topbar{", css)
        self.assertIn("overflow:visible!important", css)
        self.assertIn("z-index:30!important", css)
        self.assertIn("body.ab-apex .ttq-menu-card{", css)
        self.assertIn("top:calc(100% + 10px)!important", css)
        self.assertIn("z-index:60!important", css)
        self.assertIn("right:0!important", css)

    def test_fix_runs_after_commercial_hotfix(self):
        unpack = (ROOT / "scripts/unpack-source.sh").read_text(encoding="utf-8")
        self.assertGreater(
            unpack.rfind("python3 scripts/ab_bau_v3_quotes_new_menu_overflow_fix.py"),
            unpack.rfind("python3 scripts/ab_bau_v3_finance_mobile_pdf_hotfix.py"),
        )
''',
        encoding="utf-8",
    )


def guard() -> None:
    css = (ROOT / CSS_REL).read_text(encoding="utf-8")
    for required in (
        MARKER,
        "body.ab-apex .ttq-topbar{",
        "overflow:visible!important",
        "body.ab-apex .ttq-menu-card{",
        "top:calc(100% + 10px)!important",
        "z-index:60!important",
    ):
        if required not in css:
            raise RuntimeError(f"Quotes new-menu overflow guard failed: {required}")


def main() -> None:
    install_css()
    install_test()
    guard()
    print(f"{MARKER}: Neues Angebot dropdown is no longer clipped by the commercial hero.")


if __name__ == "__main__":
    main()
