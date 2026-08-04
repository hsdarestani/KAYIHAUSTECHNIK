import gzip
import json
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from erp.models import CatalogItem, Organization, PriceItem, PriceSource


class NormalizedPriceImportTests(TestCase):
    def test_import_is_idempotent_and_keeps_demo_separate(self):
        org = Organization.objects.create(name="KAYI Haustechnik")
        Organization.objects.create(name="KAYI Demo", settings={"is_demo": True})
        payload = {
            "version": 1,
            "sources": [{
                "path": "stammdaten/leistungskatalog/Leistungskatalog_Kayi.xlsx",
                "filename": "Leistungskatalog_Kayi.xlsx",
                "sha256": "a" * 64,
                "size": 123,
                "items": [{"code": "S1002", "description": "Waschtisch montieren", "category": "Sanitär", "unit": "Stk.", "purchase_price": None, "sales_price": "129.00"}],
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "prices.json.gz"
            with gzip.open(fixture, "wt", encoding="utf-8") as handle:
                json.dump(payload, handle)
            output = Path(directory) / "normalized"
            call_command("import_normalized_prices", str(fixture), "--output-dir", str(output))
            call_command("import_normalized_prices", str(fixture), "--output-dir", str(output))
            self.assertEqual(PriceSource.objects.filter(organization=org).count(), 1)
            self.assertEqual(PriceItem.objects.filter(organization=org).count(), 1)
            self.assertEqual(CatalogItem.objects.filter(organization=org, code="S1002").count(), 1)
            self.assertTrue(any(output.rglob("*.csv")))
            self.assertFalse(PriceSource.objects.filter(organization__settings__is_demo=True).exists())
