from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "tests" / "test_android_voice_capture_hotfix.py"
MARKER = "A+Bau semantic field voice cache contract 2026-08-18"

if not TEST.exists():
    raise RuntimeError("Android voice cache regression test is missing")

text = TEST.read_text(encoding="utf-8")
old_variants = (
    '            self.assertTrue("20260811-7" in text or "20260812-runtime-2" in text or "20260818-scope-sidebar-ui-1" in text)\n',
    '            self.assertTrue("20260811-7" in text or "20260812-runtime-2" in text)\n',
    '            self.assertIn("20260811-7", text)\n',
)
replacement = (
    '            self.assertRegex(text, r"field-authorization\\.js.*\\?v=[0-9A-Za-z._-]+")\n'
    '            self.assertRegex(text, r"field-authorization\\.css.*\\?v=[0-9A-Za-z._-]+")\n'
)

if replacement not in text:
    for old in old_variants:
        if old in text:
            text = text.replace(old, replacement, 1)
            break
    else:
        raise RuntimeError("Android voice cache assertion changed; refusing to weaken an unknown test contract")

TEST.write_text(text, encoding="utf-8")
verify = TEST.read_text(encoding="utf-8")
if "field-authorization\\.js.*\\?v=" not in verify or "field-authorization\\.css.*\\?v=" not in verify:
    raise RuntimeError("Semantic field voice cache contract was not installed")

print(f"{MARKER}: field voice assets must remain cache-busted without coupling them to the global KI asset version.")
