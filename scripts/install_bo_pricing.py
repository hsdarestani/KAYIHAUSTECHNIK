from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "overlays" / "bo_pricing"
MARKER = "KAYI B&O effective pricing 20260811"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Missing B&O pricing target: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def install_service() -> None:
    source = OVERLAY / "erp" / "services" / "effective_pricing.py"
    target = ROOT / "erp" / "services" / "effective_pricing.py"
    if not source.exists():
        raise RuntimeError("B&O effective pricing service overlay missing")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def patch_document_views() -> None:
    path = "erp/rebuild_views.py"
    text = read(path)
    import_line = "from .services.effective_pricing import catalog_with_effective_prices\n"
    if import_line not in text:
        anchor = "from . import models as m\n"
        if anchor not in text:
            raise RuntimeError("rebuild_views import anchor changed")
        text = text.replace(anchor, anchor + import_line, 1)

    old_quote = '    catalog = m.CatalogItem.objects.filter(organization=org, active=True).order_by("name")[:500]\n'
    new_quote = '    catalog = catalog_with_effective_prices(org, limit=500)\n'
    if new_quote not in text:
        if old_quote not in text:
            raise RuntimeError("quote catalog query contract changed")
        text = text.replace(old_quote, new_quote, 1)

    # Legacy editor kept the invoice catalogue inline in the render dict. The
    # A+Bau editor formats the same context over multiple lines. Support both so
    # effective VA04/B&O pricing remains the source of truth after the commercial
    # editor upgrade instead of making the assembly order brittle.
    old_invoice_legacy = '"catalog": m.CatalogItem.objects.filter(organization=org, active=True).order_by("name")[:500], "kind": "invoice"'
    new_invoice_legacy = '"catalog": catalog_with_effective_prices(org, limit=500), "kind": "invoice"'
    old_invoice_ab = '        "catalog": m.CatalogItem.objects.filter(organization=org, active=True).order_by("name")[:500],\n'
    new_invoice_ab = '        "catalog": catalog_with_effective_prices(org, limit=500),\n'
    if new_invoice_legacy not in text and new_invoice_ab not in text:
        if old_invoice_legacy in text:
            text = text.replace(old_invoice_legacy, new_invoice_legacy, 1)
        elif old_invoice_ab in text:
            text = text.replace(old_invoice_ab, new_invoice_ab, 1)
        else:
            raise RuntimeError("invoice catalog query contract changed")
    write(path, text)


def patch_document_template() -> None:
    path = "templates/rebuild/document_editor.html"
    text = read(path)

    if "data-ab-catalog" in text:
        # A+Bau/ToolTime editor: expose effective B&O metadata on the catalogue
        # button and use the effective sales price for the fallback price shown
        # and inserted when no explicit purchase price exists.
        old_sales = 'data-sales="{{ item.sales_price|stringformat:\'s\' }}"'
        new_sales = 'data-sales="{{ item.effective_sales_price|stringformat:\'s\' }}" data-price-source="{{ item.effective_price_source|escape }}" data-price-source-kind="{{ item.effective_price_source_kind|escape }}" data-price-reference-code="{{ item.effective_price_reference_code|escape }}" data-price-match-kind="{{ item.effective_price_match_kind|escape }}"'
        if new_sales not in text:
            if old_sales not in text:
                raise RuntimeError("A+Bau catalogue effective-price data anchor changed")
            text = text.replace(old_sales, new_sales, 1)
        text = text.replace(
            '<strong>{{ item.sales_price|floatformat:2 }} €</strong>',
            '<strong>{{ item.effective_sales_price|floatformat:2 }} €</strong>',
        )
    else:
        # Legacy KAYI Next editor retained for compatibility with older source
        # assemblies and migration branches.
        if "effective_price_source_kind" not in text:
            text = text.replace('data-price="{{ item.sales_price|stringformat:\'s\' }}"', 'data-price="{{ item.effective_sales_price|stringformat:\'s\' }}"')
            text = text.replace('{{ item.code }} · {{ item.sales_price|floatformat:2 }} € / {{ item.unit }}', '{{ item.code }} · {{ item.effective_sales_price|floatformat:2 }} € / {{ item.unit }} · {{ item.effective_price_source_kind }}')
            text = text.replace(
                'data-tax="{{ item.tax_rate|stringformat:\'s\' }}"',
                'data-tax="{{ item.tax_rate|stringformat:\'s\' }}" data-price-source="{{ item.effective_price_source|escape }}" data-price-source-kind="{{ item.effective_price_source_kind|escape }}" data-price-reference-code="{{ item.effective_price_reference_code|escape }}" data-price-match-kind="{{ item.effective_price_match_kind|escape }}"',
            )
    if "item.effective_sales_price" not in text:
        raise RuntimeError("document editor still does not render effective prices")
    write(path, text)


