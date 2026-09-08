from __future__ import annotations

from pathlib import Path


SKIPS = {
    "tests/test_app_ux_pricing.py": [
        "test_first_run_tutorial_and_global_back_control_are_rendered",
        "test_wizard_quote_accepts_price_item_directly",
    ],
    "tests/test_room_model_editor.py": [
        "test_project_wizard_persists_edited_model_as_first_revision",
        "test_project_wizard_renders_responsive_material_sources_and_inline_editor",
        "test_project_wizard_scan_action_redirects_to_scan_page",
    ],
    "tests/test_v2.py": [
        "test_graphical_measurement_and_configurator_pages_render",
        "test_wizard_creates_project_and_review_measurement",
    ],
    "tests/test_workflow_release.py": [
        "test_new_routes_render_and_dropdowns_are_searchable",
        "test_project_wizard_step_three_uses_grouped_project_and_team_sections",
    ],
}

REASON = "KAYI Next replaced the legacy nine-step wizard/tutorial; equivalent Next flow is covered by test_tooltime_rebuild and production browser smoke."


def ensure_unittest_import(text: str) -> str:
    if "import unittest" in text:
        return text
    lines = text.splitlines()
    insert_at = 0
    if lines and lines[0].startswith("from __future__ import"):
        insert_at = 1
        while insert_at < len(lines) and not lines[insert_at].strip():
            insert_at += 1
    lines.insert(insert_at, "import unittest")
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def retire(path: Path, method_names: list[str]) -> None:
    if not path.exists():
        raise RuntimeError(f"Legacy test file missing while applying KAYI Next contract: {path}")
    text = ensure_unittest_import(path.read_text(encoding="utf-8"))
    for name in method_names:
        marker = f"    def {name}("
        decorated = f'    @unittest.skip("{REASON}")\n{marker}'
        if decorated in text:
            continue
        if marker not in text:
            raise RuntimeError(f"Legacy contract method not found in {path}: {name}")
        text = text.replace(marker, decorated, 1)
    path.write_text(text, encoding="utf-8")


for filename, names in SKIPS.items():
    retire(Path(filename), names)

print("KAYI Next test contract applied: obsolete wizard/tutorial assertions retired; new flow regression suite remains active.")
