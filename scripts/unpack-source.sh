#!/usr/bin/env bash
set -euo pipefail

EXPECTED_SHA="b2b84d7b372316472ffc9e7483b52757dc1b8a36104c4f8c361394b29adc42fa"
ARCHIVE="${TMPDIR:-/tmp}/kayi-source.tar.gz"
REPAIRED_DIR="${TMPDIR:-/tmp}/kayi-source-parts"
rm -rf "$REPAIRED_DIR"
mkdir -p "$REPAIRED_DIR"

python3 - "$REPAIRED_DIR" "$ARCHIVE" "$EXPECTED_SHA" <<'PY'
from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path

repaired_dir = Path(sys.argv[1])
archive = Path(sys.argv[2])
expected_archive_sha = sys.argv[3]
block_size = 2000
expected = {
    "01": {
        "length": 14000,
        "hashes": [
            "f9da49766101b7ad33b7aa8193a0f3cd4cd3bdeb8951f92d6b9640665cb52e95",
            "803bc744be9870505fd59a8615ed1e15397e59ae0ffe1a464bd6f1e3afd84378",
            "c2e037f3e68a6a5651554930dbe57706ac4f211dab8b39e89a5fcda3e33bd417",
            "e46b32f0ad1916011e43a5de13f0ba94ac01c2e75757eeb267ab31e1f930f752",
            "ddf69e84d190a248aaa41d2ae216ab77986dece30cf04bda2c123aef60ca2fce",
            "6d22f3a47a67d9876eb338a5006d7e19b0a30c6f380511dcf209e767269015cf",
            "6f8e8b3398ca5c652d0460f8f0f6c84af6d57609e49dbba4f34cb72007ecdfde",
        ],
    },
    "03": {
        "length": 14000,
        "hashes": [
            "bb70398a11cf8c0d47fdcd6ec6cff89d4de5e17512a6ec4537ebe8b14245b548",
            "3f24a9b0b902885a68da74532befaa255bf036a679451675048efc792981ac2c",
            "a7ca827d66c2a57ed27642de5b08f121d6af23c98c0a737d1697e355d32b7669",
            "7a4405b7a30d0a8bd9da335380ea66125c02c9ed0290e1af0736a421006fc68b",
            "a1ee50dd256d1512987bc24408437d2d7752c8d12dc56f60e346339a57d3af24",
            "a6d06c5aacb34f36ad382c14fe5df5f7f318115e4ecbbba7bd075d54e5f09171",
            "125ef3aa426d4d992187d3e8d08ffff87e3f0df79e31fedbc8d993fa32f277b9",
        ],
    },
    "04": {
        "length": 14000,
        "hashes": [
            "9ee0df5d866250177b6de367cecdc67fe9b4074acb8db5d4ddfd595b19c18398",
            "de8c6ab855c8fb0063fb1b9d4d9e050e9c43eff0f6d582f8c8a29f5cefd28e1f",
            "eba9d03aeeb981b65ff4276d14024174e475468cfd41bd60e5c102dbc8684d3f",
            "32db1946fc112519ffef3f4582660410d413f3cf1ceb0877dc0d43e7b4ba4d83",
            "3ca8370db3ada3bfe421ac1bd0bddae9fb08cad5e551edf1a23b16f848eed3c6",
            "441088067cf367ab16b3c7e94bb1aed9ecda5b8a293c8387071f84713d42c8a2",
            "1c6aa3d2793a74a263e74a407e280ab337dba9fb4ca54a31d73d507ab5d3183b",
        ],
    },
}

errors: list[dict[str, object]] = []
for part_id, spec in expected.items():
    source = Path(f".bootstrap/source.part-{part_id}")
    text = source.read_text(encoding="utf-8")
    patches_dir = Path(".bootstrap/patches")
    for block_index in range(len(spec["hashes"])):
        patch = patches_dir / f"source.part-{part_id}.block-{block_index:02d}"
        if patch.exists():
            replacement = patch.read_text(encoding="utf-8")
            start = block_index * block_size
            end = min(start + block_size, len(text))
            text = text[:start] + replacement + text[end:]
    if len(text) > spec["length"]:
        text = text[: spec["length"]]

    actual_hashes = [
        hashlib.sha256(text[offset : offset + block_size].encode()).hexdigest()
        for offset in range(0, len(text), block_size)
    ]
    mismatches = [
        index
        for index, expected_hash in enumerate(spec["hashes"])
        if index >= len(actual_hashes) or actual_hashes[index] != expected_hash
    ]
    if len(actual_hashes) > len(spec["hashes"]):
        mismatches.extend(range(len(spec["hashes"]), len(actual_hashes)))
    if len(text) != spec["length"] or mismatches:
        errors.append(
            {
                "part": part_id,
                "expected_length": spec["length"],
                "actual_length": len(text),
                "mismatched_blocks": mismatches,
            }
        )
    (repaired_dir / f"source.part-{part_id}").write_text(text, encoding="utf-8")

if errors:
    print("Source payload verification failed:")
    print(json.dumps(errors, indent=2))
    raise SystemExit(1)

