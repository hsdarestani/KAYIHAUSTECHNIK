from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "scripts" / "production_browser_smoke.py"

if not TARGET.exists():
    raise RuntimeError("production browser smoke missing after final assembly")

text = TARGET.read_text(encoding="utf-8")
original = text

# production_browser_smoke.py contains a generated/escaped runtime smoke block.
# Update brand expectations line-by-line so escaped quotes do not matter. Keep
# technical KAYI_* environment names, fixture identifiers and routes untouched.
patched_lines: list[str] = []
for line in text.splitlines(keepends=True):
    low = line.lower()
    is_visible_brand_contract = (
        ("body_text" in line and "KAYI" in line)
        or ("brand markers" in low and "KAYI" in line)
        or ("nx-brand" in low and "KAYI" in line)
        or ("brandmark" in low)
    )
    if is_visible_brand_contract:
        line = line.replace("KAYI Haustechnik", "A+Bau")
        line = line.replace("KAYI Next", "A+Bau")
        line = line.replace("KAYI", "A+Bau")
        line = line.replace(".nx-brandmark", ".ab-brand img")
    patched_lines.append(line)

text = "".join(patched_lines)
if text != original:
    TARGET.write_text(text, encoding="utf-8")
    print("A+Bau browser smoke: generated visible brand contract updated.")
else:
    print("A+Bau browser smoke: no legacy visible brand assertion required patching.")

final = TARGET.read_text(encoding="utf-8")
legacy_brand_lines = []
for number, line in enumerate(final.splitlines(), 1):
    low = line.lower()
    if "KAYI" in line and ("body_text" in line or "brand markers" in low or "nx-brand" in low or "brandmark" in low):
        legacy_brand_lines.append((number, line.strip()))
if legacy_brand_lines:
    sample = "; ".join(f"L{n}: {line[:180]}" for n, line in legacy_brand_lines[:4])
    raise RuntimeError(f"Legacy KAYI visible brand contract survived final assembly: {sample}")

print("A+Bau browser smoke compatibility installed; technical KAYI_* identifiers preserved.")
