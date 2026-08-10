from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRADLE = ROOT / "native" / "plugins" / "kayi-room-scanner" / "android" / "build.gradle"
TARGET = "1.54.0"

if not GRADLE.exists():
    raise RuntimeError(f"KAYI room-scanner Gradle file is missing: {GRADLE}")

text = GRADLE.read_text(encoding="utf-8")
pattern = re.compile(r"(com\.google\.ar:core:)([0-9A-Za-z_.-]+)")
updated, count = pattern.subn(rf"\g<1>{TARGET}", text)
if count == 0:
    raise RuntimeError("Could not locate com.google.ar:core dependency in KAYI room scanner")
if f"com.google.ar:core:{TARGET}" not in updated:
    raise RuntimeError("ARCore release dependency upgrade could not be verified")
GRADLE.write_text(updated, encoding="utf-8")
print(f"KAYI ARCore SDK pinned to {TARGET} for current Android/Play release validation.")
