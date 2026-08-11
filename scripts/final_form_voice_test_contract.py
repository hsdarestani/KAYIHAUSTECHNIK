from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_required(rel: str, old: str, new: str) -> None:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Missing regression contract: {rel}")
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"Regression contract anchor changed in {rel}: {old}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# Asset versions are intentionally bumped by later UX layers; assert the asset is
# versioned without pinning a stale exact cache number.
replace_required(
    "tests/test_ai_stateful_entity_chat.py",
    '        self.assertIn("20260811-3", base)\n',
    '        self.assertIn("kayi-next.js", base)\n        self.assertRegex(base, r"kayi-next\\.js.*\\?v=20260811-[0-9]+")\n',
)

# The field workflow intentionally moved from the fragile Web Speech API to a
# recorded-audio MediaRecorder + server transcription flow. Keep the parity test
# focused on the capability rather than the obsolete implementation.
replace_required(
    "tests/test_tooltime_rebuild.py",
    '"SpeechRecognition"',
    '"MediaRecorder"',
)

# Correct the final hardening test marker to match the actual dataset property.
replace_required(
    "tests/test_final_form_voice_pricing_hardening.py",
    '"dataGlobalFormErrors"',
    '"dataset.globalFormErrors"',
)

print("KAYI regression contracts updated for cache-busted assets, MediaRecorder voice and global form validation.")
