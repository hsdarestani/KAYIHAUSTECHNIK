from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME PHASE 15 CI CLOSEOUT 2026-08-21"
OLD_MIGRATION_REL = "erp/migrations/0012_calendar_event_customer.py"
NEW_MIGRATION_REL = "erp/migrations/0020_calendar_event_customer.py"


def _replace_required(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Phase 15 closeout anchor missing: {label}")
    return text.replace(old, new)


def linearize_migration(module) -> None:
    old_path = ROOT / OLD_MIGRATION_REL
    new_path = ROOT / NEW_MIGRATION_REL

    if new_path.exists():
        migration = new_path.read_text(encoding="utf-8")
    elif old_path.exists():
        migration = old_path.read_text(encoding="utf-8")
    else:
        raise RuntimeError("Phase 15 generated customer migration is missing")

    migration = _replace_required(
        migration,
        '("erp", "0011_project_approval_flow")',
        '("erp", "0019_tooltime_online_acceptance")',
        "migration dependency",
    )
    module.write(NEW_MIGRATION_REL, migration)
    compile(migration, str(new_path), "exec")

    if old_path.exists() and old_path != new_path:
        old_path.unlink()


def patch_contract(module) -> None:
    rel = "tests/test_tooltime_phase15_appointment_customer_contract.py"
    text = module.read(rel)
    text = _replace_required(
        text,
        'erp/migrations/0012_calendar_event_customer.py',
        'erp/migrations/0020_calendar_event_customer.py',
        "contract migration path",
    )
    text = _replace_required(
        text,
        '("erp", "0011_project_approval_flow")',
        '("erp", "0019_tooltime_online_acceptance")',
        "contract dependency",
    )
    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def guard(module) -> None:
    old_path = ROOT / OLD_MIGRATION_REL
    new_path = ROOT / NEW_MIGRATION_REL
    if old_path.exists():
        raise RuntimeError("Phase 15 stale 0012 migration still exists")
    if not new_path.exists():
        raise RuntimeError("Phase 15 linear 0020 migration is missing")
    migration = new_path.read_text(encoding="utf-8")
    for marker in (
        '("erp", "0019_tooltime_online_acceptance")',
        'name="customer"',
        'to="erp.customer"',
    ):
        if marker not in migration:
            raise RuntimeError(f"Phase 15 linear migration marker missing: {marker}")
    contract = module.read("tests/test_tooltime_phase15_appointment_customer_contract.py")
    if "0020_calendar_event_customer.py" not in contract or "0019_tooltime_online_acceptance" not in contract:
        raise RuntimeError("Phase 15 migration contract is not synchronized")


def run(module) -> None:
    linearize_migration(module)
    patch_contract(module)
    guard(module)
    print(f"{MARKER}: customer migration linearized as 0020 after 0019; stale 0012 branch removed before migration validation.")
