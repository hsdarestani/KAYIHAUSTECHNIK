from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "/* KAYI PROJECT FORM LAYOUT 2026-08-11 */"
ASSET_VERSION = "20260811-project3"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Project form layout patch could not find {label}")
    return text.replace(old, new, 1)


def patch_template() -> None:
    path = ROOT / "templates" / "rebuild" / "project_form.html"
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        '<div class="nx-pagehead">',
        '<div class="nx-pagehead nx-project-pagehead">',
        "page header",
    )
    text = replace_once(
        text,
        '<form class="nx-form" method="post">',
        '<form class="nx-form nx-project-form" method="post">',
        "project form",
    )
    text = replace_once(
        text,
        '<section class="nx-card nx-card-pad">',
        '<section class="nx-card nx-card-pad nx-project-card">',
        "project basics card",
    )

    # Earlier assembly layers enhance the customer field with a search box, so
    # never depend on the exact field-loop markup here. We only add a scoped class
    # to the basics header and let stable field order + CSS own the final layout.
    if "nx-project-card-head" not in text:
        pattern = re.compile(r'<div class="nx-card-head"(?P<attrs>[^>]*)><div><h2>Grunddaten</h2>', re.S)
        text, count = pattern.subn(
            r'<div class="nx-card-head nx-project-card-head"\g<attrs>><div><h2>Grunddaten</h2>',
            text,
            count=1,
        )
        if count != 1:
            raise RuntimeError("Project form layout patch could not locate the Grunddaten header")

    path.write_text(text, encoding="utf-8")


def patch_css() -> Path:
    readability = ROOT / "static" / "css" / "kayi-readability.css"
    css_path = readability if readability.exists() else ROOT / "static" / "css" / "kayi-next.css"
    css = css_path.read_text(encoding="utf-8")
    if MARKER not in css:
        css += r'''

/* KAYI PROJECT FORM LAYOUT 2026-08-11 */
/* Scoped late layer: assembled customer search may add controls, but each model
   field remains one .nx-field in ProjectForm order. */
.nx-project-pagehead {
  padding-top: 14px;
  margin-bottom: 22px;
}
.nx-project-pagehead h1 { margin-top: 6px; }
.nx-project-form {
  width: min(100%, 1180px);
  margin-inline: auto;
  gap: 20px;
}
.nx-project-card { padding: 26px 28px; }
.nx-project-card-head {
  padding: 0 0 20px !important;
  align-items: center;
}
.nx-project-card-head > div { min-width: 0; }
.nx-project-card-head .nx-btn {
  min-height: 36px;
  padding: 7px 11px;
  border-radius: 11px;
  background: #f7f6f2;
  flex: 0 0 auto;
}
.nx-project-card .nx-form-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px 24px;
  align-items: start;
}
.nx-project-card .nx-form-grid > .nx-field {
  min-width: 0;
  align-content: start;
  align-self: start;
}
/* ProjectForm order: title, customer, object_location, description,
   priority, manager, members. Put semantically wide controls on their own row. */
.nx-project-card .nx-form-grid > .nx-field:nth-child(1),
.nx-project-card .nx-form-grid > .nx-field:nth-child(4),
.nx-project-card .nx-form-grid > .nx-field:nth-child(7) {
  grid-column: 1 / -1;
}
.nx-project-card .nx-form-grid > .nx-field:nth-child(1) input {
  min-height: 48px !important;
  height: 48px !important;
}
.nx-project-card .nx-form-grid > .nx-field:nth-child(4) textarea {
  min-height: 108px !important;
}
.nx-project-card .nx-form-grid > .nx-field:nth-child(7) select[multiple] {
  min-height: 118px !important;
  max-height: 150px;
}
/* Customer search + select should read as one compact control group, never make
   its grid neighbour stretch to the same height. */
.nx-project-card .nx-form-grid > .nx-field:nth-child(2) {
  gap: 7px;
}
.nx-project-card .nx-form-grid > .nx-field:nth-child(2) input,
.nx-project-card .nx-form-grid > .nx-field:nth-child(2) select,
.nx-project-card .nx-form-grid > .nx-field:nth-child(3) select {
  min-height: 46px;
}
.nx-project-card .nx-form-grid > .nx-field:nth-child(2) small {
  margin-block: 0 2px;
}
.nx-project-form .nx-form-actions {
  padding-top: 20px;
  margin-top: 2px;
}
@media (max-width: 900px) {
  .nx-project-pagehead { padding-top: 10px; }
  .nx-project-card { padding: 21px 20px; }
  .nx-project-card .nx-form-grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }
  .nx-project-card .nx-form-grid > .nx-field:nth-child(1),
  .nx-project-card .nx-form-grid > .nx-field:nth-child(4),
  .nx-project-card .nx-form-grid > .nx-field:nth-child(7) {
    grid-column: auto;
  }
}
@media (max-width: 600px) {
  .nx-project-pagehead { padding-top: 8px; margin-bottom: 18px; }
  .nx-project-card { padding: 18px 16px; border-radius: 18px; }
  .nx-project-card-head {
    align-items: stretch;
    flex-direction: column;
    gap: 12px;
  }
  .nx-project-card-head .nx-btn { width: 100%; }
  .nx-project-form .nx-form-actions {
    display: grid;
    grid-template-columns: 1fr;
  }
  .nx-project-form .nx-form-actions .nx-btn { width: 100%; }
}
'''
        css_path.write_text(css, encoding="utf-8")
    return css_path


def bust_cache(css_path: Path) -> None:
    base = ROOT / "templates" / "rebuild" / "base.html"
    text = base.read_text(encoding="utf-8")
    asset = css_path.name
    pattern = re.compile(rf"(static 'css/{re.escape(asset)}' %\}}\?v=)[^\"']+")
    updated, count = pattern.subn(rf"\g<1>{ASSET_VERSION}", text, count=1)
    if count == 0:
        raw = f"static 'css/{asset}' %}}"
        if raw not in text:
            raise RuntimeError(f"Could not cache-bust {asset} in rebuild/base.html")
        updated = text.replace(raw, raw + f"?v={ASSET_VERSION}", 1)
    base.write_text(updated, encoding="utf-8")


def install_contract() -> None:
    path = ROOT / "tests" / "test_project_form_layout_polish.py"
    path.write_text(r'''from pathlib import Path
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
        self.assertIn("KAYI PROJECT FORM LAYOUT 2026-08-11", css)
        self.assertIn("align-items: start", css)
        self.assertIn(".nx-field:nth-child(1)", css)
        self.assertIn(".nx-field:nth-child(4)", css)
        self.assertIn(".nx-field:nth-child(7)", css)
        self.assertIn("@media (max-width: 600px)", css)
''', encoding="utf-8")


def guard() -> None:
    template = (ROOT / "templates" / "rebuild" / "project_form.html").read_text(encoding="utf-8")
    if template.count("＋ Kunde anlegen") != 1:
        raise RuntimeError("Project form must expose exactly one customer-create action")
    for marker in ("nx-project-pagehead", "nx-project-form", "nx-project-card", "nx-project-card-head"):
        if marker not in template:
            raise RuntimeError(f"Project form scoped layout marker missing: {marker}")


def main() -> None:
    patch_template()
    css_path = patch_css()
    bust_cache(css_path)
    install_contract()
    guard()
    print("KAYI project creation layout polished and guarded.")


if __name__ == "__main__":
    main()
