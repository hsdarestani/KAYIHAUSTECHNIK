from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "scripts" / "production_browser_smoke.py"

if not TARGET.exists():
    raise RuntimeError("production browser smoke missing after final assembly")

text = TARGET.read_text(encoding="utf-8")
original = text

# The browser smoke is assembled from the legacy archive and several overlays.
# Rebrand only its *visible brand expectations*. Do not rename KAYI_* environment
# variables, technical module identifiers, fixture users, routes or storage keys.
for old, new in (
    ('"KAYI Haustechnik"', '"A+Bau"'),
    ("'KAYI Haustechnik'", "'A+Bau'"),
    ('"KAYI Next"', '"A+Bau"'),
    ("'KAYI Next'", "'A+Bau'"),
    ('"KAYI"', '"A+Bau"'),
    ("'KAYI'", "'A+Bau'"),
    ("shared KAYI brand markers", "shared A+Bau brand markers"),
    ("KAYI brand markers", "A+Bau brand markers"),
):
    text = text.replace(old, new)

# The former sidebar used a letter badge (.nx-brandmark); A+Bau intentionally
# renders the supplied real logo image inside .ab-brand. Update only selector
# literals in the smoke contract.
text = text.replace('".nx-brandmark"', '".ab-brand img"')
text = text.replace("'.nx-brandmark'", "'.ab-brand img'")

# Some historical smoke versions use selector/text pairs embedded in JS snippets
# passed to Playwright. Cover those narrowly without touching Python identifiers.
text = text.replace(".nx-brandmark, .nx-brand strong", ".ab-brand img, .ab-brand strong")
text = text.replace(".nx-brandmark,.nx-brand strong", ".ab-brand img,.ab-brand strong")

if text == original:
    # A future smoke may already be A+Bau-aware. Treat that as success only when
    # the expected brand is already present; otherwise fail loudly instead of
    # silently skipping a stale contract.
    if "A+Bau" not in text:
        raise RuntimeError("Could not locate legacy brand expectations in production browser smoke")
else:
    TARGET.write_text(text, encoding="utf-8")

final = TARGET.read_text(encoding="utf-8")
if "dashboard missing shared KAYI brand markers" in final:
    raise RuntimeError("Legacy KAYI dashboard brand assertion survived A+Bau smoke compatibility")
if "A+Bau" not in final:
    raise RuntimeError("A+Bau browser-smoke brand expectation missing")

print("A+Bau browser smoke compatibility installed without renaming technical KAYI_* identifiers.")
