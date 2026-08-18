from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "20260818-scope-sidebar-ui-1"
MARKER = "A+Bau scope engine final CI/cache alignment 2026-08-18"
UI_MARKER = "A+Bau unmatched catalog and desktop sidebar polish 2026-08-18"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Missing final scope alignment target: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    (ROOT / rel).write_text(text, encoding="utf-8")


def polish_scope_and_sidebar_ui() -> None:
    js_rel = "static/js/kayi-next.js"
    js = read(js_rel)
    if UI_MARKER not in js:
        old = '''      const match = item.catalog_match?.name ? `<small class="nx-ai-scope-match">Katalog: ${escapeHtml(item.catalog_match.name)}</small>` : '';
      row.innerHTML = `<div><b>${escapeHtml(item.label || 'Leistung')}</b><small>${escapeHtml(item.basis || '')}</small>${match}</div><strong>${escapeHtml(qty)} ${escapeHtml(item.unit || '')}</strong>`;
      list.append(row);
'''
        new = f'''      // {UI_MARKER}
      const match = item.catalog_match?.name
        ? `<small class="nx-ai-scope-match">Katalog: ${{escapeHtml(item.catalog_match.name)}}</small>`
        : `<span class="nx-ai-scope-unresolved"><small>Keine sichere Katalogposition gefunden.</small><button type="button" class="nx-ai-scope-choose" data-scope-catalog-choose>Position wählen</button></span>`;
      row.innerHTML = `<div><b>${{escapeHtml(item.label || 'Leistung')}}</b><small>${{escapeHtml(item.basis || '')}}</small>${{match}}</div><strong>${{escapeHtml(qty)}} ${{escapeHtml(item.unit || '')}}</strong>`;
      const chooseCatalog = row.querySelector('[data-scope-catalog-choose]');
      chooseCatalog?.addEventListener('click', () => {{
        const drawer = row.closest('[data-assistant-drawer]') || document;
        const findCatalogButton = (root) => Array.from(root.querySelectorAll('button,[role="button"]')).find((node) => normalize(node.textContent || '').includes(normalize('Katalog wählen')));
        const catalogButton = findCatalogButton(drawer) || (drawer !== document ? findCatalogButton(document) : null);
        if (catalogButton) {{ catalogButton.click(); catalogButton.focus?.(); }}
      }});
      list.append(row);
'''
        if old not in js:
            raise RuntimeError("Scope item renderer anchor changed; refusing to add an ambiguous unresolved-match UI")
        js = js.replace(old, new, 1)
        write(js_rel, js)

    css_rel = "static/css/kayi-next.css"
    css = read(css_rel)
    if UI_MARKER not in css:
        css += f'''

/* {UI_MARKER} */
.nx-ai-scope-unresolved{{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin-top:3px}}
.nx-ai-scope-unresolved small{{color:#80671f!important;font-weight:650}}
.nx-ai-scope-choose{{appearance:none;border:1px solid rgba(173,137,43,.38);background:rgba(173,137,43,.09);color:#6f5516;border-radius:999px;padding:3px 8px;font:inherit;font-size:10.5px;font-weight:850;line-height:1.25;cursor:pointer}}
.nx-ai-scope-choose:hover,.nx-ai-scope-choose:focus-visible{{background:rgba(173,137,43,.17);border-color:rgba(173,137,43,.62);outline:none}}

@media(min-width:861px){{
  body.nx-body{{background:linear-gradient(90deg,#111418 0 var(--nx-sidebar),var(--nx-bg) var(--nx-sidebar) 100%) fixed!important}}
  .nx-shell{{min-height:100vh!important;align-items:stretch}}
  .nx-sidebar{{top:0!important;height:100vh!important;min-height:100vh!important;max-height:100vh!important;background:#111418!important;overflow-y:auto!important;overflow-x:hidden!important;overscroll-behavior:contain;scrollbar-gutter:stable}}
}}
'''
        write(css_rel, css)


def bump_global_assets() -> None:
    rel = "templates/rebuild/base.html"
    text = read(rel)
    text = re.sub(
        r"(kayi-next\.(?:css|js)'\s*%\}\?v=)[^\"'\s<]+",
        rf"\g<1>{VERSION}",
        text,
    )
    if VERSION not in text:
        raise RuntimeError("Could not apply final global scope cache version")
    write(rel, text)


