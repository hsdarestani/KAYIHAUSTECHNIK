from decimal import Decimal
from pathlib import Path

from django.test import TestCase

from erp.ai_scope_catalog import enrich_scope_with_authoritative_catalog
from erp.models import Organization, PriceItem, PriceSource


class DummyProfile:
    role = "office"
    is_mobile_worker = False


class DummyUser:
    profile = DummyProfile()


class DummyRequest:
    user = DummyUser()


class AIScopeAuthoritativeCatalogTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="A+Bau scope catalog")
        self.source = PriceSource.objects.create(
            organization=self.org, name="B&O VA04", original_filename="B&O-VA04.xlsx",
            sha256="c" * 64, active=True,
        )
        self.primer = PriceItem.objects.create(
            organization=self.org, source=self.source, code="VA04-MAL-GR",
            description="Wandfläche grundieren", unit="m²", sales_price=Decimal("2.40"),
        )
        self.paint = PriceItem.objects.create(
            organization=self.org, source=self.source, code="VA04-MAL-DS",
            description="Wandfläche mit Dispersionsfarbe streichen", unit="m²", sales_price=Decimal("7.80"),
        )

    def test_scope_can_resolve_real_price_rows_outside_visible_catalog(self):
        plan = {
            "actions": [],
            "scope_items": [
                {"key":"paint.wall.primer","label":"Grundierung Wände","quantity":225.0,"unit":"m²","catalog_terms":["Wände grundieren","Grundierung Wand"],"catalog_match":None},
                {"key":"paint.wall.coat","label":"Dispersionsfarbanstrich Wände","quantity":225.0,"unit":"m²","catalog_terms":["Dispersionsfarbe Wände","Wände streichen"],"catalog_match":None},
            ],
        }
        result = enrich_scope_with_authoritative_catalog(plan, self.org, DummyRequest())
        actions = {a["scope_key"]: a for a in result["actions"]}
        self.assertEqual(actions["paint.wall.primer"]["type"], "bo_catalog_add")
        self.assertEqual(actions["paint.wall.primer"]["quantity"], 225.0)
        self.assertEqual(actions["paint.wall.coat"]["quantity"], 225.0)
        self.assertEqual(result["scope_items"][0]["catalog_match"]["code"], "VA04-MAL-GR")

    def test_technician_never_receives_priced_catalog_payload(self):
        request = DummyRequest()
        request.user.profile.role = "technician"
        plan = {"actions": [], "scope_items": [{"key":"x","label":"Grundierung Wände","quantity":225.0,"unit":"m²","catalog_terms":["Grundierung Wand"],"catalog_match":None}]}
        result = enrich_scope_with_authoritative_catalog(plan, self.org, request)
        self.assertEqual(result["actions"], [])
        self.assertIsNone(result["scope_items"][0]["catalog_match"])

    def test_frontend_uses_same_direct_search_row_inserter(self):
        js = Path("static/js/bo-direct-search.js").read_text(encoding="utf-8")
        assistant = Path("static/js/kayi-next.js").read_text(encoding="utf-8")
        self.assertIn("window.ABBauAddPricedPosition", js)
        self.assertIn("quantity === null", js)
        self.assertIn("bo_catalog_add", assistant)
