#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "Rebuilding canonical source from the legacy archive + patch chain..."
bash scripts/unpack-source.sh
python3 scripts/final_production_hardening_20260821.py
python3 scripts/tooltime_user_settings_import.py
python3 scripts/mobile_invoice_menu_fix.py
echo "Legacy source rebuild completed. Review git diff before promoting regenerated output."
