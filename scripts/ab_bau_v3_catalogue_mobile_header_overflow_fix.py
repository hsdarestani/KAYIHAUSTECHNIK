from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU V3 CATALOGUE MOBILE HEADER OVERFLOW FIX 2026-09-08"
UPLOAD_MARKER = "A+BAU V3 SETTINGS LOGO MULTIPART FIX 2026-09-08"
CSS_REL = "static/css/ab-bau-v3-finance-mobile-pdf-hotfix.css"
SETTINGS_REL = "templates/rebuild/tooltime_settings.html"
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
''',
        encoding="utf-8",
    )


def guard() -> None:
    css = (ROOT / CSS_REL).read_text(encoding="utf-8")
    if MARKER not in css or "body.ab-apex .ttc-table thead{display:none!important}" not in css:
        raise RuntimeError("Catalogue mobile header overflow guard failed")

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
    install_settings_logo_multipart_fix()
    install_test()
    guard()
    print(f"{MARKER}: mobile catalogue table header removed from layout; desktop header preserved.")
    print(f"{UPLOAD_MARKER}: Texte & Layout now submits logo/header uploads as multipart form data.")


if __name__ == "__main__":
    main()
