from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "static" / "css" / "kayi-next.css"
MARKER = "A+BAU GOLD ACCENT FIX 2026-08-12"

if not CSS.exists():
    raise RuntimeError("A+Bau assembled stylesheet is missing")

text = CSS.read_text(encoding="utf-8")
if MARKER not in text:
    text += r'''

/* A+BAU GOLD ACCENT FIX 2026-08-12 */
:root{
  --nx-accent:#c9a13b !important;
  --nx-accent-ink:#111315 !important;
}
.nx-nav a.is-active{
  box-shadow:inset 3px 0 0 #c9a13b !important;
}
.nx-control:focus,.next-control:focus,
.nx-search input:focus{
  border-color:#c9a13b !important;
  box-shadow:0 0 0 3px rgba(201,161,59,.14) !important;
}
.nx-btn-accent,.nx-job-actions .accent{
  background:linear-gradient(135deg,#b88b26,#d7b454) !important;
  border-color:#c9a13b !important;
  color:#111315 !important;
}
.nx-stat:after{
  background:linear-gradient(135deg,rgba(201,161,59,.20),rgba(232,234,236,.12)) !important;
}
.nx-job-address:after{
  background:rgba(201,161,59,.17) !important;
}
.nx-quick-icon{
  background:#fbf4df !important;
}
'''
    CSS.write_text(text, encoding="utf-8")

final = CSS.read_text(encoding="utf-8")
for needle in ("--nx-accent:#c9a13b", "box-shadow:inset 3px 0 0 #c9a13b", "rgba(201,161,59,.14)"):
    if needle not in final:
        raise RuntimeError(f"A+Bau gold accent guard missing: {needle}")

print("A+Bau gold accent installed: legacy turquoise UI accent replaced by gold.")
