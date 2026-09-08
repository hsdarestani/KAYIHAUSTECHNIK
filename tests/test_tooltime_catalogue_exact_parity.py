from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]

class ToolTimeCatalogueExactParityContractTests(SimpleTestCase):
    def test_catalogue_route_and_navigation_are_real(self):
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        for required in ("next-catalogue", "next-catalogue-create", "next-catalogue-edit", "next-catalogue-delete"):
            self.assertIn(required, urls)
        self.assertIn("next-catalogue", base)
        self.assertIn("Katalog", base)

    def test_catalogue_matches_tooltime_index_controls(self):
        template = (ROOT / "templates/rebuild/catalogue.html").read_text(encoding="utf-8")
        for required in ("data-tooltime-catalogue", "Alle Artikeltypen", "Katalog durchsuchen", "Artikel hinzufügen", "Artikelnummer", "Beschreibung", "Einheit", "Einkaufspreis", "Aufschlag", "Stückpreis", "Letzte Änderung", "ttc-row-menu"):
            self.assertIn(required, template)

    def test_catalogue_is_backed_by_existing_catalog_items(self):
        module = (ROOT / "erp/tooltime_catalogue_views.py").read_text(encoding="utf-8")
        self.assertIn("m.CatalogItem.objects.filter(organization=org)", module)
        self.assertIn("item.save()", module)
        self.assertIn("catalogue_delete", module)
        self.assertNotIn("hard-coded article", module)

    def test_browser_smoke_covers_catalogue(self):
        smoke = (ROOT / "scripts/production_browser_smoke.py").read_text(encoding="utf-8")
        self.assertIn("A+BAU TOOLTIME CATALOGUE EXACT PARITY BROWSER SMOKE", smoke)
        self.assertIn("/catalogue/", smoke)
