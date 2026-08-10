from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    "templates/erp/service_assistant.html",
    "templates/erp/price_library.html",
    "templates/erp/project_wizard.html",
    "templates/erp/configurator.html",
    "erp/forms.py",
    "erp/services/ai.py",
    "static/js/app.js",
]
TERMS = (
    "fliese", "material", "search", "suchen", "enter", "selected", "ausgewählt",
    "wizard", "assistent", "depth", "tiefe", "popup", "modal", "dialog",
    "price", "preis", "service", "leistung",
)

print("--- KAYI assembled legacy QA audit ---")
for rel in TARGETS:
    path = ROOT / rel
    if not path.exists():
        print(f"AUDIT {rel}: MISSING")
        continue
    text = path.read_text(encoding="utf-8", errors="replace")
    lowered = text.lower()
    counts = {term: lowered.count(term) for term in TERMS if lowered.count(term)}
    print(f"AUDIT {rel}: bytes={len(text)} counts={counts}")
    shown = 0
    for number, line in enumerate(text.splitlines(), 1):
        low = line.lower()
        if any(term in low for term in TERMS):
            compact = " ".join(line.strip().split())
            if len(compact) > 260:
                compact = compact[:257] + "..."
            print(f"  L{number}: {compact}")
            shown += 1
            if shown >= 18:
                break

ai_path = ROOT / "erp/services/ai.py"
if ai_path.exists():
    lines = ai_path.read_text(encoding="utf-8", errors="replace").splitlines()
    print("AUDIT suggest_catalog_services implementation:")
    for number in range(69, min(116, len(lines) + 1)):
        compact = " ".join(lines[number - 1].strip().split())
        if len(compact) > 320:
            compact = compact[:317] + "..."
        print(f"  AI L{number}: {compact}")
print("--- end legacy QA audit ---")
