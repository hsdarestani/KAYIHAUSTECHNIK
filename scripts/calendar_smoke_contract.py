from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "scripts" / "production_browser_smoke.py"
text = path.read_text(encoding="utf-8")
mark = "# KAYI CALENDAR BROWSER SMOKE 2026-08-11"
if mark not in text:
    anchor = "            # Event form keeps its deliberately tailored design, but is part of the same audit contract.\n"
    if anchor not in text:
        raise RuntimeError("calendar browser-smoke anchor changed")
    block = '''            # KAYI CALENDAR BROWSER SMOKE 2026-08-11\n            for calendar_view in ("day", "week", "month", "list"):\n                response = page.goto(urljoin(base_url, f"appointments/?view={calendar_view}"), wait_until="domcontentloaded", timeout=30_000)\n                if response is None or response.status >= 500:\n                    fail(f"calendar {calendar_view} returned {response.status if response else 'no response'}")\n                if "/login/" in page.url:\n                    fail(f"calendar {calendar_view} unexpectedly redirected to login")\n                calendar_root = page.locator("[data-calendar-view]")\n                if calendar_root.count() != 1:\n                    fail(f"calendar {calendar_view} is missing its calendar root")\n                if calendar_root.get_attribute("data-calendar-view") != calendar_view:\n                    fail(f"calendar requested {calendar_view} but rendered {calendar_root.get_attribute('data-calendar-view')!r}")\n            page.goto(urljoin(base_url, "appointments/?view=week"), wait_until="domcontentloaded", timeout=30_000)\n            if page.locator(".nx-calendar-views").count() != 1:\n                fail("calendar is missing the day/week/month/list switcher")\n            if page.locator(".nx-calendar-filters").count() != 1:\n                fail("calendar is missing employee/project filters")\n\n'''
    text = text.replace(anchor, block + anchor, 1)
    path.write_text(text, encoding="utf-8")
print("calendar browser smoke contract installed")
