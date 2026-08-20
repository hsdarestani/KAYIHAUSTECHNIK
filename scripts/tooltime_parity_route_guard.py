from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME ROUTE GUARD 2026-08-20"

path = ROOT / "erp" / "rebuild_urls.py"
text = path.read_text(encoding="utf-8")

if "from . import tooltime_parity_views as tooltime_parity" not in text:
    anchor = "from . import rebuild_views as views\n"
    if anchor not in text:
        raise RuntimeError("Import-Anker für ToolTime-Routen fehlt.")
    text = text.replace(anchor, anchor + "from . import tooltime_parity_views as tooltime_parity\n", 1)

pattern = re.compile(r'^\s*path\("settings/next/",\s*[^,]+,\s*name="next-settings"\),\s*$', re.M)
replacement = '    path("settings/next/", tooltime_parity.settings_page, name="next-settings"),'
text, count = pattern.subn(replacement, text, count=1)
if count != 1 and replacement not in text:
    raise RuntimeError("Route settings/next/ konnte nicht eindeutig auf ToolTime umgestellt werden.")

# Es darf genau eine benannte next-settings-Route geben; sonst könnte Django je
# nach Reihenfolge weiterhin eine alte Einstellungsseite ausliefern.
if text.count('name="next-settings"') != 1:
    raise RuntimeError("next-settings ist nicht eindeutig definiert.")
if replacement not in text:
    raise RuntimeError("ToolTime-Einstellungsroute ist nicht final aktiv.")

path.write_text(text, encoding="utf-8")
print(f"{MARKER}: /settings/next/ verwendet verbindlich die deutsche ToolTime-Einstellungsseite.")
