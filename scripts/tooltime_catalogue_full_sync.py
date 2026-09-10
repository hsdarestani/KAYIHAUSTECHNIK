from __future__ import annotations

import json
import pprint
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/reference_seed/tooltime_catalogue_20260910.json"
TARGET = ROOT / "erp/tooltime_catalogue_reference.py"
SERVICE = ROOT / "erp/services/effective_pricing.py"
MARKER = "A+BAU TOOLTIME FULL CATALOGUE SYNC 2026-09-10"


def identity(name: str, unit: str) -> str:
    value = (name or "").lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    unit_value = (unit or "").lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    unit_value = re.sub(r"[^a-z0-9]+", "", unit_value)
    return f"{value}|{unit_value}"


payload = json.loads(SOURCE.read_text(encoding="utf-8"))
items = payload["items"]
by_code = {}
by_identity = {}
for row in items:
    record = {
        "purchase": row["purchase"],
        "sales": row["sales"],
        "changed": row["changed"],
        "name": row["name"],
        "unit": row["unit"],
    }
    if row.get("code"):
        by_code[row["code"].strip().casefold()] = record
    by_identity[identity(row["name"], row["unit"])] = record

TARGET.write_text(
    "# Generated from the confirmed ToolTime catalogue snapshot.\n"
    f"CAPTURED_AT = {payload['captured_at']!r}\n"
    f"REFERENCE_BY_CODE = {pprint.pformat(by_code, width=120, sort_dicts=True)}\n"
    f"REFERENCE_BY_IDENTITY = {pprint.pformat(by_identity, width=120, sort_dicts=True)}\n",
    encoding="utf-8",
)


def replace_once(old: str, new: str) -> None:
    text = SERVICE.read_text(encoding="utf-8")
    if new in text:
        return
    if text.count(old) != 1:
        raise RuntimeError(f"Expected one full-sync anchor: {old[:100]!r}")
    SERVICE.write_text(text.replace(old, new, 1), encoding="utf-8")


helpers = r'''

def _tooltime_reference_matches(items):
    from erp.tooltime_catalogue_reference import REFERENCE_BY_CODE, REFERENCE_BY_IDENTITY

    matched = {}
    for item in items:
        code = (getattr(item, "code", "") or "").strip().casefold()
        reference = REFERENCE_BY_CODE.get(code) if code else None
        if reference is None:
            name, unit = _catalog_identity(item)
            reference = REFERENCE_BY_IDENTITY.get(f"{name}|{unit}")
        if reference is not None:
            matched[item.pk] = reference
    return matched
'''
replace_once("\n\ndef apply_effective_prices(org, catalog_items):", helpers + "\n\ndef apply_effective_prices(org, catalog_items):")
replace_once(
    "    items = list(catalog_items)\n    lookup_codes = []",
    "    items = list(catalog_items)\n    tooltime_references = _tooltime_reference_matches(items)\n    lookup_codes = []",
)
replace_once(
    '        use_reference = bool(row is not None and _is_bo(row) and row_value is not None)\n\n        if use_reference:',
    '        tooltime_reference = tooltime_references.get(item.pk)\n'
    '        tooltime_sales = Decimal(tooltime_reference["sales"]) if tooltime_reference else ZERO\n'
    '        tooltime_purchase = Decimal(tooltime_reference["purchase"]) if tooltime_reference else ZERO\n'
    '        use_reference = bool(row is not None and _is_bo(row) and row_value is not None)\n\n'
    '        if tooltime_reference is not None and _positive(tooltime_sales):\n'
    '            effective = tooltime_sales\n'
    '            source_name = f"ToolTime-Katalog ({tooltime_reference[\'changed\']})"\n'
    '            source_kind = "ToolTime"\n'
    '            row = None\n'
    '            match_kind = "tooltime_reference"\n'
    '        elif use_reference:',
)
replace_once(
    '        item.effective_purchase_price = peer_purchase if match_kind == "catalog_peer" and _positive(peer_purchase) else getattr(item, "purchase_price", ZERO)',
    '        item.effective_purchase_price = tooltime_purchase if match_kind == "tooltime_reference" and _positive(tooltime_purchase) else (peer_purchase if match_kind == "catalog_peer" and _positive(peer_purchase) else getattr(item, "purchase_price", ZERO))',
)

test_path = ROOT / "tests/test_tooltime_catalogue_full_sync.py"
test_path.write_text(r'''from decimal import Decimal
from django.test import TestCase
from erp.models import CatalogItem, Organization
from erp.services.effective_pricing import apply_effective_prices


class ToolTimeCatalogueFullSyncTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="ToolTime full sync")

    def test_reference_updates_existing_nonzero_price(self):
        item = CatalogItem.objects.create(organization=self.org, code="AGTEMPOFPN", name="old", unit="Pc.", purchase_price=Decimal("1"), sales_price=Decimal("2"), active=True)
        apply_effective_prices(self.org, [item])
        self.assertEqual(item.effective_purchase_price, Decimal("15.60"))
        self.assertEqual(item.effective_sales_price, Decimal("39.81"))
        self.assertEqual(item.effective_price_match_kind, "tooltime_reference")

    def test_name_and_unit_match_without_code(self):
        item = CatalogItem.objects.create(organization=self.org, code="LOCAL-1", name="Abwasserleitung", unit="Flat rate", sales_price=Decimal("0"), active=True)
        apply_effective_prices(self.org, [item])
        self.assertEqual(item.effective_sales_price, Decimal("2000.00"))
        self.assertEqual(item.effective_price_source_kind, "ToolTime")

    def test_different_unit_does_not_receive_reference_price(self):
        item = CatalogItem.objects.create(organization=self.org, code="LOCAL-2", name="Abwasserleitung", unit="m", sales_price=Decimal("0"), active=True)
        apply_effective_prices(self.org, [item])
        self.assertEqual(item.effective_sales_price, Decimal("0"))
''', encoding="utf-8")

service_text = SERVICE.read_text(encoding="utf-8")
for needle in ("_tooltime_reference_matches", "tooltime_reference", 'match_kind = "tooltime_reference"'):
    if needle not in service_text:
        raise RuntimeError(f"Full ToolTime sync verification failed: {needle}")
if len(by_identity) != 220:
    raise RuntimeError(f"Expected 220 unique ToolTime name/unit rows, found {len(by_identity)}")
print(f"{MARKER}: {len(items)} normalized ToolTime references installed ({len(by_code)} coded).")
