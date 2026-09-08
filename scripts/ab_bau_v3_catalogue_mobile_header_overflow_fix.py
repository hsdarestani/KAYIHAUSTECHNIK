from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU V3 CATALOGUE MOBILE HEADER OVERFLOW FIX 2026-09-08"
UPLOAD_MARKER = "A+BAU V3 SETTINGS LOGO MULTIPART FIX 2026-09-08"
DASHBOARD_MARKER = "A+BAU V3 DASHBOARD HERO FLOW FIX 2026-09-08"
CACHE_VERSION = "20260908-finance-mobile-pdf-4"
CSS_REL = "static/css/ab-bau-v3-finance-mobile-pdf-hotfix.css"
SETTINGS_REL = "templates/rebuild/tooltime_settings.html"
BASE_REL = "templates/rebuild/base.html"
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

DASHBOARD_FIX = r"""

/* A+BAU V3 DASHBOARD HERO FLOW FIX 2026-09-08
   The KPI strip used to be absolutely pinned to the hero bottom. At desktop zoom
   levels and on shorter viewports that let the two-line greeting and intro copy
   physically collide with the KPI labels. Keep both rows in normal layout flow so
   the hero grows with its content instead of allowing any overlap. */
@media(min-width:1101px){
  body.ab-v3 .ab-v3-dashboard-hero{
    min-height:0!important;
    height:auto!important;
    display:grid!important;
    grid-template-rows:auto auto!important;
    align-content:start!important;
    row-gap:28px!important;
  }
  body.ab-v3 .ab-v3-hero-top{min-height:0!important}
  body.ab-v3 .ab-v3-hero-copy{min-width:0;max-width:calc(100% - 260px)}
  body.ab-v3 .ab-v3-hero-copy h1{
    max-width:680px!important;
    font-size:clamp(38px,4vw,60px)!important;
    line-height:.98!important;
  }
  body.ab-v3 .ab-v3-hero-copy p{max-width:640px!important;margin-top:14px!important}
  body.ab-v3 .ab-v3-metrics{
    position:relative!important;
    inset:auto!important;
    left:auto!important;
    right:auto!important;
    bottom:auto!important;
    width:100%!important;
    margin:0!important;
  }
}
@media(min-width:1101px) and (max-width:1380px){
  body.ab-v3 .ab-v3-hero-copy{max-width:calc(100% - 230px)}
  body.ab-v3 .ab-v3-hero-copy h1{font-size:clamp(36px,4.2vw,54px)!important}
}
"""


def install_css() -> None:
    path = ROOT / CSS_REL
    if not path.exists():
        raise RuntimeError(f"Catalogue/dashboard hotfix target missing: {CSS_REL}")
    text = path.read_text(encoding="utf-8")
    changed = False
    if MARKER not in text:
        text = text.rstrip() + MOBILE_FIX + "\n"
        changed = True
    if DASHBOARD_MARKER not in text:
        text = text.rstrip() + DASHBOARD_FIX + "\n"
        changed = True
    if changed:
        path.write_text(text, encoding="utf-8")


def bust_css_cache() -> None:
    path = ROOT / BASE_REL
    if not path.exists():
        raise RuntimeError(f"Dashboard cache-bust target missing: {BASE_REL}")
    text = path.read_text(encoding="utf-8")
    pattern = r'(/static/css/ab-bau-v3-finance-mobile-pdf-hotfix\.css\?v=)[^\"\']+'
    if not re.search(pattern, text):
        raise RuntimeError("Dashboard cache-bust link for final V3 CSS is missing")
    text = re.sub(pattern, rf'\g<1>{CACHE_VERSION}', text)
    path.write_text(text, encoding="utf-8")