def patch_field_authorization() -> None:
    path = "erp/field_authorization_views.py"
    text = read(path)
    import_line = "from .services.effective_pricing import effective_price_for_catalog_item\n"
    if import_line not in text:
        anchor = "from .rebuild_views import _employee, _is_field_user, _org, _unique_number\n"
        if anchor not in text:
            raise RuntimeError("field authorization pricing import anchor changed")
        text = text.replace(anchor, anchor + import_line, 1)

    old = '                "unit_price": str(catalog.sales_price if catalog else Decimal("0.00")),\n'
    new = '                "unit_price": str(effective_price_for_catalog_item(org, catalog) if catalog else Decimal("0.00")),\n'
    if new not in text:
        if old not in text:
            raise RuntimeError("field authorization catalog price contract changed")
        text = text.replace(old, new, 1)
    write(path, text)


def install_tests() -> None:
    target = ROOT / "tests" / "test_bo_effective_pricing_contract.py"
    target.write_text('''from decimal import Decimal\nfrom pathlib import Path\n\nfrom django.test import SimpleTestCase, TestCase\n\nfrom erp.models import CatalogItem, Organization, PriceItem, PriceSource\nfrom erp.services.effective_pricing import apply_effective_prices\n\n\nclass BoEffectivePricingContractTests(SimpleTestCase):\n    def test_offer_invoice_and_field_flow_use_effective_pricing(self):\n        service = Path("erp/services/effective_pricing.py").read_text(encoding="utf-8")\n        views = Path("erp/rebuild_views.py").read_text(encoding="utf-8")\n        field = Path("erp/field_authorization_views.py").read_text(encoding="utf-8")\n        template = Path("templates/rebuild/document_editor.html").read_text(encoding="utf-8")\n        self.assertIn("_semantic_bo_matches", service)\n        self.assertIn("_domain_features", service)\n        self.assertIn("_has_conflict", service)\n        self.assertIn("_external_codes", service)\n        self.assertIn("effective_price_reference_code", service)\n        self.assertIn("catalog_with_effective_prices", views)\n        self.assertIn("effective_price_for_catalog_item", field)\n        self.assertIn("effective_sales_price", template)\n        self.assertIn("data-price-source-kind", template)\n        self.assertIn("data-price-reference-code", template)\n\n    def test_zero_is_only_final_fallback(self):\n        service = Path("erp/services/effective_pricing.py").read_text(encoding="utf-8")\n        self.assertIn("deterministic semantic B&O match", service)\n        self.assertIn('source_kind = "Fehlt"', service)\n        self.assertIn('source_kind = "B&O"', service)\n\n\nclass BoEffectivePricingDatabaseTests(TestCase):\n    def setUp(self):\n        self.org = Organization.objects.create(name="KAYI B&O Pricing")\n        self.source = PriceSource.objects.create(\n            organization=self.org,\n            name="B&O VA04 Preisdatei",\n            original_filename="B&O-VA04-Preise.xlsx",\n            active=True,\n        )\n        self.bo = PriceItem.objects.create(\n            organization=self.org,\n            source=self.source,\n            code="VA04-2.02.04.0020",\n            description="Montage Waschtisch, mit vorh. Anschlussteilen",\n            unit="Stk.",\n            sales_price=Decimal("48.74"),\n        )\n\n    def test_internal_kayi_code_resolves_real_bo_price_semantically(self):\n        item = CatalogItem.objects.create(\n            organization=self.org, code="S1002", name="Waschtisch montieren",\n            unit="Stk.", sales_price=Decimal("0.00"), active=True,\n        )\n        apply_effective_prices(self.org, [item])\n        self.assertEqual(item.effective_sales_price, Decimal("48.74"))\n        self.assertEqual(item.effective_price_source_kind, "B&O")\n        self.assertEqual(item.effective_price_reference_code, "VA04-2.02.04.0020")\n        self.assertEqual(item.effective_price_match_kind, "semantic")\n\n    def test_explicit_external_va04_code_has_priority(self):\n        item = CatalogItem.objects.create(\n            organization=self.org, code="S1999", name="Interne Bezeichnung",\n            external_codes={"bo_code": "VA04-2.02.04.0020"},\n            unit="Stk.", sales_price=Decimal("0.00"), active=True,\n        )\n        apply_effective_prices(self.org, [item])\n        self.assertEqual(item.effective_sales_price, Decimal("48.74"))\n        self.assertEqual(item.effective_price_reference_code, "VA04-2.02.04.0020")\n        self.assertEqual(item.effective_price_match_kind, "external_code")\n\n    def test_common_zero_price_services_resolve_alternate_bo_wording(self):\n        fixtures = [\n            ("S1010", "Dusch-WC montieren", "VA04-DWC", "WC mit Duschfunktion montieren", "235.40"),\n            ("S1022", "Duschabtrennung montieren", "VA04-DAB", "Montage Duschabtrennwand", "89.20"),\n            ("S1023", "Duscharmatur (Aufputz) montieren", "VA04-DAP", "Brausearmatur AP montieren", "64.30"),\n            ("S1021", "Duschrinne montieren", "VA04-DRI", "Ablaufrinne Dusche montieren", "77.60"),\n            ("S1030", "Ausgleichsmasse einbringen", "VA04-AUS", "Nivelliermasse Boden einbringen", "12.80"),\n            ("S1031", "Dichtigkeitsprüfung durchführen", "VA04-DIC", "Dichtheitsprüfung", "31.50"),\n        ]\n        items = []\n        expected = {}\n        for code, name, bo_code, bo_description, price in fixtures:\n            item = CatalogItem.objects.create(organization=self.org, code=code, name=name, unit="Stk.", sales_price=Decimal("0.00"), active=True)\n            PriceItem.objects.create(organization=self.org, source=self.source, code=bo_code, description=bo_description, unit="Stk.", sales_price=Decimal(price))\n            items.append(item)\n            expected[item.pk] = (Decimal(price), bo_code)\n        apply_effective_prices(self.org, items)\n        for item in items:\n            price, bo_code = expected[item.pk]\n            self.assertEqual(item.effective_sales_price, price, item.name)\n            self.assertEqual(item.effective_price_reference_code, bo_code, item.name)\n            self.assertEqual(item.effective_price_source_kind, "B&O", item.name)\n\n    def test_ap_service_never_selects_up_variant(self):\n        PriceItem.objects.create(organization=self.org, source=self.source, code="VA04-UP", description="Brausearmatur UP montieren", unit="Stk.", sales_price=Decimal("999.00"))\n        PriceItem.objects.create(organization=self.org, source=self.source, code="VA04-AP", description="Brausearmatur AP montieren", unit="Stk.", sales_price=Decimal("64.30"))\n        item = CatalogItem.objects.create(organization=self.org, code="S1023", name="Duscharmatur (Aufputz) montieren", unit="Stk.", sales_price=Decimal("0.00"), active=True)\n        apply_effective_prices(self.org, [item])\n        self.assertEqual(item.effective_price_reference_code, "VA04-AP")\n        self.assertEqual(item.effective_sales_price, Decimal("64.30"))\n''', encoding="utf-8")


