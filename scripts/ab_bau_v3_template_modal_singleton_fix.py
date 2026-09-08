from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU V3 TEMPLATE MODAL SINGLETON FIX 2026-09-08"
DOCUMENT_REL = "templates/rebuild/document_editor.html"
FINANCE_JS_REL = "static/js/tooltime-parity-finance.js"
ASSET_REL = "static/js/ab-bau-template-modal-singleton.js"
TEST_REL = "tests/test_ab_bau_v3_template_modal_singleton_fix.py"
FINANCE_VERSION = "20260908-quote-runtime-7"
SINGLETON_VERSION = "20260908-template-singleton-1"

RUNTIME = r'''// A+BAU V3 TEMPLATE MODAL SINGLETON FIX 2026-09-08
(() => {
  'use strict';

  const isTemplateModal = modal => {
    if (!(modal instanceof Element) || !modal.matches('.tt-modal')) return false;
    if (modal.hasAttribute('data-template-modal')) return true;
    if (modal.querySelector('[data-template-choice]')) return true;
    return (modal.querySelector('h1,h2,h3')?.textContent || '').trim() === 'Textvorlage auswählen';
  };

  const templateModals = () => Array.from(document.querySelectorAll('.tt-modal')).filter(isTemplateModal);
  const canonicalTemplateModal = () => document.querySelector('[data-template-modal]') || templateModals()[0] || null;

  const enforceTemplateSingleton = ({open = false, closeOthers = false} = {}) => {
    const keep = canonicalTemplateModal();
    templateModals().forEach(modal => {
      if (modal === keep) return;
      if (!modal.hidden) modal.hidden = true;
      if (modal.getAttribute('aria-hidden') !== 'true') modal.setAttribute('aria-hidden', 'true');
    });
    if (!keep) return null;
    if (keep.hasAttribute('aria-hidden')) keep.removeAttribute('aria-hidden');
    if (open && keep.hidden) keep.hidden = false;
    if (closeOthers) {
      document.querySelectorAll('.tt-modal').forEach(modal => {
        if (modal !== keep && !modal.hidden) modal.hidden = true;
      });
    }
    return keep;
  };

  // This listener intentionally lives in capture phase. The original ToolTime
  // runtime owns the same trigger in bubble phase, and several later compatibility
  // layers can register another owner. One capture-phase owner plus a post-event
  // sweep guarantees that a Vorlagen click can expose exactly one dialog.
  document.addEventListener('click', event => {
    const trigger = event.target.closest('[data-template-open]');
    if (!trigger) return;

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();

    window.ttTemplateKind = trigger.dataset.templateOpen || 'intro';
    const keep = enforceTemplateSingleton({open: true, closeOthers: true});
    if (!keep) return;

    const settle = () => {
      const current = enforceTemplateSingleton({open: true, closeOthers: true});
      if (current && current.hidden) current.hidden = false;
    };
    queueMicrotask(settle);
    setTimeout(settle, 0);
  }, true);

  // If any legacy handler or dynamically injected layer toggles a second template
  // modal after the click, immediately force it back to hidden state.
  const observer = new MutationObserver(() => enforceTemplateSingleton());
  observer.observe(document.documentElement, {
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: ['hidden'],
  });

  enforceTemplateSingleton();
})();
'''


def patch_document_template() -> None:
    path = ROOT / DOCUMENT_REL
    if not path.exists():
        raise RuntimeError(f"Template singleton target missing: {DOCUMENT_REL}")
    text = path.read_text(encoding="utf-8")

    finance_pattern = re.compile(
        r'(<script src="\{% static \'js/tooltime-parity-finance\.js\' %\}\?v=)[^\"]+(" defer></script>)'
    )
    text, count = finance_pattern.subn(rf'\g<1>{FINANCE_VERSION}\g<2>', text, count=1)
    if count != 1:
        raise RuntimeError("Finance runtime script tag/cache key anchor missing")

    singleton_tag = (
        '<script src="{% static \'js/ab-bau-template-modal-singleton.js\' %}'
        f'?v={SINGLETON_VERSION}" defer data-ab-template-singleton></script>'
    )
    singleton_pattern = re.compile(
        r'<script src="\{% static \'js/ab-bau-template-modal-singleton\.js\' %\}\?v=[^\"]+" defer data-ab-template-singleton></script>'
    )
    if singleton_pattern.search(text):
        text = singleton_pattern.sub(singleton_tag, text, count=1)
    else:
        finance_tag = re.search(
            r'<script src="\{% static \'js/tooltime-parity-finance\.js\' %\}\?v=[^\"]+" defer></script>',
            text,
        )
        if not finance_tag:
            raise RuntimeError("Finance runtime script tag missing for singleton insertion")
        insert_at = finance_tag.end()
        text = text[:insert_at] + "\n" + singleton_tag + text[insert_at:]

    path.write_text(text, encoding="utf-8")


