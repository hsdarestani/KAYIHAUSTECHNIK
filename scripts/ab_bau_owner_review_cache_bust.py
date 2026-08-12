from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "20260812-owner-review-1"

base_path = ROOT / "templates" / "rebuild" / "base.html"
review_path = ROOT / "templates" / "rebuild" / "review_detail.html"
css_path = ROOT / "static" / "css" / "kayi-next.css"

for path in (base_path, review_path, css_path):
    if not path.exists():
        raise RuntimeError(f"Owner review cache-bust target missing: {path.relative_to(ROOT)}")

base = base_path.read_text(encoding="utf-8")
base = re.sub(r"(kayi-next\.css' %\}\?v=)[^\"']+", rf"\g<1>{VERSION}", base)
base = re.sub(r"(kayi-next\.js' %\}\?v=)[^\"']+", rf"\g<1>{VERSION}", base)
base_path.write_text(base, encoding="utf-8")

# Older AI regression intentionally validates that the final JS is cache-busted.
# Extend its accepted version family rather than weakening the cache assertion.
test_path = ROOT / "tests" / "test_ai_stateful_entity_chat.py"
if test_path.exists():
    tests = test_path.read_text(encoding="utf-8")
    old = r'self.assertRegex(base, r"kayi-next\.js.*\?v=202608(?:11-[0-9]+|12-runtime-[0-9]+)")'
    new = r'self.assertRegex(base, r"kayi-next\.js.*\?v=202608(?:11-[0-9]+|12-runtime-[0-9]+|12-owner-review-[0-9]+)")'
    if new not in tests:
        if old not in tests:
            raise RuntimeError("Owner review cache regression anchor changed")
        test_path.write_text(tests.replace(old, new, 1), encoding="utf-8")

if "Abrechnungspositionen" not in review_path.read_text(encoding="utf-8"):
    raise RuntimeError("Owner review editor missing before final cache-bust")
if "A+BAU OWNER REVIEW EDITOR 2026-08-12" not in css_path.read_text(encoding="utf-8"):
    raise RuntimeError("Owner review CSS missing before final cache-bust")
if VERSION not in base_path.read_text(encoding="utf-8"):
    raise RuntimeError("Owner review final asset version missing")

print(f"A+Bau owner-review assets finalized with cache version {VERSION} and regression contracts aligned.")
