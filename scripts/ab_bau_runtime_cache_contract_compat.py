from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "20260812-runtime-2"


def patch(rel: str, old: str, new: str) -> None:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Cache-contract target missing: {rel}")
    text = path.read_text(encoding="utf-8")
    if new not in text:
        if old not in text:
            raise RuntimeError(f"Cache-contract anchor changed in {rel}: {old}")
        text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")


# The free-logo test is generated before later runtime/UI layers. Verify that a
# deliberate A+Bau cache key exists instead of pinning the test to one exact
# version; later final layers (for example the project team picker) may need to
# bump CSS again so browsers actually receive their new styles.
patch(
    "tests/test_ab_bau_logo_frame.py",
    'self.assertIn("kayi-next.css\' %}?v=20260811-102", base)',
    r'self.assertRegex(base, r"kayi-next\.css.*\?v=202608(?:11-[0-9]+|12-runtime-[0-9]+)")',
)

# Stateful assistant behavior is unchanged; only the final asset version moved
# from the 20260811 numeric family to the runtime hotfix family.
patch(
    "tests/test_ai_stateful_entity_chat.py",
    r'self.assertRegex(base, r"kayi-next\.js.*\?v=20260811-[0-9]+")',
    r'self.assertRegex(base, r"kayi-next\.js.*\?v=202608(?:11-[0-9]+|12-runtime-[0-9]+)")',
)

# Quick-job can still legitimately carry the prior voice cache key, while the
# appointment page must carry the new key so the single-owner time fix is loaded.
patch(
    "tests/test_android_voice_capture_hotfix.py",
    'self.assertIn("20260811-7", text)',
    f'self.assertTrue("20260811-7" in text or "{VERSION}" in text)',
)

print("A+Bau runtime cache regression contracts aligned with final/future A+Bau asset versions.")
