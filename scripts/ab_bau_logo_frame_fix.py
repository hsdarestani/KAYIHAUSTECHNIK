from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU LOGO ONLY SIDEBAR 2026-08-12"
VERSION = "20260811-202"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"A+Bau logo target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_exact(rel: str, old: str, new: str) -> None:
    text = read(rel)
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"A+Bau logo regression anchor changed in {rel}: {old}")
    write(rel, text.replace(old, new, 1))


def patch_markup() -> None:
    rel = "templates/rebuild/base.html"
    text = read(rel)
    pattern = re.compile(
        r'<a class="nx-brand(?:\s+ab-brand)?" href="(?P<href>[^"]+)">.*?</a>',
        flags=re.S,
    )
    match = pattern.search(text)
    if not match:
        raise RuntimeError("Could not locate A+Bau sidebar brand anchor")
    href = match.group("href")
    replacement = (
        f'<a class="nx-brand ab-brand" href="{href}" style="display:flex!important;align-items:center!important;justify-content:center!important;width:100%!important;min-height:126px!important;margin:0!important;padding:8px 12px 18px!important;border:0!important;outline:0!important;background:transparent!important;box-shadow:none!important;border-radius:0!important;text-decoration:none!important;overflow:visible!important">'
        '<img class="ab-brand-logo-only" data-ab-brand-image src="{% static \'brand/ab-bau-logo.png\' %}" alt="A+Bau" style="display:block!important;width:188px!important;height:auto!important;max-width:100%!important;max-height:120px!important;margin:0 auto!important;padding:0!important;border:0!important;outline:0!important;background:transparent!important;box-shadow:none!important;border-radius:0!important;object-fit:contain!important;object-position:center!important">'
        '</a>'
    )
    text = pattern.sub(replacement, text, count=1)
    write(rel, text)


def patch_css() -> None:
    rel = "static/css/kayi-next.css"
    css = read(rel)
    if MARKER not in css:
        css += r'''

/* A+BAU LOGO ONLY SIDEBAR 2026-08-12 */
.nx-sidebar .nx-brand.ab-brand{
  display:flex!important;
  align-items:center!important;
  justify-content:center!important;
  width:100%!important;
  min-height:126px!important;
  margin:0!important;
  padding:8px 12px 18px!important;
  border:0!important;
  outline:0!important;
  background:transparent!important;
  box-shadow:none!important;
  border-radius:0!important;
  text-decoration:none!important;
  overflow:visible!important;
}
.nx-sidebar .nx-brand.ab-brand .ab-brand-logo-only{
  display:block!important;
  width:188px!important;
  height:auto!important;
  max-width:100%!important;
  max-height:120px!important;
  margin:0 auto!important;
  padding:0!important;
  border:0!important;
  outline:0!important;
  background:transparent!important;
  box-shadow:none!important;
  border-radius:0!important;
  object-fit:contain!important;
  object-position:center!important;
}
@media(max-width:860px){
  .nx-sidebar .nx-brand.ab-brand{min-height:116px!important;padding:8px 10px 14px!important}
  .nx-sidebar .nx-brand.ab-brand .ab-brand-logo-only{width:176px!important;max-height:112px!important}
}
'''
    write(rel, css)


def bump_cache() -> None:
    # This helps normal browsers, but the decisive no-frame/size rules are also
    # inline so a later product-layer cache key cannot restore the old 56px box.
    rel = "templates/rebuild/base.html"
    text = read(rel)
    text = re.sub(r"(kayi-next\.css' %\}\?v=)[^\"']+", rf"\g<1>{VERSION}", text)
    text = re.sub(r"(kayi-next\.js' %\}\?v=)[^\"']+", rf"\g<1>{VERSION}", text)
    write(rel, text)


def install_test() -> None:
    write("tests/test_ab_bau_logo_frame.py", r'''import re
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
''')


def align_old_branding_contracts() -> None:
    # The previous mobile test required a separate textual fallback next to the
    # logo. The approved design is image-only, so verify the real image instead.
    patch_exact(
        "tests/test_ab_bau_mobile_navigation.py",
        '        self.assertIn("ab-brand-fallback", base)',
        '        self.assertIn("ab-brand-logo-only", base)\n        self.assertNotIn("ab-brand-fallback", base)',
    )

    # The old commercial test required the sidebar tagline as standalone text.
    # That text is already baked into the supplied logo and must not be duplicated.
    patch_exact(
        "tests/test_ab_bau_tooltime_finance_upgrade.py",
        '        self.assertIn("Alles organisiert. Alles im Griff.", base)',
        '        self.assertIn("ab-brand-logo-only", base)\n        self.assertNotIn("Alles organisiert. Alles im Griff.", base)',
    )


def guard() -> None:
    css = read("static/css/kayi-next.css")
    base = read("templates/rebuild/base.html")
    for needle in (
        MARKER,
        "width:188px!important",
        "object-fit:contain!important",
        "background:transparent!important",
        "border-radius:0!important",
    ):
        if needle not in css:
            raise RuntimeError(f"A+Bau logo-only contract missing: {needle}")
    brand = re.search(r'<a class="nx-brand ab-brand".*?</a>', base, flags=re.S)
    if not brand or "ab-brand-logo-only" not in brand.group(0):
        raise RuntimeError("A+Bau logo-only sidebar markup was not applied")
    if "data-ab-brand-image" not in brand.group(0):
        raise RuntimeError("A+Bau logo image marker is missing")
    if "<strong>" in brand.group(0) or "<small>" in brand.group(0):
        raise RuntimeError("Separate A+Bau sidebar copy still exists beside the logo")
    if "width:188px!important" not in brand.group(0):
        raise RuntimeError("Inline logo sizing contract is missing")


patch_markup()
patch_css()
bump_cache()
install_test()
align_old_branding_contracts()
guard()
print("A+Bau sidebar simplified: only the large uploaded logo remains; no frame and no separate brand text.")
