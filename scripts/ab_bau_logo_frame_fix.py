from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU FREE LOGO FRAME 2026-08-12"
VERSION = "20260811-102"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"A+Bau logo-frame target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_css() -> None:
    rel = "static/css/kayi-next.css"
    css = read(rel)
    if MARKER not in css:
        css += r'''

/* A+BAU FREE LOGO FRAME 2026-08-12 */
.nx-brand.ab-brand .ab-brand-logo,
.nx-brand.ab-brand > img{
  border:0!important;
  outline:0!important;
  background:transparent!important;
  box-shadow:none!important;
  border-radius:0!important;
  padding:0!important;
}
.nx-brand.ab-brand .ab-brand-logo{
  width:56px!important;
  height:56px!important;
  overflow:visible!important;
  display:grid!important;
  place-items:center!important;
}
.nx-brand.ab-brand .ab-brand-logo img,
.nx-brand.ab-brand > img{
  width:100%!important;
  height:100%!important;
  max-width:56px!important;
  max-height:56px!important;
  object-fit:contain!important;
  object-position:center!important;
  border:0!important;
  outline:0!important;
  background:transparent!important;
  box-shadow:none!important;
  border-radius:0!important;
  padding:0!important;
}
.nx-brand.ab-brand .ab-brand-fallback{
  border:0!important;
  background:transparent!important;
  box-shadow:none!important;
  border-radius:0!important;
}
@media(max-width:860px){
  .nx-brand.ab-brand .ab-brand-logo{width:56px!important;height:56px!important}
  .nx-brand.ab-brand .ab-brand-logo img,.nx-brand.ab-brand > img{max-width:56px!important;max-height:56px!important}
}
'''
    write(rel, css)


def bump_cache() -> None:
    rel = "templates/rebuild/base.html"
    text = read(rel)
    text = re.sub(r"(kayi-next\.css' %\}\?v=)[^\"']+", rf"\g<1>{VERSION}", text)
    text = re.sub(r"(kayi-next\.js' %\}\?v=)[^\"']+", rf"\g<1>{VERSION}", text)
    write(rel, text)


def install_test() -> None:
    write("tests/test_ab_bau_logo_frame.py", r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ABBauLogoFrameTests(SimpleTestCase):
    def test_sidebar_logo_is_free_floating(self):
        css = (ROOT / "static/css/kayi-next.css").read_text(encoding="utf-8")
        self.assertIn("A+BAU FREE LOGO FRAME 2026-08-12", css)
        self.assertIn("border:0!important", css)
        self.assertIn("background:transparent!important", css)
        self.assertIn("box-shadow:none!important", css)
        self.assertIn("border-radius:0!important", css)
        self.assertIn("object-fit:contain!important", css)
        self.assertIn("overflow:visible!important", css)

    def test_logo_cache_is_bumped(self):
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        self.assertIn("kayi-next.css' %}?v=20260811-102", base)
''')


def guard() -> None:
    css = read("static/css/kayi-next.css")
    base = read("templates/rebuild/base.html")
    for needle in (
        MARKER,
        "object-fit:contain!important",
        "overflow:visible!important",
        "background:transparent!important",
        "border-radius:0!important",
    ):
        if needle not in css:
            raise RuntimeError(f"A+Bau free-logo contract missing: {needle}")
    if f"kayi-next.css' %}}?v={VERSION}" not in base:
        raise RuntimeError("A+Bau logo-frame cache version was not applied")


patch_css()
bump_cache()
install_test()
guard()
print("A+Bau sidebar logo freed: no frame, no background panel, no rounded crop; PNG uses contain sizing.")
