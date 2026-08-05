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
        self.assertEqual(len(parts), 20)
        assembled = b"".join(part.read_bytes() for part in parts)
        self.assertEqual(len(assembled), 216320)
        self.assertEqual(
            hashlib.sha256(assembled).hexdigest(),
            "b127df3fb0b33e6f846aae477eb04cc8ac943e4461e35a2d74fcbc0e9161c113",
        )
        ciphertext = base64.b64decode(assembled, validate=True)
        self.assertEqual(len(ciphertext), 162240)
        self.assertEqual(
            hashlib.sha256(ciphertext).hexdigest(),
            "e954dba997af20e8618954c97fceb8868405fe03197106f7c3724879ce929263",
        )
        wrapped_key_b64 = (encrypted / "key.enc.b64").read_bytes()
        self.assertEqual(
            hashlib.sha256(wrapped_key_b64).hexdigest(),
            "5eb1c1fa3e604b65eb846c755ca0cd782c0aa15656dcc53983ff2ae3de1e4095",
        )
        wrapped_key = base64.b64decode(wrapped_key_b64, validate=True)
        self.assertEqual(len(wrapped_key), 384)
        self.assertEqual(
            hashlib.sha256(wrapped_key).hexdigest(),
            "70d9ef42d22dec38071e68981f938036d6acde7fcce7ace1af5e059169e5509b",
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
            files = list(output.rglob("*.csv"))
            self.assertEqual(len(files), 1)
            self.assertIn("a" * 16, files[0].name)
            self.assertFalse(PriceSource.objects.filter(organization__settings__is_demo=True).exists())

    def test_equal_paths_from_distinct_sources_create_distinct_files(self):
        org = Organization.objects.create(name="KAYI Haustechnik")
        payload = {
            "version": 1,
            "sources": [
                {
                    "path": "lieferanten/preise/Preisliste.xlsx",
                    "filename": "Preisliste.xlsx",
                    "sha256": "a" * 64,
                    "size": 100,
                    "items": [{
                        "code": "A-1",
                        "description": "Quelle A",
                        "category": "Test",
                        "unit": "Stk.",
                        "purchase_price": "1.00",
                        "sales_price": "2.00",
                    }],
                },
                {
                    "path": "lieferanten/preise/Preisliste.xlsx",
                    "filename": "Preisliste.xlsx",
                    "sha256": "b" * 64,
                    "size": 101,
                    "items": [{
                        "code": "B-1",
                        "description": "Quelle B",
                        "category": "Test",
                        "unit": "Stk.",
                        "purchase_price": "3.00",
                        "sales_price": "4.00",
                    }],
                },
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "prices.json.gz"
            with gzip.open(fixture, "wt", encoding="utf-8") as handle:
                json.dump(payload, handle)
            output = Path(directory) / "normalized"
            call_command("import_normalized_prices", str(fixture), "--output-dir", str(output))
            files = sorted(output.rglob("*.csv"))
            self.assertEqual(PriceSource.objects.filter(organization=org).count(), 2)
            self.assertEqual(PriceItem.objects.filter(organization=org).count(), 2)
            self.assertEqual(len(files), 2)
            self.assertEqual({path.name for path in files}, {
                f"Preisliste.{('a' * 16)}.normalized.csv",
                f"Preisliste.{('b' * 16)}.normalized.csv",
            })
