from decimal import Decimal
from pathlib import Path

from django.test import SimpleTestCase, TestCase

from erp.models import Organization, PriceItem, PriceSource
from erp.services.bo_direct_search import search_bo_prices, serialize_bo_price


class BoDirectSearchContractTests(SimpleTestCase):
    def test_quote_editor_contains_direct_bo_search_and_hides_unpriced_shortcuts(self):
        urls = Path("erp/rebuild_urls.py").read_text(encoding="utf-8")
        views = Path("erp/rebuild_views.py").read_text(encoding="utf-8")
        endpoint = Path("erp/bo_direct_search_views.py").read_text(encoding="utf-8")
        template = Path("templates/rebuild/document_editor.html").read_text(encoding="utf-8")
        script = Path("static/js/bo-direct-search.js").read_text(encoding="utf-8")
        self.assertIn("next-bo-price-search", urls)
        self.assertIn("_is_field_user", endpoint)
        self.assertIn("Keine Preisberechtigung", endpoint)
        self.assertIn("data-bo-direct-search", template)
        self.assertIn("data-bo-search-url", template)
        self.assertIn("B&O-Position suchen", template)
        self.assertIn("A+Bau-Vorlagen mit Preis", template)
        self.assertGreaterEqual(views.count("_fast_catalog_preview(org)"), 2)
        self.assertIn("boReferenceCode", script)
        self.assertIn("boSearchUrl", script)
        self.assertIn("data-bo-results", script)


class BoDirectSearchDatabaseTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="A+Bau Direct B&O")
        self.bo = PriceSource.objects.create(organization=self.org, name="B&O VA04", original_filename="B&O-VA04.xlsx", sha256="a" * 64, active=True)
        self.other = PriceSource.objects.create(organization=self.org, name="Andere Liste", original_filename="other.xlsx", sha256="b" * 64, active=True)
        self.ap = PriceItem.objects.create(organization=self.org, source=self.bo, code="VA04-DAP", description="Brausearmatur AP montieren", unit="Stk.", sales_price=Decimal("64.30"))
        self.dicht = PriceItem.objects.create(organization=self.org, source=self.bo, code="VA04-DIC", description="Dichtheitsprüfung Sanitärinstallation", unit="Psch.", sales_price=Decimal("31.50"))
        PriceItem.objects.create(organization=self.org, source=self.other, code="OTHER-1", description="Duscharmatur Sonderpreis", unit="Stk.", sales_price=Decimal("1.00"))

    def test_duscharmatur_finds_real_brausearmatur_bo_row(self):
        rows = search_bo_prices(self.org, "Duscharmatur")
        self.assertTrue(rows)
        self.assertEqual(rows[0].pk, self.ap.pk)
        payload = serialize_bo_price(rows[0])
        self.assertEqual(payload["price"], "64.30")
        self.assertEqual(payload["code"], "VA04-DAP")

    def test_va04_code_search_is_supported(self):
        rows = search_bo_prices(self.org, "VA04-DIC")
        self.assertEqual(rows[0].pk, self.dicht.pk)

    def test_non_bo_source_never_leaks_into_results(self):
        rows = search_bo_prices(self.org, "Duscharmatur")
        self.assertFalse(any(row.source_id == self.other.pk for row in rows))
