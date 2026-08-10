from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "scripts" / "production_browser_smoke.py"
text = path.read_text(encoding="utf-8")
marker = "# KAYI_STORE_PUBLIC_BROWSER_SMOKE"

if marker not in text:
    main_anchor = '''def main() -> None:\n    base_url = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/") + "/"\n'''
    public_check = main_anchor + '''    # KAYI_STORE_PUBLIC_BROWSER_SMOKE: these URLs are used by App Store Connect,\n    # Google Play Data Safety and users who no longer have the app installed.\n    from playwright.sync_api import sync_playwright\n    with sync_playwright() as playwright:\n        browser = playwright.chromium.launch(headless=True)\n        context = browser.new_context(locale="de-DE", viewport={"width": 430, "height": 932}, is_mobile=True)\n        page = context.new_page()\n        try:\n            for route, required in (("datenschutz/", "Datenschutzerklärung"), ("support/", "KAYI Support"), ("konto-loeschen/", "Konto und Daten löschen")):\n                response = page.goto(urljoin(base_url, route), wait_until="domcontentloaded", timeout=30_000)\n                if response is None or response.status != 200 or required not in page.locator("body").inner_text():\n                    fail(f"public store compliance page /{route} is unavailable or incomplete")\n                if "/login/" in page.url:\n                    fail(f"public store compliance page /{route} unexpectedly requires login")\n        finally:\n            context.close()\n            browser.close()\n'''
    if main_anchor not in text:
        raise RuntimeError("Could not locate production browser smoke main function")
    text = text.replace(main_anchor, public_check, 1)

    settings_anchor = '("/migration/tooltime/", ("Von ToolTime zu KAYI", "Import starten")),'
    if settings_anchor in text and '"KI-Datenverarbeitung"' not in text:
        text = text.replace(settings_anchor, settings_anchor + '\n                ("/settings/next/", ("Einstellungen", "KI-Datenverarbeitung", "Konto und Daten löschen")),', 1)

    path.write_text(text, encoding="utf-8")

print("KAYI production browser smoke now verifies public privacy, support, deletion and in-app privacy settings.")
