from decimal import Decimal
from pathlib import Path

from django.test import SimpleTestCase, TestCase

from erp.models import CatalogItem, Organization, PriceItem, PriceSource
from erp.services.effective_pricing import apply_effective_prices


class BoEffectivePricingContractTests(SimpleTestCase):
    def test_offer_invoice_and_field_flow_use_effective_pricing(self):
        service = Path("erp/services/effective_pricing.py").read_text(encoding="utf-8")
        views = Path("erp/rebuild_views.py").read_text(encoding="utf-8")
        field = Path("erp/field_authorization_views.py").read_text(encoding="utf-8")
        template = Path("templates/rebuild/document_editor.html").read_text(encoding="utf-8")
        self.assertIn("_semantic_bo_matches", service)
        self.assertIn("_domain_features", service)
        self.assertIn("_has_conflict", service)
        self.assertIn("_external_codes", service)
        self.assertIn("effective_price_reference_code", service)
        self.assertIn("catalog_with_effective_prices", views)
        self.assertIn("effective_price_for_catalog_item", field)
        self.assertIn("effective_sales_price", template)
        self.assertIn("data-price-source-kind", template)
        self.assertIn("data-price-reference-code", template)

    def test_zero_is_only_final_fallback(self):
        service = Path("erp/services/effective_pricing.py").read_text(encoding="utf-8")
        self.assertIn("deterministic semantic B&O match", service)
        self.assertIn('source_kind = "Fehlt"', service)
        self.assertIn('source_kind = "B&O"', service)


class BoEffectivePricingDatabaseTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="KAYI B&O Pricing")
        self.source = PriceSource.objects.create(
            organization=self.org,
            name="B&O VA04 Preisdatei",
            original_filename="B&O-VA04-Preise.xlsx",
            active=True,
        )
        self.bo = PriceItem.objects.create(
            organization=self.org,
            source=self.source,
            code="VA04-2.02.04.0020",
            description="Montage Waschtisch, mit vorh. Anschlussteilen",
            unit="Stk.",
            sales_price=Decimal("48.74"),
        )

    def test_internal_kayi_code_resolves_real_bo_price_semantically(self):
        item = CatalogItem.objects.create(
            organization=self.org, code="S1002", name="Waschtisch montieren",
            unit="Stk.", sales_price=Decimal("0.00"), active=True,
        )
        apply_effective_prices(self.org, [item])
        self.assertEqual(item.effective_sales_price, Decimal("48.74"))
        self.assertEqual(item.effective_price_source_kind, "B&O")
        self.assertEqual(item.effective_price_reference_code, "VA04-2.02.04.0020")
        self.assertEqual(item.effective_price_match_kind, "semantic")

    def test_explicit_external_va04_code_has_priority(self):
        item = CatalogItem.objects.create(
            organization=self.org, code="S1999", name="Interne Bezeichnung",
            external_codes={"bo_code": "VA04-2.02.04.0020"},
            unit="Stk.", sales_price=Decimal("0.00"), active=True,
        )
        apply_effective_prices(self.org, [item])
        self.assertEqual(item.effective_sales_price, Decimal("48.74"))
        self.assertEqual(item.effective_price_reference_code, "VA04-2.02.04.0020")
        self.assertEqual(item.effective_price_match_kind, "external_code")

    def test_common_zero_price_services_resolve_alternate_bo_wording(self):
        fixtures = [
            ("S1010", "Dusch-WC montieren", "VA04-DWC", "WC mit Duschfunktion montieren", "235.40"),
            ("S1022", "Duschabtrennung montieren", "VA04-DAB", "Montage Duschabtrennwand", "89.20"),
            ("S1023", "Duscharmatur (Aufputz) montieren", "VA04-DAP", "Brausearmatur AP montieren", "64.30"),
            ("S1021", "Duschrinne montieren", "VA04-DRI", "Ablaufrinne Dusche montieren", "77.60"),
            ("S1030", "Ausgleichsmasse einbringen", "VA04-AUS", "Nivelliermasse Boden einbringen", "12.80"),
            ("S1031", "Dichtigkeitsprüfung durchführen", "VA04-DIC", "Dichtheitsprüfung", "31.50"),
        ]
        items = []
        expected = {}
        for code, name, bo_code, bo_description, price in fixtures:
            item = CatalogItem.objects.create(organization=self.org, code=code, name=name, unit="Stk.", sales_price=Decimal("0.00"), active=True)
            PriceItem.objects.create(organization=self.org, source=self.source, code=bo_code, description=bo_description, unit="Stk.", sales_price=Decimal(price))
            items.append(item)
            expected[item.pk] = (Decimal(price), bo_code)
        apply_effective_prices(self.org, items)
        for item in items:
            price, bo_code = expected[item.pk]
            self.assertEqual(item.effective_sales_price, price, item.name)
            self.assertEqual(item.effective_price_reference_code, bo_code, item.name)
            self.assertEqual(item.effective_price_source_kind, "B&O", item.name)

    def test_ap_service_never_selects_up_variant(self):
        PriceItem.objects.create(organization=self.org, source=self.source, code="VA04-UP", description="Brausearmatur UP montieren", unit="Stk.", sales_price=Decimal("999.00"))
        PriceItem.objects.create(organization=self.org, source=self.source, code="VA04-AP", description="Brausearmatur AP montieren", unit="Stk.", sales_price=Decimal("64.30"))
        item = CatalogItem.objects.create(organization=self.org, code="S1023", name="Duscharmatur (Aufputz) montieren", unit="Stk.", sales_price=Decimal("0.00"), active=True)
        apply_effective_prices(self.org, [item])
        self.assertEqual(item.effective_price_reference_code, "VA04-AP")
        self.assertEqual(item.effective_sales_price, Decimal("64.30"))
