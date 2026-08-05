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
        parts = sorted(encrypted.glob("payload.part-*"))
        self.assertEqual(len(parts), 26)
        assembled = b"".join(part.read_bytes() for part in parts)
        self.assertEqual(len(assembled), 814296)
        self.assertEqual(
            hashlib.sha256(assembled).hexdigest(),
            "ffd3e1333e003e0360b747d1d0b1d56272a4824b430b0dd3fa9a91033a911821",
        )
        ciphertext = base64.b64decode(assembled, validate=True)
        self.assertEqual(len(ciphertext), 610720)
        self.assertEqual(
            hashlib.sha256(ciphertext).hexdigest(),
            "c1ab1aa6667f84700019b420b4d677726f674f63802e066c2ceb88bef84ace38",
        )
        wrapped_key_b64 = (encrypted / "key.enc.b64").read_bytes()
        self.assertEqual(
            hashlib.sha256(wrapped_key_b64).hexdigest(),
            "80359b4f2750fee4c3b5915d6ab647f7fe45c97e3d267000a07daa785443fca8",
        )
        wrapped_key = base64.b64decode(wrapped_key_b64, validate=True)
        self.assertEqual(len(wrapped_key), 384)
        self.assertEqual(
            hashlib.sha256(wrapped_key).hexdigest(),
            "6a699ce73d98968a2333e9f773cdda3c9cd3e1c452bb19075dcaf6f77996710c",
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
                "items": [{
                    "code": "S1002",
                    "description": "Waschtisch montieren",
                    "category": "Sanitär",
                    "unit": "Stk.",
                    "purchase_price": None,
                    "sales_price": "129.00",
                }],
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
