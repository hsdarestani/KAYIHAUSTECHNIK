from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "templates" / "rebuild" / "appointment_detail.html"
text = path.read_text(encoding="utf-8")
if 'name="report_text"' not in text:
    raise RuntimeError("Field completion report textarea is missing before final handoff layer")
print("KAYI active field completion template detected; final handoff layer will patch the real Field Authorization flow.")
