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
    # Older seed code blindly linked the first demo employee to the bootstrap user.
    # On a real production database that user can already belong to another Employee,
    # and Employee.user is unique, so every deployment after that state crashed.
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

# This script is intentionally invoked by the final branding stage, after all
# product/Room Planner overlays. Run the trade-scope planner here so no earlier
# assistant overlay can overwrite its deterministic rules or UI integration.
scope_installer = ROOT / "scripts" / "install_ai_scope_planner.py"
if scope_installer.exists():
    exec(
        compile(scope_installer.read_text(encoding="utf-8"), str(scope_installer), "exec"),
        {"__name__": "__main__", "__file__": str(scope_installer)},
    )

print("A+Bau production seed is idempotent for already-linked Employee users.")
