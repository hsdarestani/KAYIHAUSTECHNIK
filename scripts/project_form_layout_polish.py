from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "/* KAYI PROJECT FORM LAYOUT 2026-08-11 */"
ASSET_VERSION = "20260811-project2"


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

    # The old customer-create CTA floated in the card header, visually detached
    # from the field it belongs to. Keep the heading clean and move the action
    # next to the customer field below.
    header_pattern = re.compile(
        r'<div class="nx-card-head" style="padding:0 0 16px"><div><h2>Grunddaten</h2><p>(.*?)</p></div>'
        r'<a class="nx-btn nx-btn-ghost" href="\{% url \'next-customer-create\' %\}">＋ Kunde anlegen</a></div>',
        re.S,
    )
    if "nx-project-card-head" not in text:
        text, count = header_pattern.subn(
            r'<div class="nx-card-head nx-project-card-head" style="padding:0 0 16px"><div><h2>Grunddaten</h2><p>\1</p></div></div>',
            text,
            count=1,
        )
        if count != 1:
            raise RuntimeError("Project form layout patch could not normalize basics card header")

    old_loop = '''      <div class="nx-field {% if field.name == 'description' or field.name == 'members' %}nx-field-full{% endif %}"><label for="{{ field.id_for_label }}">{{ field.label }}</label>{{ field }}{{ field.errors }}{% if field.help_text %}<small class="nx-muted">{{ field.help_text }}</small>{% endif %}</div>'''
    new_loop = '''      <div class="nx-field nx-field-{{ field.name }} {% if field.name == 'title' or field.name == 'description' or field.name == 'members' %}nx-field-full{% endif %}">
        {% if field.name == 'customer' %}
        <div class="nx-project-field-head"><label for="{{ field.id_for_label }}">{{ field.label }}</label><a class="nx-project-inline-action" href="{% url 'next-customer-create' %}">＋ Kunde anlegen</a></div>
        {% else %}<label for="{{ field.id_for_label }}">{{ field.label }}</label>{% endif %}
        {{ field }}{{ field.errors }}{% if field.help_text %}<small class="nx-muted">{{ field.help_text }}</small>{% endif %}
      </div>'''
    text = replace_once(text, old_loop, new_loop, "generic project field loop")

    path.write_text(text, encoding="utf-8")


def patch_css() -> Path:
    readability = ROOT / "static" / "css" / "kayi-readability.css"
    css_path = readability if readability.exists() else ROOT / "static" / "css" / "kayi-next.css"
    css = css_path.read_text(encoding="utf-8")
    if MARKER not in css:
        css += r'''

/* KAYI PROJECT FORM LAYOUT 2026-08-11 */
/* Keep the project start compact, balanced and visually tied to its actions. */
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
  align-items: flex-start;
}
.nx-project-card .nx-form-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px 24px;
  align-items: start;
}
.nx-project-card .nx-field {
  min-width: 0;
  align-content: start;
  align-self: start;
}
.nx-project-card .nx-field-title,
.nx-project-card .nx-field-description,
.nx-project-card .nx-field-members {
  grid-column: 1 / -1;
}
.nx-project-card .nx-field-title input {
  min-height: 48px !important;
  height: 48px;
}
.nx-project-card .nx-field-description textarea {
  min-height: 108px !important;
}
.nx-project-card .nx-field-members select[multiple] {
  min-height: 118px !important;
  max-height: 150px;
}
.nx-project-field-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 26px;
}
.nx-project-field-head label {
  margin: 0;
  font-size: 13.5px !important;
  font-weight: 850;
}
.nx-project-inline-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 30px;
  padding: 5px 10px;
  border: 1px solid var(--nx-line, #d9d5cc);
  border-radius: 10px;
  background: #f7f6f2;
  color: var(--nx-ink, #111418);
  font-size: 12.5px !important;
  font-weight: 800;
  line-height: 1.2;
  white-space: nowrap;
  transition: .15s ease;
}
.nx-project-inline-action:hover {
  background: #efede7;
  transform: translateY(-1px);
}
.nx-project-card .nx-field-customer > input,
.nx-project-card .nx-field-customer > select,
.nx-project-card .nx-field-object_location > select {
  min-height: 46px;
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
  .nx-project-card .nx-field-title,
  .nx-project-card .nx-field-description,
  .nx-project-card .nx-field-members {
    grid-column: auto;
  }
}
@media (max-width: 600px) {
  .nx-project-pagehead { padding-top: 8px; margin-bottom: 18px; }
  .nx-project-card { padding: 18px 16px; border-radius: 18px; }
  .nx-project-field-head {
    align-items: stretch;
    flex-direction: column;
    gap: 7px;
  }
  .nx-project-inline-action { width: 100%; min-height: 38px; }
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
        # Late readability stylesheet can be emitted without a query in older
        # assemblies. Add/update a query only on that exact asset reference.
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
        for marker in (
            "nx-project-pagehead",
            "nx-project-form",
            "nx-project-card",
            "nx-project-field-head",
            "nx-project-inline-action",
            "nx-field-{{ field.name }}",
        ):
            self.assertIn(marker, template)
        self.assertIn("field.name == 'title'", template)
        self.assertIn("＋ Kunde anlegen", template)
        self.assertIn("KAYI PROJECT FORM LAYOUT 2026-08-11", css)
        self.assertIn("align-items: start", css)
        self.assertIn(".nx-project-card .nx-field-title", css)
        self.assertIn("@media (max-width: 600px)", css)
''', encoding="utf-8")


def guard() -> None:
    template = (ROOT / "templates" / "rebuild" / "project_form.html").read_text(encoding="utf-8")
    if template.count("＋ Kunde anlegen") != 1:
        raise RuntimeError("Project form must expose exactly one contextual customer-create action")
    if "nx-project-form" not in template or "nx-field-{{ field.name }}" not in template:
        raise RuntimeError("Project form scoped layout markers are missing")


def main() -> None:
    patch_template()
    css_path = patch_css()
    bust_cache(css_path)
    install_contract()
    guard()
    print("KAYI project creation layout polished and guarded.")


if __name__ == "__main__":
    main()
