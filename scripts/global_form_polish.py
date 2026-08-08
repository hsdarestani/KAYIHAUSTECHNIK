from __future__ import annotations

import re
from pathlib import Path

CSS_MARKER = "/* KAYI GLOBAL FORM SYSTEM */"
JS_MARKER = "// KAYI GLOBAL FORM SYSTEM"
ASSET_VERSION = "20260809-0115"
CACHE_NAME = "kayi-shell-v21-20260809"


def replace_regex(path: str, pattern: str, replacement: str, *, optional: bool = False) -> None:
    target = Path(path)
    if not target.exists():
        if optional:
            return
        raise RuntimeError(f"Global form target is missing: {path}")
    text = target.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        if optional:
            return
        raise RuntimeError(f"Global form cache-bust pattern did not match in {path}: {pattern}")
    target.write_text(updated, encoding="utf-8")


css_path = Path("static/css/app.css")
css = css_path.read_text(encoding="utf-8")
if CSS_MARKER not in css:
    css += r'''

/* KAYI GLOBAL FORM SYSTEM */
:root {
  --kayi-form-gap: 16px;
  --kayi-form-radius: 18px;
  --kayi-field-radius: 11px;
  --kayi-field-height: 44px;
}
.kayi-form-polished:not(.kayi-form-compact):not(.event-form-refined) {
  width: min(100%, 1120px);
  margin-inline: auto;
}
.kayi-form-polished:not(.kayi-form-compact):not(.kayi-form-in-card):not(.event-form-refined) {
  padding: 22px;
  border: 1px solid var(--border, #dfe6ef);
  border-radius: var(--kayi-form-radius);
  background: var(--surface, #fff);
  box-shadow: 0 12px 34px rgba(28, 47, 78, .055);
}
.kayi-form-polished.kayi-form-in-card:not(.event-form-refined) {
  padding: 0;
  border: 0;
  background: transparent;
  box-shadow: none;
}
.kayi-balanced-grid,
.kayi-form-polished.kayi-direct-grid:not(.kayi-form-compact) {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--kayi-form-gap);
  align-items: start;
}
.kayi-form-polished .kayi-field {
  min-width: 0;
  margin: 0;
}
.kayi-form-polished .kayi-field-full,
.kayi-form-polished .kayi-form-actions,
.kayi-form-polished .errorlist,
.kayi-form-polished .nonfield,
.kayi-form-polished .non-field-errors {
  grid-column: 1 / -1;
}
.kayi-form-polished .kayi-field > label,
.kayi-form-polished label.kayi-field,
.kayi-form-polished .kayi-field-label {
  color: var(--text, #172033);
  font-size: 12.5px;
  font-weight: 750;
}
.kayi-form-polished .kayi-field > label:not(.kayi-choice-row),
.kayi-form-polished label.kayi-field:not(.kayi-choice-field) {
  display: grid;
  gap: 7px;
}
.kayi-form-polished input:not([type="checkbox"]):not([type="radio"]):not([type="hidden"]):not([type="submit"]):not([type="button"]),
.kayi-form-polished select,
.kayi-form-polished textarea,
.kayi-form-polished .form-control {
  width: 100%;
  min-width: 0;
  min-height: var(--kayi-field-height);
  padding: 10px 12px;
  border: 1px solid var(--border, #d9e1ec);
  border-radius: var(--kayi-field-radius);
  background: var(--surface, #fff);
  color: var(--text, #172033);
  line-height: 1.45;
  transition: border-color .16s ease, box-shadow .16s ease, background .16s ease;
}
.kayi-form-polished input:not([type="checkbox"]):not([type="radio"]):not([type="hidden"]):focus,
.kayi-form-polished select:focus,
.kayi-form-polished textarea:focus,
.kayi-form-polished .form-control:focus {
  outline: none;
  border-color: rgba(31, 115, 210, .64);
  box-shadow: 0 0 0 3px rgba(31, 115, 210, .105);
}
.kayi-form-polished textarea {
  min-height: 118px;
  max-height: 280px;
  resize: vertical;
}
.kayi-form-polished select[multiple] {
  min-height: 106px;
  max-height: 168px;
}
.kayi-form-polished input[type="file"] {
  min-height: 46px;
  padding: 7px 9px;
  background: color-mix(in srgb, var(--surface, #fff) 96%, #eef5ff 4%);
}
.kayi-form-polished input[type="file"]::file-selector-button {
  margin-right: 10px;
  padding: 7px 10px;
  border: 0;
  border-radius: 8px;
  background: rgba(31, 115, 210, .1);
  color: #1769d2;
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}
.kayi-form-polished input::placeholder,
.kayi-form-polished textarea::placeholder {
  color: var(--muted, #8792a5);
  opacity: .92;
}
.kayi-choice-field,
.kayi-form-polished .kayi-choice-row {
  display: flex !important;
  flex-direction: row !important;
  gap: 9px !important;
  align-items: center;
}
.kayi-choice-field {
  min-height: 44px;
  padding: 10px 12px;
  border: 1px solid var(--border, #dfe6ef);
  border-radius: var(--kayi-field-radius);
  background: color-mix(in srgb, var(--surface, #fff) 97%, #eef5ff 3%);
}
.kayi-form-polished input[type="checkbox"],
.kayi-form-polished input[type="radio"] {
  flex: 0 0 auto;
  width: 17px;
  height: 17px;
  accent-color: #1f73d2;
}
.kayi-form-polished .helptext,
.kayi-form-polished .form-text,
.kayi-form-polished small.help,
.kayi-form-polished .kayi-help {
  display: block;
  margin-top: 5px;
  color: var(--muted, #7b879a);
  font-size: 11.5px;
  line-height: 1.45;
}
.kayi-form-polished .errorlist,
.kayi-form-polished .field-error,
.kayi-form-polished .invalid-feedback {
  margin: 6px 0 0;
  padding: 8px 10px;
  border-radius: 9px;
  background: rgba(194, 49, 49, .075);
  color: #ad2e2e;
  font-size: 12px;
  line-height: 1.4;
  list-style: none;
}
.kayi-form-polished fieldset {
  min-width: 0;
  margin: 0;
  padding: 18px;
  border: 1px solid var(--border, #e0e6ef);
  border-radius: 14px;
}
.kayi-form-polished fieldset > legend {
  padding: 0 7px;
  color: var(--text, #172033);
  font-size: 13px;
  font-weight: 800;
}
.kayi-form-polished .kayi-form-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 4px;
  padding-top: 16px;
  border-top: 1px solid var(--border, #e1e7ef);
}
.kayi-form-polished .kayi-form-actions .btn,
.kayi-form-polished .kayi-form-actions button,
.kayi-form-polished .kayi-form-actions input[type="submit"] {
  min-height: 42px;
}
.kayi-form-compact {
  width: 100%;
}
.kayi-form-compact .kayi-balanced-grid,
.kayi-form-compact.kayi-direct-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: end;
}
.kayi-form-compact .kayi-field {
  flex: 1 1 190px;
}
.kayi-form-compact .kayi-field-full {
  flex-basis: 100%;
}
.kayi-form-compact .kayi-form-actions {
  flex: 0 0 auto;
  margin: 0;
  padding: 0;
  border: 0;
}
.kayi-form-polished .searchable-select,
.kayi-form-polished [data-searchable-wrap] {
  width: 100%;
  min-width: 0;
}
@media (max-width: 760px) {
  :root { --kayi-form-gap: 13px; }
  .kayi-balanced-grid,
  .kayi-form-polished.kayi-direct-grid:not(.kayi-form-compact) {
    grid-template-columns: 1fr;
  }
  .kayi-form-polished .kayi-field-full,
  .kayi-form-polished .kayi-form-actions {
    grid-column: auto;
  }
  .kayi-form-polished:not(.kayi-form-compact):not(.kayi-form-in-card):not(.event-form-refined) {
    padding: 16px;
    border-radius: 15px;
  }
  .kayi-form-polished .kayi-form-actions {
    justify-content: stretch;
  }
  .kayi-form-polished .kayi-form-actions .btn,
  .kayi-form-polished .kayi-form-actions button,
  .kayi-form-polished .kayi-form-actions input[type="submit"] {
    flex: 1 1 150px;
  }
}
'''
    css_path.write_text(css, encoding="utf-8")


