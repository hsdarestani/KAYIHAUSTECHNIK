from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "templates" / "rebuild" / "base.html"
VERSION = "20260811-100"

if not TARGET.exists():
    raise RuntimeError("A+Bau base template missing for mobile cache compatibility")

text = TARGET.read_text(encoding="utf-8")
text = re.sub(r"(kayi-next\.css' %\}\?v=)[^\"']+", rf"\g<1>{VERSION}", text)
text = re.sub(r"(kayi-next\.js' %\}\?v=)[^\"']+", rf"\g<1>{VERSION}", text)
TARGET.write_text(text, encoding="utf-8")

final = TARGET.read_text(encoding="utf-8")
if f"kayi-next.js' %}}?v={VERSION}" not in final or f"kayi-next.css' %}}?v={VERSION}" not in final:
    raise RuntimeError("A+Bau mobile asset cache version was not applied")

print(f"A+Bau mobile assets cache-busted with regression-compatible version {VERSION}.")
