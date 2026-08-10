from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "scripts/production_browser_smoke.py"
text = path.read_text(encoding="utf-8")
marker = "catalog search Enter and selected-state smoke"
if marker not in text:
    old = '''            if after != before + 1:\n                fail(f"+ Position did not add a row: {before} -> {after}")\n'''
    new = '''            if after != before + 1:\n                fail(f"+ Position did not add a row: {before} -> {after}")\n\n            # catalog search Enter and selected-state smoke\n            catalog_items = page.locator('[data-catalog-item]')\n            if catalog_items.count():\n                first_catalog = catalog_items.first\n                catalog_name = first_catalog.get_attribute('data-name') or first_catalog.inner_text().split('\\n', 1)[0]\n                catalog_search = page.locator('[data-catalog-search]')\n                catalog_search.fill(catalog_name)\n                catalog_search.press('Enter')\n                if '/quotes/new/' not in page.url:\n                    fail(f"catalog Enter navigated away from quote editor: {page.url}")\n                visible_catalog = page.locator('[data-catalog-item]:visible')\n                if visible_catalog.count() < 1:\n                    fail("catalog search hid the expected result")\n                rows_before_catalog = table.locator('tbody tr').count()\n                visible_catalog.first.click()\n                page.wait_for_timeout(100)\n                rows_after_catalog = table.locator('tbody tr').count()\n                if rows_after_catalog != rows_before_catalog + 1:\n                    fail("catalog click did not add a quote position")\n                selected_text = page.locator('[data-catalog-selected]').inner_text()\n                if catalog_name not in selected_text:\n                    fail(f"catalog selection is not visible after adding {catalog_name!r}")\n'''
    if old not in text:
        raise RuntimeError("Quote-position browser smoke anchor changed")
    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")
print("KAYI catalog browser smoke installed.")
