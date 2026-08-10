from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "overlays" / "bo_direct_search"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Missing B&O direct-search target: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def copy_overlay() -> None:
    pairs = (
        ("erp/services/bo_direct_search.py", "erp/services/bo_direct_search.py"),
        ("erp/bo_direct_search_views.py", "erp/bo_direct_search_views.py"),
        ("static/js/bo-direct-search.js", "static/js/bo-direct-search.js"),
    )
    for source_rel, target_rel in pairs:
        source = OVERLAY / source_rel
        if not source.exists():
            raise RuntimeError(f"B&O direct-search overlay missing: {source_rel}")
        target = ROOT / target_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def patch_urls() -> None:
    path = "erp/rebuild_urls.py"
    text = read(path)
    import_line = "from . import bo_direct_search_views as bo_search\n"
    if import_line not in text:
        anchor = "from . import rebuild_views as views\n"
        if anchor not in text:
            raise RuntimeError("B&O direct-search URL import anchor changed")
        text = text.replace(anchor, anchor + import_line, 1)
    route = '    path("pricing/bando/search/", bo_search.bo_price_search, name="next-bo-price-search"),\n'
    if route not in text:
        anchor = '    path("quotes/", views.quote_list, name="next-quotes"),\n'
        if anchor not in text:
            raise RuntimeError("B&O direct-search route anchor changed")
        text = text.replace(anchor, route + anchor, 1)
    write(path, text)


def patch_document_views() -> None:
    path = "erp/rebuild_views.py"
    text = read(path)
    quote_old = "    catalog = catalog_with_effective_prices(org, limit=500)\n"
    quote_new = '    catalog = [item for item in catalog_with_effective_prices(org, limit=500) if item.effective_sales_price > Decimal("0")]\n'
    if quote_new not in text:
        if quote_old not in text:
            raise RuntimeError("B&O priced KAYI quote catalog anchor changed")
        text = text.replace(quote_old, quote_new, 1)
    invoice_old = '"catalog": catalog_with_effective_prices(org, limit=500), "kind": "invoice"'
    invoice_new = '"catalog": [item for item in catalog_with_effective_prices(org, limit=500) if item.effective_sales_price > Decimal("0")], "kind": "invoice"'
    if invoice_new not in text:
        if invoice_old not in text:
            raise RuntimeError("B&O priced KAYI invoice catalog anchor changed")
        text = text.replace(invoice_old, invoice_new, 1)
    write(path, text)


def patch_template() -> None:
    path = "templates/rebuild/document_editor.html"
    text = read(path)
    if "{% load static %}" not in text:
        first = "{% extends 'rebuild/base.html' %}\n"
        if first not in text:
            raise RuntimeError("document editor extends anchor changed")
        text = text.replace(first, first + "{% load static %}\n", 1)

    if "data-bo-direct-search" not in text:
        # catalog_interaction_hardening.py runs inside install_tooltime_rebuild
        # before this final B&O layer, so patch its final header contract.
        anchor = '<section class="nx-card"><div class="nx-card-head"><div><h3>Katalog</h3><p>Suchen und mit einem Klick als Position übernehmen.</p></div></div>'
        if anchor not in text:
            raise RuntimeError("document editor final catalog panel anchor changed")
        replacement = '''<section class="nx-card nx-card-pad" data-bo-direct-search data-bo-search-url="{% url 'next-bo-price-search' %}">
        <div class="nx-card-head" style="padding:0 0 12px"><div><div class="nx-kicker">B&O ORIGINALPREISE</div><h3>B&O-Position suchen</h3><p>Direkt in der importierten VA04-Preisliste suchen. Nur Positionen mit echtem hinterlegtem Preis werden angezeigt.</p></div></div>
        <div class="nx-field"><label>Leistung oder VA04-Code</label><input class="nx-control" type="search" data-bo-query autocomplete="off" placeholder="z. B. Duscharmatur, Dichtheitsprüfung oder VA04-…"></div>
        <small class="nx-muted" data-bo-status>Mindestens 2 Zeichen eingeben.</small>
        <div data-bo-results style="display:grid;gap:7px;max-height:360px;overflow:auto;margin-top:10px"></div>
      </section>
      <section class="nx-card"><div class="nx-card-head"><div><h3>KAYI-Vorlagen mit Preis</h3><p>Nur bereits bepreiste Schnellpositionen. Für B&O oben direkt in der Originalpreisliste suchen.</p></div></div>'''
        text = text.replace(anchor, replacement, 1)

    script = '<script src="{% static \'js/bo-direct-search.js\' %}?v=20260811-2"></script>'
    if "bo-direct-search.js" not in text:
        marker = "{% endblock %}"
        index = text.rfind(marker)
        if index < 0:
            raise RuntimeError("document editor endblock missing")
        text = text[:index] + script + "\n" + text[index:]
    write(path, text)


