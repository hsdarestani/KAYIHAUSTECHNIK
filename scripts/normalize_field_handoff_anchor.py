from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "templates" / "rebuild" / "appointment_detail.html"
text = path.read_text(encoding="utf-8")
if 'name="report_text"' not in text or "data-completion-form" not in text:
    raise RuntimeError("Active Field Authorization completion form is missing before final handoff layer")
if "data-completion-form data-documentation-form" not in text:
    text = text.replace("data-completion-form", "data-completion-form data-documentation-form", 1)
    path.write_text(text, encoding="utf-8")
print("KAYI active Field Authorization completion form detected and aliased for shared voice runtime.")
