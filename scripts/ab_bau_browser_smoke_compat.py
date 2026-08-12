from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "scripts" / "production_browser_smoke.py"

if not TARGET.exists():
    raise RuntimeError("production browser smoke missing after final assembly")

text = TARGET.read_text(encoding="utf-8")
original = text

# production_browser_smoke.py contains a generated/escaped runtime smoke block.
# Update visible brand expectations and legacy quote-editor selectors only. Keep
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

    # Old ToolTime smoke expected the legacy per-row tax control. A+Bau correctly
    # has one document-level tax selector, so make the smoke assert that instead.
    if "item_tax" in line and ("locator" in line or "query_selector" in line or "count" in line):
        line = line.replace("item_tax", "document_tax_code")

    # The old quote smoke clicks [data-add-item]. A+Bau retains that only as a
    # hidden compatibility marker; real controls use [data-ab-add-item]. There are
    # two visible add buttons, so select the first one for Playwright strict mode.
    if "data-add-item" in line and ("locator" in line or ".click" in line or "query_selector" in line):
        line = line.replace("data-add-item", "data-ab-add-item")
    if "data-ab-add-item" in line and "page.locator" in line and "=" in line and ".first" not in line:
        line = line.replace('page.locator("[data-ab-add-item]")', 'page.locator("[data-ab-add-item]").first')
        line = line.replace("page.locator('[data-ab-add-item]')", "page.locator('[data-ab-add-item]').first")

    patched_lines.append(line)

text = "".join(patched_lines)
if text != original:
    TARGET.write_text(text, encoding="utf-8")
    print("A+Bau browser smoke: generated brand and quote interaction contracts updated.")
else:
    print("A+Bau browser smoke: no legacy visible brand or quote selector required patching.")

final = TARGET.read_text(encoding="utf-8")
legacy_brand_lines = []
legacy_add_lines = []
legacy_row_tax_lines = []
for number, line in enumerate(final.splitlines(), 1):
    low = line.lower()
    if "KAYI" in line and ("body_text" in line or "brand markers" in low or "nx-brand" in low or "brandmark" in low):
        legacy_brand_lines.append((number, line.strip()))
    if "data-add-item" in line and ("locator" in line or ".click" in line or "query_selector" in line):
        legacy_add_lines.append((number, line.strip()))
    if "item_tax" in line and ("locator" in line or "query_selector" in line or "count" in line):
        legacy_row_tax_lines.append((number, line.strip()))
if legacy_brand_lines:
    sample = "; ".join(f"L{n}: {line[:180]}" for n, line in legacy_brand_lines[:4])
    raise RuntimeError(f"Legacy KAYI visible brand contract survived final assembly: {sample}")
if legacy_add_lines:
    sample = "; ".join(f"L{n}: {line[:180]}" for n, line in legacy_add_lines[:4])
    raise RuntimeError(f"Legacy hidden quote add-position selector survived final assembly: {sample}")
if legacy_row_tax_lines:
    sample = "; ".join(f"L{n}: {line[:180]}" for n, line in legacy_row_tax_lines[:4])
    raise RuntimeError(f"Legacy per-row tax smoke selector survived final assembly: {sample}")
if "data-ab-add-item" not in final or "document_tax_code" not in final:
    raise RuntimeError("A+Bau browser smoke is not wired to visible add-position and document-tax controls")

print("A+Bau browser smoke compatibility installed; technical KAYI_* identifiers preserved.")
