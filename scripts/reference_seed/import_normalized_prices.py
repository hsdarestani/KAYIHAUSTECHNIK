from __future__ import annotations

import csv
import gzip
import json
import lzma
import mimetypes
import re
from decimal import Decimal
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from erp.models import CatalogItem, Organization, PriceItem, PriceSource, Supplier
from erp.services.reference_data import _detect


def money(value):
    return Decimal(str(value)).quantize(Decimal("0.01")) if value not in (None, "") else None


class Command(BaseCommand):
    help = "Importiert die verschlüsselt übertragene, normalisierte KAYI-Preisbibliothek."

    def add_arguments(self, parser):
        parser.add_argument("fixture")
        parser.add_argument("--organization-id", type=int)
        parser.add_argument("--output-dir", default="/reference-data/normalized")

    @transaction.atomic
    def handle(self, *args, **options):
        fixture = Path(options["fixture"])
        if not fixture.is_file():
            raise CommandError(f"Preisdaten nicht gefunden: {fixture}")
        org = (
            Organization.objects.filter(pk=options.get("organization_id")).first()
            if options.get("organization_id")
            else Organization.objects.exclude(settings__is_demo=True).first() or Organization.objects.first()
        )
        if not org:
            raise CommandError("Keine Organisation vorhanden.")
        try:
            if fixture.suffix.lower() == ".xz":
                with lzma.open(fixture, "rt", encoding="utf-8") as handle:
                    compact = json.load(handle)
                if not isinstance(compact, list) or len(compact) != 2 or compact[0] != 1:
                    raise ValueError("compact schema")
                payload = {"version": 1, "sources": []}
                for source in compact[1]:
                    path, filename, sha256, size, rows = source
                    payload["sources"].append({
                        "path": path,
                        "filename": filename,
                        "sha256": sha256,
                        "size": size,
                        "items": [
                            {
                                "code": row[0],
                                "description": row[1],
                                "category": row[2],
                                "unit": row[3],
                                "purchase_price": row[4],
                                "sales_price": row[5],
                            }
                            for row in rows
                        ],
                    })
            else:
                with gzip.open(fixture, "rt", encoding="utf-8") as handle:
                    payload = json.load(handle)
        except Exception as exc:
            raise CommandError(f"Preisbibliothek ist ungültig: {exc}") from exc
        if payload.get("version") != 1 or not isinstance(payload.get("sources"), list):
            raise CommandError("Nicht unterstützte Preisbibliothek.")

        output_root = Path(options["output_dir"])
        output_root.mkdir(parents=True, exist_ok=True)
        total_rows = 0
        imported_sources = 0
        for source_data in payload["sources"]:
            original_path = Path(source_data["path"])
            source_sha = str(source_data.get("sha256") or "").lower()
            if not re.fullmatch(r"[0-9a-f]{64}", source_sha):
                raise CommandError(f"Ungültiger SHA256 für Preisquelle: {source_data.get('path', '')}")
            kind, display_name, supplier_name = _detect(original_path)
            supplier = None
            if supplier_name:
                supplier, _ = Supplier.objects.get_or_create(
                    organization=org,
                    name=supplier_name,
                    defaults={
                        "number": re.sub(r"[^A-Z0-9]", "", supplier_name.upper())[:30]
                        or f"L{Supplier.objects.filter(organization=org).count() + 1:04d}"
                    },
                )
            items = source_data.get("items") or []
            source, _ = PriceSource.objects.update_or_create(
                organization=org,
                sha256=source_sha,
                defaults={
                    "supplier": supplier,
                    "name": display_name,
                    "kind": kind,
                    "original_filename": source_data["filename"],
                    "mime_type": mimetypes.guess_type(source_data["filename"])[0] or "application/octet-stream",
                    "imported_at": timezone.now(),
                    "imported_rows": len(items),
                    "import_summary": {
                        "normalized_secure_import": True,
                        "original_path": source_data["path"],
                        "original_size": source_data.get("size", 0),
                        "rows": len(items),
                    },
                    "active": True,
                },
            )
            source.items.all().delete()
            PriceItem.objects.bulk_create(
                [
                    PriceItem(
                        organization=org,
                        source=source,
                        code=str(item.get("code") or "")[:120],
                        description=str(item.get("description") or "")[:5000],
                        category=str(item.get("category") or "")[:180],
                        unit=str(item.get("unit") or "")[:40],
                        purchase_price=money(item.get("purchase_price")),
                        sales_price=money(item.get("sales_price")),
                        external_data={"normalized_from": source_data["path"]},
                    )
                    for item in items
                ],
                batch_size=1000,
            )

            safe_dir = output_root / re.sub(r"[^A-Za-z0-9._-]+", "_", str(original_path.parent))
            safe_dir.mkdir(parents=True, exist_ok=True)
            # Different commercial sources can legitimately have the same parent and
            # stem. Include a deterministic SHA token so no normalized file can
            # overwrite another source while keeping the filename human-readable.
            normalized_file = safe_dir / f"{original_path.stem}.{source_sha[:16]}.normalized.csv"
            with normalized_file.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle, delimiter=";")
                writer.writerow(["Code", "Beschreibung", "Kategorie", "Einheit", "Einkaufspreis", "Verkaufspreis"])
                for item in items:
                    writer.writerow([
                        item.get("code") or "",
                        item.get("description") or "",
                        item.get("category") or "",
                        item.get("unit") or "",
                        item.get("purchase_price") or "",
                        item.get("sales_price") or "",
                    ])
            with normalized_file.open("rb") as handle:
                source.raw_file.save(normalized_file.name, File(handle), save=False)
            source.save(update_fields=["raw_file", "updated_at"])

            if kind == PriceSource.Kind.CATALOG:
                for item in items:
                    code = str(item.get("code") or "")[:80]
                    if not code:
                        continue
                    CatalogItem.objects.update_or_create(
                        organization=org,
                        code=code,
                        defaults={
                            "name": str(item.get("description") or code)[:240],
                            "description": str(item.get("description") or ""),
                            "unit": str(item.get("unit") or "Stk.")[:30],
                            "purchase_price": money(item.get("purchase_price")) or Decimal("0"),
                            "sales_price": money(item.get("sales_price")) or money(item.get("purchase_price")) or Decimal("0"),
                            "supplier": supplier_name,
                            "external_codes": {"price_source_id": source.pk, "original_path": source_data["path"]},
                            "active": True,
                        },
                    )
            imported_sources += 1
            total_rows += len(items)

        self.stdout.write(
            self.style.SUCCESS(
                f"{imported_sources} Preisquellen und {total_rows} Positionen sicher importiert; normalisierte Serverdateien: {output_root}"
            )
        )
