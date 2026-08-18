from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "20260818-scope-complete-1"
MARKER = "A+Bau scope engine final CI/cache alignment 2026-08-18"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Missing final scope alignment target: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    (ROOT / rel).write_text(text, encoding="utf-8")


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
        f'''from pathlib import Path\nfrom django.test import SimpleTestCase\n\n\nclass ScopeEngineFinalAlignmentTests(SimpleTestCase):\n    def test_global_scope_assets_are_cache_busted_to_final_version(self):\n        base = Path("templates/rebuild/base.html").read_text(encoding="utf-8")\n        self.assertIn("kayi-next.css' %}}?v={VERSION}", base)\n        self.assertIn("kayi-next.js' %}}?v={VERSION}", base)\n\n    def test_direct_bo_search_contract_matches_current_specialized_ui(self):\n        editor = Path("templates/rebuild/document_editor.html").read_text(encoding="utf-8")\n        self.assertIn("B&O-Position suchen", editor)\n        self.assertIn("A+Bau-Vorlagen mit Preis", editor)\n        self.assertIn("data-bo-direct-search", editor)\n\n    def test_scope_completion_behavior_tests_are_still_present(self):\n        test = Path("tests/test_ab_bau_scope_engine_completion.py").read_text(encoding="utf-8")\n        for needle in ("test_abgedeckt_triggers_floor_cover", "test_furniture_number_never_becomes_door_number", "test_bad_catalog_examples_are_rejected", "test_appointment_ui_uses_shared_scope_engine"):\n            self.assertIn(needle, test)\n''',
    )


def guard() -> None:
    checks = {
        "templates/rebuild/base.html": [VERSION],
        "tests/test_ai_stateful_entity_chat.py": [VERSION],
        "tests/test_android_voice_capture_hotfix.py": [VERSION],
        "tests/test_bo_direct_search.py": [
            'self.assertIn("B&O-Position suchen", template)',
            'self.assertIn("A+Bau-Vorlagen mit Preis", template)',
        ],
        "tests/test_ab_bau_scope_engine_final_alignment.py": ["ScopeEngineFinalAlignmentTests", "A+Bau-Vorlagen mit Preis"],
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
    bump_global_assets()
    align_regression_contracts()
    install_contract_test()
    guard()
    print(f"{MARKER}: regression contracts aligned and final browser cache version is {VERSION}.")


if __name__ == "__main__":
    main()
