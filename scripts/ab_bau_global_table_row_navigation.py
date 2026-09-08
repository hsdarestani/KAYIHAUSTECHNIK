from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU GLOBAL TABLE ROW NAVIGATION 2026-09-08"
VERSION = "20260908-table-row-nav-1"
BASE_REL = "templates/rebuild/base.html"
JS_REL = "static/js/ab-bau-table-row-navigation.js"
CSS_REL = "static/css/ab-bau-table-row-navigation.css"
TEST_REL = "tests/test_ab_bau_global_table_row_navigation.py"

JS = r'''// A+BAU GLOBAL TABLE ROW NAVIGATION 2026-09-08
(() => {
  'use strict';

  const ROW_SELECTOR = 'table tbody tr';
  const INTERACTIVE_SELECTOR = [
    'a', 'button', 'input', 'select', 'textarea', 'label', 'summary', 'details',
    '[role="button"]', '[contenteditable]', '[data-row-click-ignore]', '.no-row-click'
  ].join(',');
  const EXPLICIT_ATTRS = ['data-row-href', 'data-detail-url', 'data-edit-url', 'data-href', 'data-url'];
  const currentRoot = location.pathname.split('/').filter(Boolean)[0] || '';
  let refreshQueued = false;

  const normalize = raw => {
    if (!raw) return null;
    try {
      const url = new URL(String(raw), location.href);
      if (url.origin !== location.origin) return null;
      if (!/^https?:$/.test(url.protocol)) return null;
      return url;
    } catch (_) {
      return null;
    }
  };

  const rootOf = url => url.pathname.split('/').filter(Boolean)[0] || '';

  const unsafe = (node, url) => {
    const href = `${url.pathname}${url.search}`.toLowerCase();
    const label = [
      node?.textContent || '', node?.getAttribute?.('title') || '', node?.getAttribute?.('aria-label') || ''
    ].join(' ').toLowerCase();
    const haystack = `${href} ${label}`;
    if (node?.hasAttribute?.('download')) return true;
    if (/\.(pdf|csv|xlsx?|zip)(?:$|[?#])/.test(url.pathname.toLowerCase())) return true;
    return /(delete|remove|destroy|loeschen|löschen|storno|cancel|archive|trash|download|export|print|pdf)/.test(haystack);
  };

  const score = (node, url, explicit = false) => {
    let value = explicit ? 400 : 0;
    const targetRoot = rootOf(url);
    const path = url.pathname.toLowerCase();
    const label = [
      node?.textContent || '', node?.getAttribute?.('title') || '', node?.getAttribute?.('aria-label') || ''
    ].join(' ').toLowerCase();

    if (currentRoot && targetRoot === currentRoot) value += 220;
    if (node?.matches?.('[data-row-target],[data-detail-link]')) value += 300;
    if (/(open|view|detail|edit|bearbeiten|öffnen|oeffnen|anzeigen)/.test(`${path} ${label}`)) value += 120;
    if (node?.closest?.('[data-row-actions],.ttq-actions,.tti-actions,.ttc-actions,.actions,.menu,.dropdown,[role="menu"]')) value += 45;
    if (currentRoot && targetRoot && targetRoot !== currentRoot && /^(customers?|contacts?|projects?)$/.test(targetRoot)) value -= 160;
    if (url.pathname === location.pathname && url.search === location.search) value -= 300;
    return value;
  };

  const candidates = row => {
    const result = [];
    const seen = new Set();
    const push = (node, raw, explicit = false) => {
      const url = normalize(raw);
      if (!url || unsafe(node, url)) return;
      const key = url.href;
      if (seen.has(key)) return;
      seen.add(key);
      result.push({href: key, score: score(node, url, explicit)});
    };

    for (const attr of EXPLICIT_ATTRS) {
      if (row.hasAttribute(attr)) push(row, row.getAttribute(attr), true);
    }
    row.querySelectorAll('[data-row-href],[data-detail-url],[data-edit-url],[data-href],[data-url]').forEach(node => {
      for (const attr of EXPLICIT_ATTRS) {
        if (node.hasAttribute(attr)) push(node, node.getAttribute(attr), true);
      }
    });
    row.querySelectorAll('a[href]').forEach(anchor => push(anchor, anchor.getAttribute('href'), false));
    return result.sort((a, b) => b.score - a.score);
  };

  const destination = row => {
    const rows = candidates(row);
    if (!rows.length) return null;
    if (rows[0].score >= 100) return rows[0].href;
    if (rows.length === 1 && rows[0].score > -100) return rows[0].href;
    return null;
  };

  const resetOwnedA11y = row => {
    row.classList.remove('ab-row-clickable');
    delete row.dataset.abResolvedRowHref;
    if (row.dataset.abRowTabindexOwned === '1') {
      row.removeAttribute('tabindex');
      delete row.dataset.abRowTabindexOwned;
    }
    if (row.dataset.abRowRoleOwned === '1') {
      row.removeAttribute('role');
      delete row.dataset.abRowRoleOwned;
    }
  };

  const prepare = row => {
    const href = destination(row);
    if (!href) {
      resetOwnedA11y(row);
      return;
    }
    row.dataset.abResolvedRowHref = href;
    row.classList.add('ab-row-clickable');
    if (!row.hasAttribute('tabindex')) {
      row.tabIndex = 0;
      row.dataset.abRowTabindexOwned = '1';
    }
    if (!row.hasAttribute('role')) {
      row.setAttribute('role', 'link');
      row.dataset.abRowRoleOwned = '1';
    }
  };

  const refresh = root => {
    if (root?.matches?.(ROW_SELECTOR)) prepare(root);
    root?.querySelectorAll?.(ROW_SELECTOR).forEach(prepare);
  };

  const scheduleRefresh = () => {
    if (refreshQueued) return;
    refreshQueued = true;
    requestAnimationFrame(() => {
      refreshQueued = false;
      refresh(document);
    });
  };

  const selectionActive = () => {
    const selection = window.getSelection?.();
    return Boolean(selection && !selection.isCollapsed && selection.toString().trim());
  };

  const openRow = (row, event) => {
    const href = row.dataset.abResolvedRowHref || destination(row);
    if (!href) return false;
    if (event?.ctrlKey || event?.metaKey) {
      window.open(href, '_blank', 'noopener');
    } else {
      window.location.assign(href);
    }
    return true;
  };

  document.addEventListener('click', event => {
    if (event.defaultPrevented || event.button !== 0) return;
    const target = event.target instanceof Element ? event.target : event.target?.parentElement;
    if (!target || target.closest(INTERACTIVE_SELECTOR) || selectionActive()) return;
    const row = target.closest(ROW_SELECTOR);
    if (!row || !row.classList.contains('ab-row-clickable')) return;
    openRow(row, event);
  });

  document.addEventListener('keydown', event => {
    if (event.defaultPrevented || event.key !== 'Enter') return;
    const target = event.target instanceof Element ? event.target : null;
    if (!target || !target.matches(ROW_SELECTOR) || !target.classList.contains('ab-row-clickable')) return;
    if (target.closest(INTERACTIVE_SELECTOR)) return;
    event.preventDefault();
    openRow(target, event);
  });

  const observer = new MutationObserver(scheduleRefresh);
  observer.observe(document.documentElement, {childList: true, subtree: true, attributes: true, attributeFilter: ['href', ...EXPLICIT_ATTRS]});

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => refresh(document), {once: true});
  } else {
    refresh(document);
  }
})();
'''