def install_settings_logo_multipart_fix() -> None:
    """Ensure the Texte & Layout form actually transmits selected logo/header files."""
    path = ROOT / SETTINGS_REL
    if not path.exists():
        raise RuntimeError(f"Settings upload target missing: {SETTINGS_REL}")
    text = path.read_text(encoding="utf-8")
    layout_marker = '<input type="hidden" name="section" value="layout">'
    marker_pos = text.find(layout_marker)
    if marker_pos < 0:
        raise RuntimeError("Settings logo multipart fix: layout form marker missing")
    form_start = text.rfind("<form", 0, marker_pos)
    form_end = text.find(">", form_start)
    if form_start < 0 or form_end < 0:
        raise RuntimeError("Settings logo multipart fix: layout form bounds missing")
    opening = text[form_start:form_end + 1]
    if 'enctype="multipart/form-data"' not in opening:
        opening = opening[:-1] + ' enctype="multipart/form-data" data-ab-logo-multipart-fix="20260908">'
        text = text[:form_start] + opening + text[form_end + 1:]
    elif "data-ab-logo-multipart-fix" not in opening:
        opening = opening[:-1] + ' data-ab-logo-multipart-fix="20260908">'
        text = text[:form_start] + opening + text[form_end + 1:]
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

    def test_layout_form_posts_uploaded_logo_as_multipart(self):
        template = (ROOT / "templates/rebuild/tooltime_settings.html").read_text(encoding="utf-8")
        marker = '<input type="hidden" name="section" value="layout">'
        marker_pos = template.index(marker)
        form_start = template.rfind("<form", 0, marker_pos)
        form_end = template.index(">", form_start)
        opening = template[form_start:form_end + 1]
        self.assertIn('enctype="multipart/form-data"', opening)
        self.assertIn('data-ab-logo-multipart-fix="20260908"', opening)

    def test_dashboard_hero_keeps_greeting_and_kpis_in_separate_flow_rows(self):
        css = (ROOT / "static/css/ab-bau-v3-finance-mobile-pdf-hotfix.css").read_text(encoding="utf-8")
        self.assertIn("A+BAU V3 DASHBOARD HERO FLOW FIX 2026-09-08", css)
        self.assertIn("grid-template-rows:auto auto!important", css)
        self.assertIn("body.ab-v3 .ab-v3-metrics", css)
        self.assertIn("position:relative!important", css)
        self.assertIn("inset:auto!important", css)

    def test_dashboard_hotfix_css_is_cache_busted(self):
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        self.assertIn("ab-bau-v3-finance-mobile-pdf-hotfix.css?v=20260908-finance-mobile-pdf-4", base)
''',
        encoding="utf-8",
    )


def guard() -> None:
    css = (ROOT / CSS_REL).read_text(encoding="utf-8")
    if MARKER not in css or "body.ab-apex .ttc-table thead{display:none!important}" not in css:
        raise RuntimeError("Catalogue mobile header overflow guard failed")
    for marker in (
        DASHBOARD_MARKER,
        "grid-template-rows:auto auto!important",
        "body.ab-v3 .ab-v3-metrics",
        "position:relative!important",
        "inset:auto!important",
    ):
        if marker not in css:
            raise RuntimeError(f"Dashboard hero flow guard failed: {marker}")

    base = (ROOT / BASE_REL).read_text(encoding="utf-8")
    if f"ab-bau-v3-finance-mobile-pdf-hotfix.css?v={CACHE_VERSION}" not in base:
        raise RuntimeError("Dashboard hero hotfix CSS cache version was not installed")

    settings = (ROOT / SETTINGS_REL).read_text(encoding="utf-8")
    layout_marker = '<input type="hidden" name="section" value="layout">'
    marker_pos = settings.find(layout_marker)
    form_start = settings.rfind("<form", 0, marker_pos)
    form_end = settings.find(">", form_start)
    opening = settings[form_start:form_end + 1] if marker_pos >= 0 and form_start >= 0 and form_end >= 0 else ""
    if 'enctype="multipart/form-data"' not in opening or 'data-ab-logo-multipart-fix="20260908"' not in opening:
        raise RuntimeError("Settings logo upload form is not multipart; selected files would be dropped")


def main() -> None:
    install_css()
    bust_css_cache()
    install_settings_logo_multipart_fix()
    install_test()
    guard()
    print(f"{MARKER}: mobile catalogue table header removed from layout; desktop header preserved.")
    print(f"{UPLOAD_MARKER}: Texte & Layout now submits logo/header uploads as multipart form data.")
    print(f"{DASHBOARD_MARKER}: dashboard greeting and KPI strip now remain in separate layout rows.")


if __name__ == "__main__":
    main()
