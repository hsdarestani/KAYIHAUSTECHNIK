from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "scripts" / "production_browser_smoke.py"
text = path.read_text(encoding="utf-8")

# The upgraded time overview intentionally replaces the old section title
# "Letzte Buchungen" with the more complete "Arbeitszeiten" workspace.
# Keep the smoke test checking the page, but don't pin it to the retired copy.
text = text.replace('"Letzte Buchungen"', '"Arbeitszeiten"')
text = text.replace("'Letzte Buchungen'", "'Arbeitszeiten'")
path.write_text(text, encoding="utf-8")
print("KAYI time overview browser smoke contract updated")