CSS = r'''/* A+BAU GLOBAL TABLE ROW NAVIGATION 2026-09-08 */
table tbody tr.ab-row-clickable{cursor:pointer}
table tbody tr.ab-row-clickable:focus-visible{outline:2px solid currentColor;outline-offset:-2px}
'''


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Global table-row navigation target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def install_assets() -> None:
    write(JS_REL, JS)
    write(CSS_REL, CSS)


def patch_base() -> None:
    text = read(BASE_REL)
    # Idempotently replace an older copy if this installer is run more than once.
    text = re.sub(r'\n?<link[^>]*data-ab-table-row-navigation-css[^>]*>\n?', '\n', text)
    text = re.sub(r'\n?<script[^>]*data-ab-table-row-navigation(?:=[^ >]+)?[^>]*></script>\n?', '\n', text)

    if "{% static " not in text and "{% load static %}" not in text:
        text = "{% load static %}\n" + text

    css_tag = f'<link rel="stylesheet" href="{{% static \'css/ab-bau-table-row-navigation.css\' %}}?v={VERSION}" data-ab-table-row-navigation-css>'
    js_tag = f'<script src="{{% static \'js/ab-bau-table-row-navigation.js\' %}}?v={VERSION}" defer data-ab-table-row-navigation></script>'

    if "</head>" not in text or "</body>" not in text:
        raise RuntimeError("Global table-row navigation base anchors missing")
    text = text.replace("</head>", f"{css_tag}\n</head>", 1)
    text = text.replace("</body>", f"{js_tag}\n</body>", 1)
    write(BASE_REL, text)