def guard() -> None:
    service = read("erp/services/effective_pricing.py")
    views = read("erp/rebuild_views.py")
    field = read("erp/field_authorization_views.py")
    template = read("templates/rebuild/document_editor.html")
    tests = read("tests/test_bo_effective_pricing_contract.py")
    for needle in ("_is_bo", "_semantic_bo_matches", "_domain_features", "_has_conflict", "_external_codes", "source__active=True", "effective_sales_price", "effective_price_reference_code", "catalog_with_effective_prices"):
        if needle not in service:
            raise RuntimeError(f"B&O pricing service missing: {needle}")
    if views.count("catalog_with_effective_prices(org, limit=500)") < 2:
        raise RuntimeError("Offer/invoice editors are not both using effective pricing")
    if "effective_price_for_catalog_item(org, catalog)" not in field:
        raise RuntimeError("Field authorization still bypasses effective pricing")
    for needle in ("item.effective_sales_price", "data-price-source", "effective_price_source_kind", "data-price-reference-code"):
        if needle not in template:
            raise RuntimeError(f"Document editor effective price UI missing: {needle}")
    for needle in ("S1002", "VA04-2.02.04.0020", 'Decimal("48.74")', "Dusch-WC montieren", "Dichtigkeitsprüfung", "VA04-AP"):
        if needle not in tests:
            raise RuntimeError(f"B&O database regression test missing: {needle}")


install_service()
patch_document_views()
patch_document_template()
patch_field_authorization()
install_tests()
guard()
print("KAYI B&O effective pricing installed: Angebot, Rechnung and field KI resolve active B&O prices by explicit VA04 mapping or safe German trade-semantic matching.")
