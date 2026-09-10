from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME ZERO PRICE PEER REPAIR 2026-09-10"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if text.count(old) != 1:
        raise RuntimeError(f"Expected one repair anchor in {path}: {old[:80]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


service = ROOT / "erp/services/effective_pricing.py"
helpers = r'''

def _catalog_identity(item):
    name = re.sub(r"[^a-z0-9]+", " ", _ascii(getattr(item, "name", "") or "")).strip()
    unit = re.sub(r"[^a-z0-9]+", "", _ascii(getattr(item, "unit", "") or ""))
    return name, unit


def _catalog_peer_matches(org, items):
    """Find an exact priced peer for duplicate zero-price ToolTime rows."""
    wanted = {item.pk: _catalog_identity(item) for item in items}
    wanted = {pk: key for pk, key in wanted.items() if key[0]}
    if not wanted:
        return {}
    keys = set(wanted.values())
    best = {}
    for peer in m.CatalogItem.objects.filter(organization=org, active=True).order_by("pk"):
        key = _catalog_identity(peer)
        if key not in keys:
            continue
        sales = getattr(peer, "sales_price", None)
        purchase = getattr(peer, "purchase_price", None)
        if not _positive(sales) and not _positive(purchase):
            continue
        score = (1 if _positive(sales) else 0, getattr(peer, "pk", 0) or 0)
        previous = best.get(key)
        if previous is None or score > previous[0]:
            best[key] = (score, peer)
    return {item_id: best[key][1] for item_id, key in wanted.items() if key in best and best[key][1].pk != item_id}
'''
replace_once(service, "\n\ndef apply_effective_prices(org, catalog_items):", helpers + "\n\ndef apply_effective_prices(org, catalog_items):")
replace_once(service, "    unresolved = []\n    matched = {}", "    zero_items = [item for item in items if not _positive(item.sales_price)]\n    catalog_peers = _catalog_peer_matches(org, zero_items)\n    unresolved = []\n    matched = {}")
replace_once(service, "        if not _positive(item.sales_price):\n            unresolved.append(item)", "        if not _positive(item.sales_price) and item.pk not in catalog_peers:\n            unresolved.append(item)")
replace_once(service, '        catalog_value = item.sales_price if _positive(item.sales_price) else None\n        use_reference = bool(row is not None and _is_bo(row) and row_value is not None)', '        catalog_value = item.sales_price if _positive(item.sales_price) else None\n        catalog_peer = catalog_peers.get(item.pk)\n        peer_sales = getattr(catalog_peer, "sales_price", None) if catalog_peer is not None else None\n        peer_purchase = getattr(catalog_peer, "purchase_price", None) if catalog_peer is not None else None\n        peer_value = peer_sales if _positive(peer_sales) else peer_purchase\n        use_reference = bool(row is not None and _is_bo(row) and row_value is not None)')
replace_once(service, '            match_kind = "catalog"\n        elif row_value is not None:', '            match_kind = "catalog"\n        elif peer_value is not None:\n            effective = peer_value\n            source_name = "ToolTime-Katalog"\n            source_kind = "ToolTime"\n            row = None\n            match_kind = "catalog_peer"\n        elif row_value is not None:')
replace_once(service, '        item.effective_price_reference_id = row.pk if row is not None else None\n        item.effective_price_reference_code = (row.code or "").strip() if row is not None else ""\n        item.effective_price_match_kind = match_kind\n        item.effective_price_mode = row_mode if row is not None else "catalog"', '        item.effective_price_reference_id = row.pk if row is not None else (catalog_peer.pk if match_kind == "catalog_peer" else None)\n        item.effective_price_reference_code = (row.code or "").strip() if row is not None else ((catalog_peer.code or "").strip() if match_kind == "catalog_peer" else "")\n        item.effective_price_match_kind = match_kind\n        item.effective_price_mode = row_mode if row is not None else ("sales" if match_kind == "catalog_peer" and _positive(peer_sales) else "catalog")\n        item.effective_purchase_price = peer_purchase if match_kind == "catalog_peer" and _positive(peer_purchase) else getattr(item, "purchase_price", ZERO)')

catalogue = ROOT / "erp/tooltime_catalogue_views.py"
replace_once(catalogue, '    purchase = _as_decimal(getattr(item, "purchase_price", None))\n    sales = _as_decimal(getattr(item, "sales_price", None))', '    purchase = _as_decimal(getattr(item, "effective_purchase_price", getattr(item, "purchase_price", None)))\n    sales = _as_decimal(getattr(item, "effective_sales_price", getattr(item, "sales_price", None)))')
replace_once(catalogue, "    rows = [_row(item) for item in qs[:3000]]", "    from .services.effective_pricing import apply_effective_prices\n\n    items = apply_effective_prices(org, list(qs[:3000]))\n    rows = [_row(item) for item in items]")

test_path = ROOT / "tests/test_tooltime_zero_price_peer_repair.py"
test_path.write_text(r'''from decimal import Decimal
from django.test import TestCase
from erp.models import CatalogItem, Organization
from erp.services.effective_pricing import apply_effective_prices


class ToolTimeZeroPricePeerRepairTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="ToolTime peer repair")

    def test_exact_name_and_unit_use_priced_peer(self):
        priced = CatalogItem.objects.create(organization=self.org, code="TT-ABWASSER-PRICED", name="Abwasserleitung", unit="Pausch.", purchase_price=Decimal("2000.00"), sales_price=Decimal("2000.00"), active=True)
        zero = CatalogItem.objects.create(organization=self.org, code="TT-ABWASSER-ZERO", name="Abwasserleitung", unit="Pausch.", purchase_price=Decimal("0.00"), sales_price=Decimal("0.00"), active=True)
        apply_effective_prices(self.org, [zero])
        self.assertEqual(zero.effective_sales_price, Decimal("2000.00"))
        self.assertEqual(zero.effective_purchase_price, Decimal("2000.00"))
        self.assertEqual(zero.effective_price_source_kind, "ToolTime")
        self.assertEqual(zero.effective_price_reference_id, priced.pk)
        self.assertEqual(zero.effective_price_match_kind, "catalog_peer")

    def test_same_name_with_different_unit_is_not_used(self):
        CatalogItem.objects.create(organization=self.org, code="TT-ABWASSER-METER", name="Abwasserleitung", unit="m", sales_price=Decimal("80.00"), active=True)
        zero = CatalogItem.objects.create(organization=self.org, code="TT-ABWASSER-FLAT-ZERO", name="Abwasserleitung", unit="Pausch.", sales_price=Decimal("0.00"), active=True)
        apply_effective_prices(self.org, [zero])
        self.assertEqual(zero.effective_sales_price, Decimal("0"))
        self.assertEqual(zero.effective_price_source_kind, "Fehlt")
''', encoding="utf-8")

for path, needles in {service: ("_catalog_peer_matches", 'source_kind = "ToolTime"', 'match_kind = "catalog_peer"'), catalogue: ("effective_purchase_price", "apply_effective_prices"), test_path: ("test_exact_name_and_unit_use_priced_peer", "test_same_name_with_different_unit_is_not_used")}.items():
    text = path.read_text(encoding="utf-8")
    for needle in needles:
        if needle not in text:
            raise RuntimeError(f"Zero-price repair verification failed for {path}: {needle}")

print(f"{MARKER}: exact ToolTime catalogue peers now replace duplicate zero-price display rows.")
