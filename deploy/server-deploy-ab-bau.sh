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

required = (
    '"ORGANIZATION_NAME=A+Bau"',
    "name='A+Bau'",
    "'ORGANIZATION_NAME': 'A+Bau'",
    "Organization.objects.filter(name='A+Bau').first()",
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
