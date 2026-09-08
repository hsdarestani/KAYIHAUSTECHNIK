#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

required_files=(
  manage.py
  config/settings.py
  erp/models.py
  templates/rebuild/base.html
  static/js/app.js
  native/package.json
  compose.yaml
  Dockerfile
  requirements.txt
)

for path in "${required_files[@]}"; do
  test -f "$path" || { echo "Canonical source file missing: $path" >&2; exit 1; }
  git ls-files --error-unmatch "$path" >/dev/null 2>&1 || {
    echo "Canonical source is not tracked: $path" >&2
    exit 1
  }
done

test -d mobile || { echo "Canonical mobile source missing" >&2; exit 1; }
test -d native || { echo "Canonical native source missing" >&2; exit 1; }

echo "A+Bau canonical source checkout verified; no legacy assembly required."
