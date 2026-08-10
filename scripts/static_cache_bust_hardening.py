from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "templates/rebuild/base.html"
text = path.read_text(encoding="utf-8")
for old in ("?v=20260810-4", "?v=20260810-5"):
    text = text.replace(old, "?v=20260810-6")
if "?v=20260810-6" not in text:
    raise RuntimeError("KAYI Next static asset version marker was not found")
path.write_text(text, encoding="utf-8")
print("KAYI Next CSS/JS cache version bumped to 20260810-6.")
