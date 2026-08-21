from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REL = "scripts/production_browser_smoke.py"
path = ROOT / REL
text = path.read_text(encoding="utf-8")

old = r'''            for header in ("Angebotsdatum", "Nr.", "Status", "Angebotstitel", "Kunde", "Betrag", "Letzte Änderung"):
                if quote_page.get_by_text(header, exact=True).count() < 1:
                    fail(f"ToolTime-Angebotsspalte fehlt: {header}")
'''
new = r'''            # Use DOM text rather than rendered inner text because the exact
            # responsive ToolTime table intentionally hides lower-priority columns
            # at narrower Chromium viewports. Hidden responsive headers must still
            # exist in the semantic table contract.
            quote_header_text = quote_page.locator("thead").text_content() or ""
            for header in ("Angebotsdatum", "Nr.", "Status", "Angebotstitel", "Kunde", "Betrag", "Letzte Änderung"):
                if header not in quote_header_text:
                    fail(f"ToolTime-Angebotsspalte fehlt im DOM: {header}")
'''

if old in text:
    text = text.replace(old, new, 1)
elif new not in text:
    raise RuntimeError("ToolTime quote header smoke anchor missing")

path.write_text(text, encoding="utf-8")
compile(text, str(path), "exec")
print("ToolTime Quotes Smoke stabilisiert: responsive ausgeblendete Spalten werden semantisch im DOM geprüft.")
