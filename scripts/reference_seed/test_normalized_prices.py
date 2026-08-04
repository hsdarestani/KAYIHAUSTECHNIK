import base64
import gzip
import hashlib
import json
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from erp.models import CatalogItem, Organization, PriceItem, PriceSource


class NormalizedPriceImportTests(TestCase):
    def test_encrypted_fixture_integrity(self):
        root = Path(__file__).resolve().parents[1]
        encrypted = root / "reference_data" / "encrypted"
        assembled = (
            (encrypted / "prices.part-00").read_bytes()[:8000]
            + b"".join((encrypted / f"prices.part-{index:02d}").read_bytes() for index in range(1, 6))
        )
        self.assertEqual(len(assembled), 85720)
        self.assertEqual(
            hashlib.sha256(assembled).hexdigest(),
            "fba909127ab186258355cb76de5a73ddfdf5e78a5aa92a5e182f7a6f5b3525d0",
        )
        ciphertext = base64.b64decode(assembled, validate=True)
        self.assertEqual(
            hashlib.sha256(ciphertext).hexdigest(),
            "e1906a43c44023045e772e8921c51fb1acd9f26e3d9c91838b842fc9c3ef3651",
        )
        wrapped_key_b64 = (encrypted / "key.enc.b64").read_bytes()
        self.assertEqual(
            hashlib.sha256(wrapped_key_b64).hexdigest(),
            "d560705add12afde62f91af0bb2e913031d9d2466cf64e8b0e000d72f89b4979",
        )
        wrapped_key = base64.b64decode(wrapped_key_b64, validate=True)
        self.assertEqual(
            hashlib.sha256(wrapped_key).hexdigest(),
            "7f411bb00e4e2a7f478c5987529761e3eda2233a94e70d5f74fef55b96607e1a",
        )

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
