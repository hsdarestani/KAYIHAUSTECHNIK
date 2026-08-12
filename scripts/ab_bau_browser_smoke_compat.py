from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "scripts" / "production_browser_smoke.py"

if not TARGET.exists():
    raise RuntimeError("production browser smoke missing after final assembly")

text = TARGET.read_text(encoding="utf-8")
original = text

# The browser smoke is assembled from the legacy archive and several overlays.
# Rebrand only visible brand expectations. Never rename KAYI_* environment names,
# technical module identifiers, fixture users, URLs, routes or storage keys.
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

# The former sidebar used a letter badge. A+Bau renders the supplied logo image.
text = text.replace('".nx-brandmark"', '".ab-brand img"')
text = text.replace("'.nx-brandmark'", "'.ab-brand img'")
text = text.replace(".nx-brandmark, .nx-brand strong", ".ab-brand img, .ab-brand strong")
text = text.replace(".nx-brandmark,.nx-brand strong", ".ab-brand img,.ab-brand strong")

if text != original:
    TARGET.write_text(text, encoding="utf-8")
    print("A+Bau browser smoke: visible legacy brand literals updated.")
else:
    print("A+Bau browser smoke: no direct legacy brand literal found at final assembly; diagnostic brand lines follow.")

# Emit only compact source diagnostics into Actions logs so any dynamically-built
# brand assertion can be aligned without dumping credentials or application data.
final = TARGET.read_text(encoding="utf-8")
for number, line in enumerate(final.splitlines(), 1):
    low = line.lower()
    if any(token in low for token in ("brand", "nx-brand", "dashboard missing", "kayi")):
        compact = " ".join(line.strip().split())
        if len(compact) > 360:
            compact = compact[:357] + "..."
        print(f"A+Bau smoke diagnostic L{number}: {compact}")

print("A+Bau browser smoke compatibility stage completed; technical KAYI_* identifiers preserved.")
