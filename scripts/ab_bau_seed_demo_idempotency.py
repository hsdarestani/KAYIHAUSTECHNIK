from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "erp" / "management" / "commands" / "seed_demo_data.py"
MARKER = "A_BAU_IDEMPOTENT_EMPLOYEE_USER_SEED"

if not TARGET.exists():
    raise RuntimeError(f"Seed command missing: {TARGET.relative_to(ROOT)}")

text = TARGET.read_text(encoding="utf-8")
if MARKER not in text:
    pattern = re.compile(
        r'(?P<indent>^[ \t]*)employees\[0\]\.user\s*=\s*user\s*\n'
        r'(?P=indent)employees\[0\]\.save\(update_fields=\[\s*["\']user["\']\s*,\s*["\']updated_at["\']\s*\]\)',
        re.MULTILINE,
    )
    match = pattern.search(text)
    if not match:
        raise RuntimeError("Could not locate employee/user seed assignment for idempotency patch")
    indent = match.group("indent")
    replacement = (
        f'{indent}# {MARKER}: keep deployments idempotent when this user is already linked.\n'
        f'{indent}existing_employee_for_user = type(employees[0]).objects.filter(user=user).exclude(pk=employees[0].pk).first()\n'
        f'{indent}if existing_employee_for_user is None:\n'
        f'{indent}    employees[0].user = user\n'
        f'{indent}    employees[0].save(update_fields=["user", "updated_at"])\n'
    )
    text = text[: match.start()] + replacement + text[match.end() :]
    TARGET.write_text(text, encoding="utf-8")

verify = TARGET.read_text(encoding="utf-8")
if MARKER not in verify or "existing_employee_for_user" not in verify:
    raise RuntimeError("Idempotent employee/user seed guard was not installed")

scope_installer = ROOT / "scripts" / "install_ai_scope_planner.py"
if scope_installer.exists():
    exec(compile(scope_installer.read_text(encoding="utf-8"), str(scope_installer), "exec"), {"__name__": "__main__", "__file__": str(scope_installer)})

catalog_installer = ROOT / "scripts" / "install_ai_scope_authoritative_catalog.py"
if catalog_installer.exists():
    exec(compile(catalog_installer.read_text(encoding="utf-8"), str(catalog_installer), "exec"), {"__name__": "__main__", "__file__": str(catalog_installer)})

owner_workflow = ROOT / "scripts" / "run_owner_pricing_commercial_ai_safety.py"
if owner_workflow.exists():
    exec(compile(owner_workflow.read_text(encoding="utf-8"), str(owner_workflow), "exec"), {"__name__": "__main__", "__file__": str(owner_workflow)})

# Make the assembled model state identical to its generated migration so CI does
# not synthesize a meaningless follow-up AlterModelOptions migration.
normalizer = ROOT / "scripts" / "normalize_owner_commercial_models.py"
if normalizer.exists():
    exec(compile(normalizer.read_text(encoding="utf-8"), str(normalizer), "exec"), {"__name__": "__main__", "__file__": str(normalizer)})

# Last scope rule: explicit dimensions must win over historical 2.5 assumptions.
# This is after all AI and owner layers so no legacy installer can replace it.
painting_fix = ROOT / "scripts" / "fix_owner_workflow_regressions.py"
if painting_fix.exists():
    exec(compile(painting_fix.read_text(encoding="utf-8"), str(painting_fix), "exec"), {"__name__": "__main__", "__file__": str(painting_fix)})

print("A+Bau production seed and final owner/commercial/AI safeguards installed.")
