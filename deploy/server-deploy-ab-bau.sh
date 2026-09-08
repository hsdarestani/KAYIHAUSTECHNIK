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
# Build the importer and the final screenshot-review hardening into the assembled
# source before Docker builds the production image.
assembly_anchor = "bash scripts/unpack-source.sh\n"
hardening_command = "python3 scripts/final_production_hardening_20260821.py\n"
installer_command = "python3 scripts/tooltime_user_settings_import.py\n"
mobile_menu_fix_command = "python3 scripts/mobile_invoice_menu_fix.py\n"
pdf_preview_hardening_command = "python3 scripts/pdf_preview_embed_hardening.py\n"
# Django intentionally keeps X_FRAME_OPTIONS=DENY globally, while the dedicated
# PDF preview views opt into SAMEORIGIN. Caddy must not overwrite those per-view
# headers with a blanket DENY after the response leaves Django.
frame_header_fix_command = "test -f deploy/Caddyfile && sed -i '/X-Frame-Options/d' deploy/Caddyfile && ! grep -Fq 'X-Frame-Options' deploy/Caddyfile\n"
if frame_header_fix_command not in text:
    if assembly_anchor not in text:
        raise SystemExit("Could not find source assembly anchor for PDF preview proxy header fix")
    text = text.replace(assembly_anchor, assembly_anchor + frame_header_fix_command, 1)
if pdf_preview_hardening_command not in text:
    frame_anchor = assembly_anchor + frame_header_fix_command
    if frame_anchor in text:
        text = text.replace(frame_anchor, frame_anchor + pdf_preview_hardening_command, 1)
    elif assembly_anchor in text:
        text = text.replace(assembly_anchor, assembly_anchor + pdf_preview_hardening_command, 1)
    else:
        raise SystemExit("Could not find source assembly anchor for PDF preview response hardening")
if hardening_command not in text:
    if assembly_anchor not in text:
        raise SystemExit("Could not find source assembly anchor for final production hardening")
    text = text.replace(assembly_anchor, assembly_anchor + hardening_command, 1)
if installer_command not in text:
    hardening_anchor = assembly_anchor + hardening_command
    if hardening_anchor in text:
        text = text.replace(hardening_anchor, hardening_anchor + installer_command, 1)
    elif assembly_anchor in text:
        text = text.replace(assembly_anchor, assembly_anchor + installer_command, 1)
    else:
        raise SystemExit("Could not find source assembly anchor for ToolTime settings importer")
if mobile_menu_fix_command not in text:
    installer_anchor = hardening_command + installer_command
    if installer_anchor in text:
        text = text.replace(installer_anchor, hardening_command + installer_command + mobile_menu_fix_command, 1)
    elif installer_command in text:
        text = text.replace(installer_command, installer_command + mobile_menu_fix_command, 1)
    else:
        raise SystemExit("Could not find production assembly anchor for mobile invoice menu fix")

organization_anchor = (
    "dc run --rm web python manage.py shell -c \"from erp.models import Organization; "
    "Organization.objects.get_or_create(name='A+Bau', defaults={'settings': {}})\"\n"
)
settings_command = "dc run --rm web python manage.py apply_tooltime_user_settings --organization 'A+Bau'\n"
if settings_command not in text:
    if organization_anchor not in text:
        raise SystemExit("Could not find A+Bau organization bootstrap anchor for ToolTime settings import")
    text = text.replace(organization_anchor, organization_anchor + settings_command, 1)

# Production is only considered healthy when the same built image passes the full
# mobile regression suite on two phone viewports in addition to the desktop smoke.
desktop_smoke = "    python scripts/production_browser_smoke.py http://127.0.0.1:8001\n"
mobile_smoke = "    python scripts/mobile_browser_smoke.py http://127.0.0.1:8001\n"
if mobile_smoke not in text:
    if desktop_smoke not in text:
        raise SystemExit("Could not find production browser smoke anchor for mobile audit")
    text = text.replace(desktop_smoke, desktop_smoke + mobile_smoke, 1)

required = (
    '"ORGANIZATION_NAME=A+Bau"',
    "name='A+Bau'",
    "'ORGANIZATION_NAME': 'A+Bau'",
    "Organization.objects.filter(name='A+Bau').first()",
    frame_header_fix_command.strip(),
    pdf_preview_hardening_command.strip(),
    hardening_command.strip(),
    installer_command.strip(),
    mobile_menu_fix_command.strip(),
    settings_command.strip(),
    mobile_smoke.strip(),
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
sh "$TMP_SCRIPT"

# deploy/Caddyfile is a single-file bind mount. sed -i replaces the host inode,
# so an already-running Caddy container can keep seeing the old inode even though
# the host path is correct. Validate the host-side file first, then recreate only
# Caddy so Docker establishes a fresh bind mount to the updated inode. A plain
# restart is not sufficient for this bind-mount case.
if docker compose version >/dev/null 2>&1; then
  dc() { docker compose "$@"; }
else
  dc() { docker-compose "$@"; }
fi

test -f deploy/Caddyfile
! grep -Fq 'X-Frame-Options' deploy/Caddyfile
dc up -d --force-recreate caddy
sleep 2
dc exec -T caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
curl -fsS --retry 5 --retry-delay 1 https://kayi.smarbiz.sbs/login/ >/dev/null
dc ps caddy