def install_tests() -> None:
    write(TEST_REL, f'''from pathlib import Path\nfrom django.test import SimpleTestCase\n\nROOT = Path(__file__).resolve().parents[1]\n\n\nclass ABauGlobalTableRowNavigationTests(SimpleTestCase):\n    def test_global_runtime_is_cache_busted_once(self):\n        base = (ROOT / "{BASE_REL}").read_text(encoding="utf-8")\n        self.assertEqual(base.count("data-ab-table-row-navigation-css"), 1)\n        self.assertEqual(base.count("data-ab-table-row-navigation></script>"), 1)\n        self.assertIn("ab-bau-table-row-navigation.css\\' %}}?v={VERSION}", base)\n        self.assertIn("ab-bau-table-row-navigation.js\\' %}}?v={VERSION}", base)\n\n    def test_rows_open_records_without_hijacking_native_controls(self):\n        js = (ROOT / "{JS_REL}").read_text(encoding="utf-8")\n        for required in (\n            "{MARKER}",\n            "table tbody tr",\n            "data-row-href",\n            "INTERACTIVE_SELECTOR",\n            "window.location.assign",\n            "window.open",\n            "MutationObserver",\n            "event.key !== 'Enter'",\n            "url.origin !== location.origin",\n            "delete|remove|destroy",\n            "download|export|print|pdf",\n        ):\n            self.assertIn(required, js)\n\n    def test_clickable_rows_have_pointer_and_keyboard_focus(self):\n        css = (ROOT / "{CSS_REL}").read_text(encoding="utf-8")\n        self.assertIn(".ab-row-clickable", css)\n        self.assertIn("cursor:pointer", css)\n        self.assertIn(":focus-visible", css)\n''')


def guard() -> None:
    base = read(BASE_REL)
    js = read(JS_REL)
    css = read(CSS_REL)
    for required in (
        f"ab-bau-table-row-navigation.css' %}}?v={VERSION}",
        f"ab-bau-table-row-navigation.js' %}}?v={VERSION}",
        "data-ab-table-row-navigation-css",
        "data-ab-table-row-navigation></script>",
    ):
        if required not in base:
            raise RuntimeError(f"Global table-row navigation base guard failed: {required}")
    if base.count("data-ab-table-row-navigation-css") != 1 or base.count("data-ab-table-row-navigation></script>") != 1:
        raise RuntimeError("Global table-row navigation assets were linked more than once")
    for required in (MARKER, "table tbody tr", "INTERACTIVE_SELECTOR", "window.location.assign", "MutationObserver"):
        if required not in js:
            raise RuntimeError(f"Global table-row navigation runtime guard failed: {required}")
    if "cursor:pointer" not in css:
        raise RuntimeError("Global table-row navigation cursor guard failed")


def main() -> None:
    install_assets()
    patch_base()
    install_tests()
    guard()
    print(f"{MARKER}: full record rows now open their detail view while native row controls remain independent.")


if __name__ == "__main__":
    main()