js_path = Path("static/js/app.js")
js = js_path.read_text(encoding="utf-8")
if JS_MARKER not in js:
    js += r'''

// KAYI GLOBAL FORM SYSTEM
(() => {
  const visibleFieldSelector = [
    'input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="reset"])',
    'select',
    'textarea'
  ].join(',');
  const specializedSelector = [
    '.event-form-refined',
    '[data-inline-room-model]',
    '[data-room-model-editor]',
    '.room-model-editor',
    '.configurator',
    '[data-signature-pad]',
    '.signature-pad',
    '.wizard-shell',
    '.wizard-step'
  ].join(',');
  const navigationSelector = '.topbar, .sidebar, .mobile-nav, nav, [role="navigation"]';

  const fieldWrapper = (control, form) => {
    const candidate = control.closest('label, .form-field, .form-group, .field, .field-row, .input-group');
    return candidate && form.contains(candidate) ? candidate : control.parentElement;
  };

  const markField = (control, form) => {
    const box = fieldWrapper(control, form);
    if (!box || box === form) return null;
    box.classList.add('kayi-field');
    const type = (control.type || '').toLowerCase();
    if (control.tagName === 'TEXTAREA' || type === 'file' || (control.tagName === 'SELECT' && control.multiple)) {
      box.classList.add('kayi-field-full');
    }
    if (type === 'checkbox' || type === 'radio') {
      box.classList.add('kayi-choice-field');
      const label = control.closest('label');
      if (label) label.classList.add('kayi-choice-row');
    }
    return box;
  };

  const markGrids = (form, fieldBoxes) => {
    const parents = new Map();
    fieldBoxes.forEach((box) => {
      if (!box || !box.parentElement || box.parentElement === form) return;
      const parent = box.parentElement;
      if (!parents.has(parent)) parents.set(parent, []);
      parents.get(parent).push(box);
    });
    parents.forEach((boxes, parent) => {
      if (boxes.length >= 2 && !parent.closest(specializedSelector)) {
        parent.classList.add('kayi-balanced-grid');
        if (boxes.length % 2 === 1 && boxes.length >= 3) {
          boxes[boxes.length - 1].classList.add('kayi-field-balance-last');
        }
      }
    });

    const direct = fieldBoxes.filter((box) => box && box.parentElement === form);
    if (direct.length >= 2) form.classList.add('kayi-direct-grid');
  };

  const markActions = (form) => {
    const submitters = Array.from(form.querySelectorAll('button[type="submit"], input[type="submit"], .btn-primary'));
    submitters.forEach((button) => {
      const box = button.closest('.form-actions, .actions, .button-row, .btn-row, .footer-actions') || button.parentElement;
      if (!box || box === form || !form.contains(box)) return;
      const field = box.querySelector(visibleFieldSelector);
      if (!field || field === button) box.classList.add('kayi-form-actions');
    });
  };

  const shouldSkip = (form, controls) => {
    if (form.matches('[data-no-form-polish]')) return 'explicit';
    if (form.matches('.event-form-refined')) return 'event-special';
    if (form.closest(navigationSelector)) return 'navigation';
    if (form.closest(specializedSelector) || form.querySelector(specializedSelector)) return 'specialized';
    if (!controls.length) return 'no-fields';
    return '';
  };

  const polishForm = (form) => {
    if (!(form instanceof HTMLFormElement) || form.dataset.kayiFormAudit) return;
    const controls = Array.from(form.querySelectorAll(visibleFieldSelector)).filter((control) => !control.disabled || control.offsetParent !== null);
    const skipReason = shouldSkip(form, controls);
    if (skipReason) {
      form.dataset.kayiFormAudit = `skip:${skipReason}`;
      return;
    }

    form.dataset.kayiFormAudit = 'polished';
    form.classList.add('kayi-form-polished');
    if (form.closest('.panel, .card, .modal-content, .drawer, .sheet')) form.classList.add('kayi-form-in-card');
    if ((form.method || '').toLowerCase() === 'get' || controls.length <= 2) form.classList.add('kayi-form-compact');

    const boxes = [];
    controls.forEach((control) => {
      const box = markField(control, form);
      if (box && !boxes.includes(box)) boxes.push(box);
    });
    markGrids(form, boxes);
    markActions(form);
    form.querySelectorAll('fieldset').forEach((fieldset) => fieldset.classList.add('kayi-form-fieldset'));
    document.body.classList.add('kayi-has-polished-form');
  };

  const polishAll = (root = document) => {
    if (root instanceof HTMLFormElement) polishForm(root);
    root.querySelectorAll?.('form').forEach(polishForm);
  };

  const start = () => {
    polishAll(document);
    const observer = new MutationObserver((records) => {
      records.forEach((record) => record.addedNodes.forEach((node) => {
        if (node instanceof Element) polishAll(node);
      }));
    });
    observer.observe(document.body, {childList: true, subtree: true});
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true});
  else start();
})();
'''
    js_path.write_text(js, encoding="utf-8")


