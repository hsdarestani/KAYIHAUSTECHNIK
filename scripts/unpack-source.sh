#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ "${KAYI_FORCE_LEGACY_REBUILD:-0}" != "1" ]; then
  if git ls-files --error-unmatch manage.py config/settings.py erp/models.py templates/rebuild/base.html static/js/app.js native/package.json compose.yaml >/dev/null 2>&1; then
    bash scripts/verify-canonical-source.sh
    echo "Canonical source detected; legacy archive + patch assembly skipped."
    exit 0
  fi
fi

exec bash scripts/unpack-source-legacy.sh
