from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "scripts" / "production_browser_smoke.py"

if not TARGET.exists():
    raise RuntimeError("production browser smoke missing after final assembly")

text = TARGET.read_text(encoding="utf-8")
original = text

# production_browser_smoke.py contains a generated/escaped runtime smoke block.
# Update visible brand expectations and the old hidden +Position selector only.
# Keep technical KAYI_* environment names, fixture identifiers and routes untouched.
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

    if "data-add-item" in line and ("locator" in line or ".click" in line or "query_selector" in line):
        line = line.replace("data-add-item", "data-ab-add-item")
    if "data-ab-add-item" in line and "page.locator" in line and "=" in line and ".first" not in line:
        line = line.replace('page.locator("[data-ab-add-item]")', 'page.locator("[data-ab-add-item]").first')
        line = line.replace("page.locator('[data-ab-add-item]')", "page.locator('[data-ab-add-item]').first")

    patched_lines.append(line)

text = "".join(patched_lines)
if text != original:
    TARGET.write_text(text, encoding="utf-8")
    print("A+Bau browser smoke: generated brand and +Position contracts updated.")
else:
    print("A+Bau browser smoke: no legacy visible brand or +Position selector required patching.")

final = TARGET.read_text(encoding="utf-8")
lines = final.splitlines()
legacy_brand_lines = []
legacy_add_lines = []
for number, line in enumerate(lines, 1):
    low = line.lower()
    if "KAYI" in line and ("body_text" in line or "brand markers" in low or "nx-brand" in low or "brandmark" in low):
        legacy_brand_lines.append((number, line.strip()))
    if "data-add-item" in line and ("locator" in line or ".click" in line or "query_selector" in line):
        legacy_add_lines.append((number, line.strip()))
if legacy_brand_lines:
    sample = "; ".join(f"L{n}: {line[:180]}" for n, line in legacy_brand_lines[:4])
    raise RuntimeError(f"Legacy KAYI visible brand contract survived final assembly: {sample}")
if legacy_add_lines:
    sample = "; ".join(f"L{n}: {line[:180]}" for n, line in legacy_add_lines[:4])
    raise RuntimeError(f"Legacy hidden quote add-position selector survived final assembly: {sample}")

# One-shot diagnostic: reveal the exact generated condition around the legacy
# quote-control assertion. This fails during assembly (before dependencies/tests)
# so the next patch can target the real contract rather than guessing.
for index, line in enumerate(lines):
    if "quote position editor controls are missing" in line:
        start = max(0, index - 7)
        end = min(len(lines), index + 3)
        context = " || ".join(f"L{i+1}: {lines[i].strip()}" for i in range(start, end))
        raise RuntimeError(f"A+Bau quote smoke contract diagnostic: {context}")

raise RuntimeError("A+Bau quote smoke diagnostic target was not found in the assembled browser smoke")