def install_tests() -> None:
    target = ROOT / "tests" / "test_bo_direct_search.py"
    target.write_text('''from decimal import Decimal\nfrom pathlib import Path\n\nfrom django.test import SimpleTestCase, TestCase\n\nfrom erp.models import Organization, PriceItem, PriceSource\nfrom erp.services.bo_direct_search import search_bo_prices, serialize_bo_price\n\n\nclass BoDirectSearchContractTests(SimpleTestCase):\n    def test_quote_editor_contains_direct_bo_search_and_hides_unpriced_shortcuts(self):\n        urls = Path("erp/rebuild_urls.py").read_text(encoding="utf-8")\n        views = Path("erp/rebuild_views.py").read_text(encoding="utf-8")\n        template = Path("templates/rebuild/document_editor.html").read_text(encoding="utf-8")\n        script = Path("static/js/bo-direct-search.js").read_text(encoding="utf-8")\n        self.assertIn("next-bo-price-search", urls)\n        self.assertIn("data-bo-direct-search", template)\n        self.assertIn("data-bo-search-url", template)\n        self.assertIn("B&O-Position suchen", template)\n        self.assertIn("KAYI-Vorlagen mit Preis", template)\n        self.assertGreaterEqual(views.count('effective_sales_price > Decimal("0")'), 2)\n        self.assertIn("boReferenceCode", script)\n        self.assertIn("boSearchUrl", script)\n        self.assertIn("data-bo-results", script)\n\n\nclass BoDirectSearchDatabaseTests(TestCase):\n    def setUp(self):\n        self.org = Organization.objects.create(name="KAYI Direct B&O")\n        self.bo = PriceSource.objects.create(organization=self.org, name="B&O VA04", original_filename="B&O-VA04.xlsx", active=True)\n        self.other = PriceSource.objects.create(organization=self.org, name="Andere Liste", original_filename="other.xlsx", active=True)\n        self.ap = PriceItem.objects.create(organization=self.org, source=self.bo, code="VA04-DAP", description="Brausearmatur AP montieren", unit="Stk.", sales_price=Decimal("64.30"))\n        self.dicht = PriceItem.objects.create(organization=self.org, source=self.bo, code="VA04-DIC", description="Dichtheitsprüfung Sanitärinstallation", unit="Psch.", sales_price=Decimal("31.50"))\n        PriceItem.objects.create(organization=self.org, source=self.other, code="OTHER-1", description="Duscharmatur Sonderpreis", unit="Stk.", sales_price=Decimal("1.00"))\n\n    def test_duscharmatur_finds_real_brausearmatur_bo_row(self):\n        rows = search_bo_prices(self.org, "Duscharmatur")\n        self.assertTrue(rows)\n        self.assertEqual(rows[0].pk, self.ap.pk)\n        payload = serialize_bo_price(rows[0])\n        self.assertEqual(payload["price"], "64.30")\n        self.assertEqual(payload["code"], "VA04-DAP")\n\n    def test_va04_code_search_is_supported(self):\n        rows = search_bo_prices(self.org, "VA04-DIC")\n        self.assertEqual(rows[0].pk, self.dicht.pk)\n\n    def test_non_bo_source_never_leaks_into_results(self):\n        rows = search_bo_prices(self.org, "Duscharmatur")\n        self.assertFalse(any(row.source_id == self.other.pk for row in rows))\n''', encoding="utf-8")


def guard() -> None:
    urls = read("erp/rebuild_urls.py")
    views = read("erp/rebuild_views.py")
    template = read("templates/rebuild/document_editor.html")
    script = read("static/js/bo-direct-search.js")
    for needle in ("next-bo-price-search", "bo_direct_search_views"):
        if needle not in urls:
            raise RuntimeError(f"B&O direct-search URL wiring missing: {needle}")
    if views.count('effective_sales_price > Decimal("0")') < 2:
        raise RuntimeError("Unpriced KAYI shortcut positions are still shown in quote/invoice catalog")
    for needle in ("data-bo-direct-search", "data-bo-search-url", "B&O-Position suchen", "KAYI-Vorlagen mit Preis", "bo-direct-search.js"):
        if needle not in template:
            raise RuntimeError(f"B&O direct-search UI missing: {needle}")
    for needle in ("data-bo-results", "boReferenceCode", "boSearchUrl", "fetch(url"):
        if needle not in script:
            raise RuntimeError(f"B&O direct-search JS missing: {needle}")


copy_overlay()
patch_urls()
patch_document_views()
patch_template()
install_tests()
guard()
print("KAYI direct B&O search installed: Angebot/Rechnung search real priced VA04 rows; unresolved KAYI shortcuts are hidden from the main quick catalog.")
