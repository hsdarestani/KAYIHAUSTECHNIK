#!/bin/sh
set -eu

# Production still uses the established technical paths/domain (/opt/kayi,
# kayi.smarbiz.sbs), but the tenant visible to the application is now A+Bau.
# Patch a disposable copy of the proven deployment script so its internal
# git reset cannot undo the rebrand compatibility changes while it is running.
TMP_SCRIPT="$(mktemp /tmp/ab-bau-server-deploy.XXXXXX.sh)"
cleanup() {
  rm -f "$TMP_SCRIPT"
}
trap cleanup EXIT INT TERM
cp deploy/server-deploy.sh "$TMP_SCRIPT"

python3 - "$TMP_SCRIPT" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")

replacements = {
    '"ORGANIZATION_NAME=KAYI Haustechnik"': '"ORGANIZATION_NAME=A+Bau"',
    "name='KAYI Haustechnik'": "name='A+Bau'",
    "Organization.objects.filter(name='KAYI Haustechnik')": "Organization.objects.filter(name='A+Bau')",
    "KAYI release data verified:": "A+Bau release data verified:",
    "KAYI deployment healthy and user-flow smoke tests passed": "A+Bau deployment healthy and user-flow smoke tests passed",
}
for old, new in replacements.items():
    text = text.replace(old, new)

# Existing production .env files predate the rebrand. server-deploy.sh updates a
# small forced-value mapping on every release, so add ORGANIZATION_NAME there as
# well instead of relying only on the value used when a new .env is created.
forced_anchor = "    'COOKIE_SECURE': '1',\n}"
if forced_anchor in text:
    text = text.replace(
        forced_anchor,
        "    'COOKIE_SECURE': '1',\n    'ORGANIZATION_NAME': 'A+Bau',\n}",
        1,
    )
elif "'ORGANIZATION_NAME': 'A+Bau'" not in text:
    raise SystemExit("Could not install A+Bau ORGANIZATION_NAME into deployment environment")

# Captured ToolTime account values are deliberately not rendered as constants.
# Build a fixture-backed Django command into the assembled source before the
# Docker image is built, then apply it to the real A+Bau organization after
# migrations and tenant bootstrap have completed.
assembly_anchor = "bash scripts/unpack-source.sh\n"
installer_command = "python3 scripts/tooltime_user_settings_import.py\n"
if installer_command not in text:
    if assembly_anchor not in text:
        raise SystemExit("Could not find source assembly anchor for ToolTime settings importer")
    text = text.replace(assembly_anchor, assembly_anchor + installer_command, 1)

organization_anchor = (
    "dc run --rm web python manage.py shell -c \"from erp.models import Organization; "
    "Organization.objects.get_or_create(name='A+Bau', defaults={'settings': {}})\"\n"
)
settings_command = "dc run --rm web python manage.py apply_tooltime_user_settings --organization 'A+Bau'\n"
if settings_command not in text:
    if organization_anchor not in text:
        raise SystemExit("Could not find A+Bau organization bootstrap anchor for ToolTime settings import")
    text = text.replace(organization_anchor, organization_anchor + settings_command, 1)

required = (
    '"ORGANIZATION_NAME=A+Bau"',
    "name='A+Bau'",
    "'ORGANIZATION_NAME': 'A+Bau'",
    "Organization.objects.filter(name='A+Bau').first()",
    installer_command.strip(),
    settings_command.strip(),
)
missing = [value for value in required if value not in text]
if missing:
    raise SystemExit(f"A+Bau deployment compatibility incomplete: {missing}")

# No business-data delete/merge is performed here. The migration already renamed
# the established tenant; this wrapper only prevents the deploy script from
# recreating/verifying a second empty tenant under the legacy display name.
path.write_text(text, encoding="utf-8")
PY

chmod 700 "$TMP_SCRIPT"
exec sh "$TMP_SCRIPT"