def align_regression_contracts() -> None:
    rel = "tests/test_ai_stateful_entity_chat.py"
    text = read(rel)
    text = text.replace(
        r'kayi-next\.js.*\?v=20260816-owner-commercial-ai-safe-1',
        rf'kayi-next\.js.*\?v={VERSION}',
    )
    if VERSION not in text:
        raise RuntimeError("Stateful AI cache regression contract was not aligned")
    write(rel, text)

    rel = "tests/test_android_voice_capture_hotfix.py"
    text = read(rel)
    old = 'self.assertTrue("20260811-7" in text or "20260812-runtime-2" in text)'
    new = f'self.assertTrue("20260811-7" in text or "20260812-runtime-2" in text or "{VERSION}" in text)'
    if old in text:
        text = text.replace(old, new)
    elif VERSION not in text:
        raise RuntimeError("Android voice cache regression contract changed")
    write(rel, text)

    rel = "tests/test_bo_direct_search.py"
    text = read(rel)
    text = text.replace(
        'self.assertIn("Preislisten-Position suchen", template)',
        'self.assertIn("B&O-Position suchen", template)',
    )
    text = text.replace(
        'self.assertIn("Schnellpositionen mit Preis", template)',
        'self.assertIn("A+Bau-Vorlagen mit Preis", template)',
    )
    if 'self.assertIn("B&O-Position suchen", template)' not in text:
        raise RuntimeError("Direct B&O search regression heading contract changed")
    if 'self.assertIn("A+Bau-Vorlagen mit Preis", template)' not in text:
        raise RuntimeError("Direct B&O search quick-template contract changed")
    write(rel, text)


def install_contract_test() -> None:
    write(
        "tests/test_ab_bau_scope_engine_final_alignment.py",
        f'''from pathlib import Path\nfrom django.test import SimpleTestCase\n\n\nclass ScopeEngineFinalAlignmentTests(SimpleTestCase):\n    def test_global_scope_assets_are_cache_busted_to_final_version(self):\n        base = Path("templates/rebuild/base.html").read_text(encoding="utf-8")\n        self.assertIn("kayi-next.css' %}}?v={VERSION}", base)\n        self.assertIn("kayi-next.js' %}}?v={VERSION}", base)\n\n    def test_direct_bo_search_contract_matches_current_specialized_ui(self):\n        editor = Path("templates/rebuild/document_editor.html").read_text(encoding="utf-8")\n        self.assertIn("B&O-Position suchen", editor)\n        self.assertIn("A+Bau-Vorlagen mit Preis", editor)\n        self.assertIn("data-bo-direct-search", editor)\n\n    def test_scope_completion_behavior_tests_are_still_present(self):\n        test = Path("tests/test_ab_bau_scope_engine_completion.py").read_text(encoding="utf-8")\n        for needle in ("test_abgedeckt_triggers_floor_cover", "test_furniture_number_never_becomes_door_number", "test_bad_catalog_examples_are_rejected", "test_appointment_ui_uses_shared_scope_engine"):\n            self.assertIn(needle, test)\n\n    def test_unmatched_scope_position_is_explicit_and_selectable(self):\n        js = Path("static/js/kayi-next.js").read_text(encoding="utf-8")\n        self.assertIn("Keine sichere Katalogposition gefunden.", js)\n        self.assertIn("data-scope-catalog-choose", js)\n        self.assertIn("Position wählen", js)\n        self.assertIn("Katalog wählen", js)\n\n    def test_desktop_sidebar_background_covers_full_viewport(self):\n        css = Path("static/css/kayi-next.css").read_text(encoding="utf-8")\n        self.assertIn("@media(min-width:861px)", css)\n        self.assertIn("linear-gradient(90deg,#111418 0 var(--nx-sidebar)", css)\n        self.assertIn("height:100vh!important", css)\n        self.assertIn("overflow-y:auto!important", css)\n''',
    )


def guard() -> None:
    checks = {
        "templates/rebuild/base.html": [VERSION],
        "static/js/kayi-next.js": [UI_MARKER, "Keine sichere Katalogposition gefunden.", "data-scope-catalog-choose", "Position wählen"],
        "static/css/kayi-next.css": [UI_MARKER, ".nx-ai-scope-unresolved", "@media(min-width:861px)", "linear-gradient(90deg,#111418 0 var(--nx-sidebar)", "overflow-y:auto!important"],
        "tests/test_ai_stateful_entity_chat.py": [VERSION],
        "tests/test_android_voice_capture_hotfix.py": [VERSION],
        "tests/test_bo_direct_search.py": [
            'self.assertIn("B&O-Position suchen", template)',
            'self.assertIn("A+Bau-Vorlagen mit Preis", template)',
        ],
        "tests/test_ab_bau_scope_engine_final_alignment.py": ["ScopeEngineFinalAlignmentTests", "A+Bau-Vorlagen mit Preis", "test_unmatched_scope_position_is_explicit_and_selectable", "test_desktop_sidebar_background_covers_full_viewport"],
    }
    missing = []
    for rel, needles in checks.items():
        text = read(rel)
        for needle in needles:
            if needle not in text:
                missing.append(f"{rel}: {needle}")
    if missing:
        raise RuntimeError("Final scope CI/cache alignment guard failed: " + "; ".join(missing))


def main() -> None:
    polish_scope_and_sidebar_ui()
    bump_global_assets()
    align_regression_contracts()
    install_contract_test()
    guard()
    print(f"{MARKER}: unresolved catalog choices are explicit, desktop sidebar background is continuous, and browser cache version is {VERSION}.")


if __name__ == "__main__":
    main()
