from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+Bau PR106 final contract repair 2026-08-16"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Missing final PR106 repair target: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.write_text(text, encoding="utf-8")


def patch_non_destructive_ai_paths() -> None:
    rel = "static/js/kayi-next.js"
    text = read(rel)

    # The assistant has two generations of set_field handling in the assembled app.
    # Both must obey the same non-destructive contract independently. The previous
    # installer used an either/or condition, which left the legacy path destructive
    # whenever the advanced path had already been patched.
    advanced_old = "        if (!setControlValue(field, action.value)) continue;\n"
    advanced_new = "        if (window.ABBauPreserveTypedText?.(field, action.value)) continue;\n        if (!setControlValue(field, action.value)) continue;\n"
    if "window.ABBauPreserveTypedText?.(field, action.value)" not in text:
        if advanced_old not in text:
            raise RuntimeError("Advanced assistant set_field path changed; refusing destructive fallback")
        text = text.replace(advanced_old, advanced_new, 1)

    legacy_old = "        if (field.type === 'checkbox') field.checked = /^(1|true|ja|yes)$/i.test(action.value || '');\n        else field.value = action.value ?? '';\n"
    legacy_new = "        if (field.type === 'checkbox') field.checked = /^(1|true|ja|yes)$/i.test(action.value || '');\n        else { const proposed = action.value ?? ''; if (window.ABBauPreserveTypedText?.(field, proposed)) continue; field.value = proposed; }\n"
    if "ABBAuPreserveTypedText?.(field, proposed)" not in text:
        if legacy_old not in text:
            raise RuntimeError("Legacy assistant set_field path changed; refusing destructive fallback")
        text = text.replace(legacy_old, legacy_new, 1)

    if MARKER not in text:
        text += f"\n// {MARKER}\n"
    write(rel, text)


def patch_scope_wording_and_visible_math() -> None:
    rel = "erp/ai_scope_planner.py"
    text = read(rel)

    # Keep bathroom clarification human and generic: the parent concept is
    # Wasserleitungen; Kalt-/Warmwasser are the dependent positions.
    text = text.replace(
        '"water_lines_change": "Sollen Kalt-/Warmwasserleitungen umgebaut bzw. neu hergestellt werden, oder bleiben die vorhandenen Leitungen bestehen?",',
        '"water_lines_change": "Müssen die Wasserleitungen umgebaut bzw. neu hergestellt werden, oder bleiben die vorhandenen Leitungen bestehen? (Kalt-/Warmwasser)",',
    )

    # Make the requested business heuristic visible as the actual equation the owner
    # gave us: 90 m² × 2,5 = 225 m². More complete L×B×H geometry still wins earlier.
    text = text.replace(
        'return value, f"{_fmt(floor)} m² Grundfläche × {_fmt(height)} m Raumhöhe (Kalkulationsansatz)"',
        'return value, f"{_fmt(floor)} m² × {_fmt(height)}"',
    )
    text = text.replace(
        'return value, f"{_fmt(floor)} m² Wohn-/Grundfläche × {_fmt(WALL_AREA_FACTOR)} Standardfaktor"',
        'return value, f"{_fmt(floor)} m² × {_fmt(WALL_AREA_FACTOR)}"',
    )

    if MARKER not in text:
        text += f"\n# {MARKER}\n"
    write(rel, text)


def align_stale_regression_expectations() -> None:
    # These tests protected old user-visible branding/B&O-only wording. Runtime has
    # intentionally moved to A+Bau and tenant-owned price lists, so the tests must
    # assert the new product contract rather than force legacy labels back into UI.
    replacements = {
        "KAYI Demo": "A+Bau Demo",
        "KAYI Support": "A+Bau Support",
        "KAYI AI CONTROL + SEARCH FIX 2026-08-11": "A+Bau AI CONTROL + SEARCH FIX 2026-08-11",
        "KAYI EVENT FORM UX REGRESSION 2026-08-08": "A+Bau EVENT FORM UX REGRESSION 2026-08-08",
        "KAYI ANDROID VOICE CAPTURE HOTFIX 20260808": "A+Bau ANDROID VOICE CAPTURE HOTFIX 20260808",
        "KAYI GLOBAL FORM VALIDATION 2026-08-11": "A+Bau GLOBAL FORM VALIDATION 2026-08-11",
        "KAYI PROJECT PAGE LAYOUT 2026-08-08": "A+Bau PROJECT PAGE LAYOUT 2026-08-08",
        "B&O-Position suchen": "Preislisten-Position suchen",
    }
    tests_dir = ROOT / "tests"
    if not tests_dir.exists():
        raise RuntimeError("Assembled tests directory missing")
    for path in tests_dir.glob("test_*.py"):
        text = path.read_text(encoding="utf-8")
        updated = text
        for old, new in replacements.items():
            updated = updated.replace(old, new)
        if updated != text:
            path.write_text(updated, encoding="utf-8")


def guard() -> None:
    js = read("static/js/kayi-next.js")
    planner = read("erp/ai_scope_planner.py")
    required_js = (
        "window.ABBauPreserveTypedText?.(field, action.value)",
        "ABBAuPreserveTypedText?.(field, proposed)",
        "KI-Vorschlag",
        "Deine Eingabe",
    )
    missing = [needle for needle in required_js if needle not in js]
    if "Müssen die Wasserleitungen" not in planner:
        missing.append("generic Wasserleitungen follow-up")
    if 'f"{_fmt(floor)} m² × {_fmt(height)}"' not in planner:
        missing.append("floor×height visible equation")
    if 'f"{_fmt(floor)} m² × {_fmt(WALL_AREA_FACTOR)}"' not in planner:
        missing.append("floor×factor visible equation")
    if missing:
        raise RuntimeError("Final PR106 contract guard failed: " + "; ".join(missing))


patch_non_destructive_ai_paths()
patch_scope_wording_and_visible_math()
align_stale_regression_expectations()
guard()
print("A+Bau PR106 final contracts repaired: all KI form paths preserve typed text, scope math is visible, bathroom questions are generic, and regression tests follow current branding/pricing UI.")
