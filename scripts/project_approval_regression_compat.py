from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Regression compatibility target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    (ROOT / rel).write_text(text, encoding="utf-8")


def patch_field_authorization_test() -> None:
    """Retire the one legacy regression that asserts direct-priced Schnellauftrag.

    The replacement flow has its own database E2E test covering the same existing-
    customer path plus the new review, office pricing and customer-signature gates.
    Keeping the old assertion active would test a behavior that must no longer exist.
    """
    rel = "tests/test_field_authorization.py"
    text = read(rel)
    method = "    def test_quick_job_can_reuse_existing_customer(self):\n"
    skip = (
        "        self.skipTest(\"Replaced by TechnicianProjectApprovalDatabaseTests: "
        "price-free intake -> office approval -> customer signature.\")\n"
    )
    if skip not in text:
        if method not in text:
            raise RuntimeError("Legacy quick-job regression method changed")
        text = text.replace(method, method + skip, 1)
        write(rel, text)


def patch_tooltime_test() -> None:
    rel = "tests/test_tooltime_rebuild.py"
    text = read(rel)
    old = 'self.assertIn("Schnellauftrag", field_home)'
    new = 'self.assertIn("Projekt aufnehmen", field_home)'
    if new not in text:
        if old not in text:
            raise RuntimeError("ToolTime field-home Schnellauftrag assertion changed")
        write(rel, text.replace(old, new, 1))


def guard() -> None:
    field = read("tests/test_field_authorization.py")
    tooltime = read("tests/test_tooltime_rebuild.py")
    replacement = read("tests/test_technician_project_approval_flow.py")
    if "Replaced by TechnicianProjectApprovalDatabaseTests" not in field:
        raise RuntimeError("Obsolete direct-priced quick-job regression is still active")
    if 'self.assertIn("Projekt aufnehmen", field_home)' not in tooltime:
        raise RuntimeError("ToolTime test still expects obsolete Schnellauftrag copy")
    for needle in (
        "test_full_technician_owner_customer_flow",
        'self.assertEqual(project.status, "review")',
        'self.assertEqual(flow.status, "submitted")',
        'self.assertEqual(project.status, "in_progress")',
    ):
        if needle not in replacement:
            raise RuntimeError(f"Replacement approval-flow regression missing: {needle}")


patch_field_authorization_test()
patch_tooltime_test()
guard()
print("A+Bau regression contracts aligned: obsolete direct-priced Schnellauftrag test retired; full approval-flow E2E remains authoritative.")
