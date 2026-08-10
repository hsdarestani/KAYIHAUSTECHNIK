from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "templates" / "rebuild" / "appointment_detail.html"
text = path.read_text(encoding="utf-8")
if 'name="report_text"' not in text or "data-completion-form" not in text:
    raise RuntimeError("Active Field Authorization completion form is missing before final handoff layer")
if "data-completion-form data-documentation-form" not in text:
    text = text.replace("data-completion-form", "data-completion-form data-documentation-form", 1)
    path.write_text(text, encoding="utf-8")

# Commercial prices must be resolved after catalog/UI hardening and after the
# Field Authorization overlay has replaced the active technician views. Running
# here keeps Angebot, Rechnung and on-site customer approval on the same B&O-aware
# price resolver before the final global KI/voice layer is installed.
runpy.run_path(str(ROOT / "scripts" / "install_bo_pricing.py"), run_name="__main__")

print("KAYI active Field Authorization completion form detected; shared voice alias and B&O effective pricing installed.")
