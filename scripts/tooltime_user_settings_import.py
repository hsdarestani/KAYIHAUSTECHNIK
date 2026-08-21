from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FIXTURE = ROOT / "reference_data" / "tooltime_user_settings.json"
TARGET_FIXTURE = ROOT / "erp" / "fixtures" / "tooltime_user_settings.json"
COMMAND = ROOT / "erp" / "management" / "commands" / "apply_tooltime_user_settings.py"
TEST = ROOT / "tests" / "test_tooltime_user_settings_import_contract.py"
MARKER = "A+BAU TOOLTIME USER SETTINGS IMPORT 2026-08-21"


def install_fixture() -> None:
    if not SOURCE_FIXTURE.exists():
        raise RuntimeError("Captured ToolTime settings fixture is missing")
    TARGET_FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    TARGET_FIXTURE.write_text(SOURCE_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")


def install_command() -> None:
    COMMAND.parent.mkdir(parents=True, exist_ok=True)
    COMMAND.write_text(r'''from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from erp.models import Organization, ToolTimeCommercialProfile, ToolTimeTextTemplate


FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "tooltime_user_settings.json"


def deep_merge(target, incoming):
    result = deepcopy(target or {})
    for key, value in (incoming or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


class Command(BaseCommand):
    help = "Import the product-owner supplied ToolTime settings into one organization's persisted settings profile."

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
            merged = deep_merge(profile.settings, profile_patch)

            if options["dry_run"]:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING(
                    f"Dry run: {organization.name}; {len(profile_patch)} settings groups and {len(templates)} templates validated."
                ))
                return

            profile.settings = merged
            profile.save(update_fields=["settings", "updated_at"])

            # The editor consumes real database-backed text templates. Keep one
            # captured Standard row per kind instead of baking customer copy into HTML.
            for row in templates:
                document_kind = row.get("document_kind")
                text_kind = row.get("text_kind")
                if document_kind not in {"quote", "invoice"} or text_kind not in {"intro", "closing"}:
                    raise CommandError(f"Invalid text template kind: {document_kind}/{text_kind}")
                if row.get("is_standard"):
                    ToolTimeTextTemplate.objects.filter(
                        organization=organization,
                        document_kind=document_kind,
                        text_kind=text_kind,
                        is_standard=True,
                    ).update(is_standard=False)
                ToolTimeTextTemplate.objects.update_or_create(
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

        self.stdout.write(self.style.SUCCESS(
            f"ToolTime settings imported for {organization.name}: {len(profile_patch)} settings groups, {len(templates)} database templates."
        ))
''', encoding="utf-8")
    compile(COMMAND.read_text(encoding="utf-8"), str(COMMAND), "exec")


def install_contract_test() -> None:
    TEST.parent.mkdir(parents=True, exist_ok=True)
    TEST.write_text(r'''import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_tooltime_user_settings_are_fixture_backed_not_template_hardcoded():
    fixture = ROOT / "erp" / "fixtures" / "tooltime_user_settings.json"
    command = ROOT / "erp" / "management" / "commands" / "apply_tooltime_user_settings.py"
    assert fixture.exists()
    assert command.exists()
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    cfg = payload["commercial_profile"]
    assert cfg["numbering"]["invoice"] == {"prefix": "R-", "start": 145}
    assert cfg["numbering"]["quote"] == {"prefix": "A-", "start": 220}
    assert cfg["communication"]["reply_email"] == "info@kayi-haustechnik.de"
    assert cfg["layout"]["logo_position"] == "right"
    assert cfg["layout"]["logo_size"] == "large"
    assert [row["label"] for row in cfg["appointments"]["types"]] == [
        "Besichtigung", "Ausführung", "Beratung", "Abnahme", "Wartung", "Notfall", "Intern"
    ]
    source = command.read_text(encoding="utf-8")
    assert "profile.settings = merged" in source
    assert "ToolTimeTextTemplate.objects.update_or_create" in source


def test_invoice_copy_is_stored_as_database_templates():
    payload = json.loads((ROOT / "erp" / "fixtures" / "tooltime_user_settings.json").read_text(encoding="utf-8"))
    rows = {(row["document_kind"], row["text_kind"]): row for row in payload["text_templates"]}
    assert rows[("invoice", "intro")]["body"] == "nachfolgend berechnen wir Ihnen wie vorab besprochen:"
    assert rows[("invoice", "closing")]["body"].startswith("Vielen Dank für Ihren Auftrag!")
''', encoding="utf-8")
    compile(TEST.read_text(encoding="utf-8"), str(TEST), "exec")


def run() -> None:
    install_fixture()
    install_command()
    install_contract_test()
    print(f"{MARKER}: captured ToolTime choices are installed as a database import fixture, not UI constants.")


if __name__ == "__main__":
    run()
