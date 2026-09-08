from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from erp.models import Organization, ToolTimeCommercialProfile, ToolTimeTextTemplate


FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "tooltime_user_settings.json"


def merge_missing(current, defaults):
    """Seed only missing keys; values edited by the tenant always win."""
    result = deepcopy(current or {})
    for key, value in (defaults or {}).items():
        if key not in result:
            result[key] = deepcopy(value)
        elif isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_missing(result[key], value)
    return result


class Command(BaseCommand):
    help = "Seed product-owner supplied ToolTime/A+Bau defaults without overwriting tenant edits."

    def add_arguments(self, parser):
        parser.add_argument("--organization", required=True, help="Exact Organization.name to update")
        parser.add_argument("--fixture", default=str(FIXTURE), help="Optional settings fixture path")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        fixture_path = Path(options["fixture"])
        if not fixture_path.exists():
            raise CommandError(f"Settings fixture not found: {fixture_path}")
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != 1:
            raise CommandError("Unsupported ToolTime settings fixture schema")

        try:
            organization = Organization.objects.get(name=options["organization"])
        except Organization.DoesNotExist as exc:
            raise CommandError(f"Organization not found: {options['organization']}") from exc

        profile_patch = payload.get("commercial_profile") or {}
        templates = payload.get("text_templates") or []

        with transaction.atomic():
            profile, _ = ToolTimeCommercialProfile.objects.get_or_create(
                organization=organization,
                defaults={"settings": {}},
            )
            merged = merge_missing(profile.settings, profile_patch)

            if options["dry_run"]:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING(
                    f"Dry run: {organization.name}; {len(profile_patch)} settings groups and {len(templates)} templates validated."
                ))
                return

            profile.settings = merged
            profile.save(update_fields=["settings", "updated_at"])

            for row in templates:
                document_kind = row.get("document_kind")
                text_kind = row.get("text_kind")
                if document_kind not in {"quote", "invoice"} or text_kind not in {"intro", "closing"}:
                    raise CommandError(f"Invalid text template kind: {document_kind}/{text_kind}")

                template, created = ToolTimeTextTemplate.objects.get_or_create(
                    organization=organization,
                    document_kind=document_kind,
                    text_kind=text_kind,
                    title=row.get("title") or "Standard",
                    defaults={
                        "salutation": row.get("salutation") or "",
                        "body": row.get("body") or "",
                        "is_standard": bool(row.get("is_standard")),
                        "sort_order": int(row.get("sort_order") or 1),
                    },
                )
                # Empty placeholder rows from older Settings screens are safe to seed.
                # Any non-empty tenant text is a deliberate edit and is never replaced.
                changed = False
                if not created and not str(template.body or "").strip() and str(row.get("body") or "").strip():
                    template.body = row.get("body") or ""
                    changed = True
                if not created and not str(template.salutation or "").strip() and str(row.get("salutation") or "").strip():
                    template.salutation = row.get("salutation") or ""
                    changed = True
                if row.get("is_standard") and not template.is_standard:
                    has_other_standard = ToolTimeTextTemplate.objects.filter(
                        organization=organization,
                        document_kind=document_kind,
                        text_kind=text_kind,
                        is_standard=True,
                    ).exclude(pk=template.pk).exists()
                    if not has_other_standard:
                        template.is_standard = True
                        changed = True
                if changed:
                    template.save()

        self.stdout.write(self.style.SUCCESS(
            f"A+Bau settings seeded for {organization.name}: tenant edits preserved; {len(templates)} document defaults checked."
        ))