def install_runtime_asset() -> None:
    path = ROOT / ASSET_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(RUNTIME, encoding="utf-8")


def install_test() -> None:
    path = ROOT / TEST_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'''from pathlib import Path\nfrom django.test import SimpleTestCase\n\nROOT = Path(__file__).resolve().parents[1]\n\n\nclass ABauV3TemplateModalSingletonFixTests(SimpleTestCase):\n    def test_finance_runtime_is_forced_to_fresh_cache_key(self):\n        template = (ROOT / "{DOCUMENT_REL}").read_text(encoding="utf-8")\n        self.assertIn("tooltime-parity-finance.js' %}}?v={FINANCE_VERSION}", template)\n\n    def test_singleton_runtime_is_linked_once(self):\n        template = (ROOT / "{DOCUMENT_REL}").read_text(encoding="utf-8")\n        self.assertEqual(template.count("data-ab-template-singleton"), 1)\n        self.assertIn("ab-bau-template-modal-singleton.js' %}}?v={SINGLETON_VERSION}", template)\n\n    def test_singleton_runtime_hardens_legacy_duplicate_openers(self):\n        runtime = (ROOT / "{ASSET_REL}").read_text(encoding="utf-8")\n        for required in (\n            "{MARKER}",\n            "event.stopImmediatePropagation()",\n            "enforceTemplateSingleton",\n            "MutationObserver",\n            "queueMicrotask",\n            "setTimeout(settle, 0)",\n            "closeOthers: true",\n        ):\n            self.assertIn(required, runtime)\n\n    def test_existing_quote_editor_runtime_is_still_assembled(self):\n        runtime = (ROOT / "{FINANCE_JS_REL}").read_text(encoding="utf-8")\n        self.assertIn("A+BAU V3 QUOTE EDITOR RUNTIME FIX 2026-09-08", runtime)\n''',
        encoding="utf-8",
    )


def guard() -> None:
    template = (ROOT / DOCUMENT_REL).read_text(encoding="utf-8")
    runtime = (ROOT / ASSET_REL).read_text(encoding="utf-8")
    finance = (ROOT / FINANCE_JS_REL).read_text(encoding="utf-8")

    for required in (
        f"tooltime-parity-finance.js' %}}?v={FINANCE_VERSION}",
        f"ab-bau-template-modal-singleton.js' %}}?v={SINGLETON_VERSION}",
        "data-ab-template-singleton",
    ):
        if required not in template:
            raise RuntimeError(f"Template singleton guard failed: {required}")
    if template.count("data-ab-template-singleton") != 1:
        raise RuntimeError("Template singleton asset must be linked exactly once")
    for required in (MARKER, "event.stopImmediatePropagation()", "MutationObserver", "closeOthers: true"):
        if required not in runtime:
            raise RuntimeError(f"Template singleton runtime guard failed: {required}")
    if "A+BAU V3 QUOTE EDITOR RUNTIME FIX 2026-09-08" not in finance:
        raise RuntimeError("Existing quote editor runtime fix is missing before singleton layer")


def main() -> None:
    install_runtime_asset()
    patch_document_template()
    install_test()
    guard()
    print(f"{MARKER}: Vorlagen uses one canonical modal and both finance/singleton runtimes are cache-busted.")


if __name__ == "__main__":
    main()
