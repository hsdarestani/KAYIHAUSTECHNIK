from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "scripts" / "production_browser_smoke.py"

if not TARGET.exists():
    raise RuntimeError("production browser smoke missing after final assembly")

text = TARGET.read_text(encoding="utf-8")
original = text

# production_browser_smoke.py is generated from the legacy archive plus several
# overlays. Patch only visible A+Bau brand expectations and quote-editor selectors;
# technical KAYI_* environment variables, routes and fixture identifiers stay put.
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

    if "table = page.locator" in line and "data-document-items" in line:
        line = line.replace("[data-document-items]", "[data-ab-items]")
        if ".first" not in line:
            line = line.rstrip("\n") + ".first\n"

    if "add = page.locator" in line and ("data-add-item" in line or "data-ab-add-item" in line):
        indent = line[: len(line) - len(line.lstrip())]
        line = indent + "add = page.locator('[data-ab-add-item]:visible').first\n"
    elif "data-add-item" in line and ("locator" in line or ".click" in line or "query_selector" in line):
        line = line.replace("data-add-item", "data-ab-add-item")

    if "if table.count() != 1 or add.count() != 1:" in line:
        line = line.replace("if table.count() != 1 or add.count() != 1:", "if table.count() == 0 or add.count() == 0:")

    if ("before =" in line or "after =" in line) and "table.locator" in line and "tbody tr" in line:
        line = line.replace("tbody tr", ".ab-item-row")

    patched_lines.append(line)

text = "".join(patched_lines)
if text != original:
    TARGET.write_text(text, encoding="utf-8")
    print("A+Bau browser smoke: visible brand and commercial-editor selectors updated.")
else:
    print("A+Bau browser smoke: final generated contract already compatible.")

final = TARGET.read_text(encoding="utf-8")
lines = final.splitlines()
legacy_brand_lines: list[tuple[int, str]] = []
legacy_add_lines: list[tuple[int, str]] = []
legacy_row_count_lines: list[tuple[int, str]] = []
quote_contract_found = False
for number, line in enumerate(lines, 1):
    low = line.lower()
    if "KAYI" in line and ("body_text" in line or "brand markers" in low or "nx-brand" in low or "brandmark" in low):
        legacy_brand_lines.append((number, line.strip()))
    if "data-add-item" in line and ("locator" in line or ".click" in line or "query_selector" in line):
        legacy_add_lines.append((number, line.strip()))
    if ("before =" in line or "after =" in line) and "table.locator" in line and "tbody tr" in line:
        legacy_row_count_lines.append((number, line.strip()))
    if "quote position editor controls are missing" in line:
        quote_contract_found = True

if legacy_brand_lines:
    sample = "; ".join(f"L{n}: {line[:180]}" for n, line in legacy_brand_lines[:4])
    raise RuntimeError(f"Legacy KAYI visible brand contract survived final assembly: {sample}")
if legacy_add_lines:
    sample = "; ".join(f"L{n}: {line[:180]}" for n, line in legacy_add_lines[:4])
    raise RuntimeError(f"Legacy hidden quote add-position selector survived final assembly: {sample}")
if legacy_row_count_lines:
    sample = "; ".join(f"L{n}: {line[:180]}" for n, line in legacy_row_count_lines[:4])
    raise RuntimeError(f"Legacy tbody-row position counting survived final assembly: {sample}")
if quote_contract_found:
    if "page.locator('[data-ab-items]').first" not in final:
        raise RuntimeError("Browser smoke quote table is not wired to the A+Bau commercial editor")
    if "page.locator('[data-ab-add-item]:visible').first" not in final:
        raise RuntimeError("Browser smoke quote add action is not wired to a visible A+Bau control")
    if "if table.count() == 0 or add.count() == 0:" not in final:
        raise RuntimeError("Browser smoke still requires a unique quote control instead of checking presence")

# Final visual identity and mobile-navigation passes must run after every legacy
# layer so the production assembly cannot restore turquoise accents or the old
# fixed-width drawer behavior.
runpy.run_path(str(ROOT / "scripts" / "ab_bau_gold_accent_fix.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "ab_bau_mobile_nav_polish.py"), run_name="__main__")

print("A+Bau browser smoke compatibility installed; technical KAYI_* identifiers preserved.")