# Rotate all app-shell asset references after the event-specific refinement has run.
replace_regex(
    "templates/erp/base.html",
    r'href="\{% static \'css/app\.css\' %\}(?:\?v=[^"]*)?"',
    f'href="{{% static \'css/app.css\' %}}?v={ASSET_VERSION}"',
)
replace_regex(
    "templates/erp/base.html",
    r'src="\{% static \'js/app\.js\' %\}(?:\?v=[^"]*)?"',
    f'src="{{% static \'js/app.js\' %}}?v={ASSET_VERSION}"',
)
replace_regex(
    "templates/erp/quote_sign.html",
    r'href="\{% static \'css/app\.css\' %\}(?:\?v=[^"]*)?"',
    f'href="{{% static \'css/app.css\' %}}?v={ASSET_VERSION}"',
    optional=True,
)
replace_regex(
    "static/js/app.js",
    r'navigator\.serviceWorker\.register\("/sw\.js(?:\?v=[^"]*)?",\s*\{[^}]*scope:\s*"/"[^}]*\}\)(?:\.then\([^\n]*\))?\.catch\(\(\)\s*=>\s*\{\}\)',
    f'navigator.serviceWorker.register("/sw.js?v={ASSET_VERSION}", {{scope: "/", updateViaCache: "none"}}).then((registration) => registration.update()).catch(() => {{}})',
)
replace_regex("static/js/sw.js", r'const CACHE = "[^"]+";', f'const CACHE = "{CACHE_NAME}";')
replace_regex(
    "static/js/sw.js",
    r'const ASSETS = \[[^\n]+\];',
    f'const ASSETS = ["/static/css/app.css?v={ASSET_VERSION}", "/static/js/app.js?v={ASSET_VERSION}", "/static/manifest.webmanifest", "/privacy/", "/terms/"];',
)

# Assembly-time inventory: this gives CI/deploy logs a concrete view of every template containing a form.
form_templates = []
for template in sorted(Path("templates").rglob("*.html")):
    try:
        text = template.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    if "<form" in text.lower():
        form_templates.append(str(template))

final_css = css_path.read_text(encoding="utf-8")
final_js = js_path.read_text(encoding="utf-8")
base = Path("templates/erp/base.html").read_text(encoding="utf-8")
if CSS_MARKER not in final_css or JS_MARKER not in final_js:
    raise RuntimeError("Global form design markers are missing after assembly")
if f"app.css' %}}?v={ASSET_VERSION}" not in base or f"app.js' %}}?v={ASSET_VERSION}" not in base:
    raise RuntimeError("Global form cache-bust did not reach the base template")
if not form_templates:
    raise RuntimeError("Global form inventory found no form templates")

print(f"KAYI global form system applied; form templates discovered: {len(form_templates)}")
for template in form_templates:
    print(f"  form-template: {template}")