encoded_parts: list[str] = []
for source in sorted(Path(".bootstrap").glob("source.part-*")):
    repaired = repaired_dir / source.name
    selected = repaired if repaired.exists() else source
    encoded_parts.append(selected.read_text(encoding="utf-8"))
try:
    archive_bytes = base64.b64decode("".join(encoded_parts), validate=True)
except ValueError as exc:
    raise SystemExit(f"Source archive base64 verification failed: {exc}") from exc
actual_archive_sha = hashlib.sha256(archive_bytes).hexdigest()
if actual_archive_sha != expected_archive_sha:
    raise SystemExit(
        f"Source archive checksum mismatch: expected {expected_archive_sha}, got {actual_archive_sha}"
    )
archive.write_bytes(archive_bytes)
print(f"{archive}: OK")
PY

tar -xzf "$ARCHIVE"
python3 scripts/source_overrides.py
python3 scripts/cache_bust_overrides.py
python3 scripts/project_wizard_visibility_fix.py
python3 scripts/leistungsnachweise_index.py
python3 scripts/ux_flow_hardening.py
python3 scripts/restore_nine_step_wizard.py
python3 scripts/event_form_layout.py
python3 scripts/event_form_layout_fix.py
python3 scripts/global_form_polish.py
python3 scripts/global_form_polish_balance_fix.py
python3 scripts/global_form_smoke_fix.py
python3 scripts/ashkan_ux_fixes.py
python3 scripts/integration_overrides.py
# Primary product layer.
python3 scripts/install_tooltime_rebuild.py
# Final business rules must run after every UI/field overlay. This guarantees
# B&O price provenance and office approval cannot be overwritten by an older
# KAYI Next layer during CI or production assembly.
python3 scripts/install_bo_pricing.py
python3 scripts/install_bo_direct_search.py
python3 scripts/install_manager_review.py
# First finish all existing A+Bau visual/mobile compatibility layers.
python3 scripts/ab_bau_browser_smoke_compat.py
# Then activate the uploaded PNG and confirmed agent so no older mobile layer can
# restore the legacy WebP reference or overwrite the multi-step assistant UI.
python3 scripts/install_ab_bau_agent_orchestrator.py
# Final branding override: keep the uploaded PNG completely free-floating in the
# sidebar with no frame, panel, rounded crop or legacy background around it.
python3 scripts/ab_bau_logo_frame_fix.py
# Runtime hotfix runs last so no older overlay can reintroduce the duplicate time
# handler or the 500-item synchronous catalog pricing path.
python3 scripts/ab_bau_runtime_ux_performance_hotfix.py
# Older regression files intentionally hard-code their cache key. Align them only
# after the runtime layer has selected the final assets that browsers must load.
python3 scripts/ab_bau_runtime_cache_contract_compat.py
# Final operational polish: resolve owner/office users to an auditable Employee
# before starting time and replace the native multi-select with a clear team picker.
python3 scripts/ab_bau_time_employee_team_picker.py
# Finalize owner-review UI and force browsers to fetch the replaced logo/new CSS.
python3 scripts/ab_bau_owner_review_cache_bust.py
# Final Room Planner runtime rule: every wall stays nearly transparent in every
# camera mode, after all older overlays and generated assets have finished.
python3 scripts/room_planner_wall_transparency_hotfix.py
# Premium Room Planner visuals run last so generated/legacy object meshes cannot
# overwrite the rounded sanitary geometry, physical materials or soft lighting.
python3 scripts/room_planner_visual_upgrade.py
# Persist and visibly render KI renovation finishes after every older Room Planner
# overlay so tile formats/heights and Q3-painted zones survive save/reload.
python3 scripts/room_planner_surface_visuals.py
# Owner pricing/commercial workflow must be an explicit production assembly step.
# Do not rely only on the nested branding-cleanup hook to activate Preislisten UI/routes.
python3 scripts/run_owner_pricing_commercial_ai_safety.py
# Final brand sweep runs after every legacy/room/owner overlay so login copy, AI prompts
# and any remaining visible old product name cannot be reintroduced downstream.
python3 scripts/ab_bau_branding_cleanup.py
# Shared scope engine must be the final runtime patch: natural German instructions,
# semantic-safe catalog selection and the Termin KI all use one deterministic flow.
python3 scripts/ab_bau_scope_engine_completion.py
# Catalog matching must run after the shared scope engine because it replaces the
# assembled runtime catalog service with the hardened authoritative matcher.
python3 scripts/ab_bau_catalog_context_hardening.py
# Keep legacy regression contracts and browser cache keys aligned with the final
# shared scope engine after every generated/owner overlay has finished.
python3 scripts/ab_bau_scope_engine_ci_alignment.py
# Voice assets have their own cache lifecycle. Verify they remain cache-busted
# without coupling their regression test to the unrelated global KI asset version.
python3 scripts/ab_bau_voice_cache_contract_fix.py
# Final cross-app UX/business-document layer: 10-minute time grid, legal business
# identity on PDFs and three-source live pricing directly in position fields.
python3 scripts/global_time_pdf_catalog_upgrade.py

echo "A+Bau source tree assembled with editable owner Einsatzprüfung, replaced logo, stable Zeiterfassung and current operational UX."
