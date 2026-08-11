from __future__ import annotations

import runpy
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "overlays" / "tooltime_rebuild"


def copy_tree(source: Path, target: Path) -> None:
    if not source.exists():
        raise RuntimeError(f"Missing rebuild overlay: {source}")
    target.mkdir(parents=True, exist_ok=True)
    for item in source.rglob("*"):
        if item.is_dir():
            continue
        relative = item.relative_to(source)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, destination)


def patch_urls() -> None:
    path = ROOT / "erp" / "urls.py"
    original = path.read_text(encoding="utf-8")
    text = original
    if "include(\"erp.rebuild_urls\")" in text or "include('erp.rebuild_urls')" in text:
        return
    if "from django.urls import" in text:
        lines = text.splitlines()
        for index, line in enumerate(lines):
            if line.startswith("from django.urls import "):
                names = [part.strip() for part in line.split("import", 1)[1].split(",")]
                if "include" not in names:
                    names.append("include")
                lines[index] = "from django.urls import " + ", ".join(names)
                text = "\n".join(lines) + ("\n" if original.endswith("\n") else "")
                break
    else:
        text = "from django.urls import include\n" + text

    marker = "urlpatterns = ["
    if marker not in text:
        raise RuntimeError("Could not locate urlpatterns in erp/urls.py")
    text = text.replace(
        marker,
        marker + "\n    # KAYI Next: ToolTime-parity flow takes precedence; legacy URLs remain as fallback.\n    path(\"\", include(\"erp.rebuild_urls\")),",
        1,
    )
    path.write_text(text, encoding="utf-8")


def guard() -> None:
    required = [
        ROOT / "erp" / "rebuild_views.py",
        ROOT / "erp" / "rebuild_urls.py",
        ROOT / "erp" / "rebuild_ops.py",
        ROOT / "erp" / "rebuild_projects.py",
        ROOT / "erp" / "rebuild_migration.py",
        ROOT / "templates" / "rebuild" / "base.html",
        ROOT / "templates" / "rebuild" / "appointment_detail.html",
        ROOT / "templates" / "rebuild" / "field_home.html",
        ROOT / "templates" / "rebuild" / "document_editor.html",
        ROOT / "templates" / "rebuild" / "tasks.html",
        ROOT / "templates" / "rebuild" / "expenses.html",
        ROOT / "templates" / "rebuild" / "employees.html",
        ROOT / "templates" / "rebuild" / "migration.html",
        ROOT / "static" / "css" / "kayi-next.css",
        ROOT / "static" / "css" / "kayi-next-field.css",
        ROOT / "static" / "js" / "kayi-next.js",
        ROOT / "scripts" / "production_browser_smoke.py",
        ROOT / "scripts" / "next_test_contract.py",
        ROOT / "tests" / "test_tooltime_rebuild.py",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        raise RuntimeError(f"KAYI Next installation incomplete: {missing}")
    urls = (ROOT / "erp" / "urls.py").read_text(encoding="utf-8")
    if "include(\"erp.rebuild_urls\")" not in urls:
        raise RuntimeError("KAYI Next URL overlay was not installed")
    smoke = (ROOT / "scripts" / "production_browser_smoke.py").read_text(encoding="utf-8")
    if "KAYI Next browser smoke" not in smoke:
        raise RuntimeError("Legacy production browser smoke was not replaced")
    tests = (ROOT / "tests" / "test_tooltime_rebuild.py").read_text(encoding="utf-8")
    if "legacy_nine_step_wizard_is_not_primary" not in tests:
        raise RuntimeError("KAYI Next regression contract is missing")


copy_tree(OVERLAY / "erp", ROOT / "erp")
copy_tree(OVERLAY / "templates", ROOT / "templates")
copy_tree(OVERLAY / "static", ROOT / "static")
copy_tree(OVERLAY / "tests", ROOT / "tests")
copy_tree(OVERLAY / "scripts", ROOT / "scripts")
patch_urls()
runpy.run_path(str(ROOT / "scripts" / "next_test_contract.py"), run_name="__main__")
guard()
# Specialist product layers are installed after KAYI Next so their project/field
# integrations survive every deterministic source assembly and production deploy.
runpy.run_path(str(ROOT / "scripts" / "install_room_planner_pro.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "install_field_authorization.py"), run_name="__main__")
# Final quality layers run after every specialist overlay so no old template can
# reintroduce English UI or the obsolete single-FileList photo flow.
runpy.run_path(str(ROOT / "scripts" / "install_german_ui_quality.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "patch_german_browser_smoke.py"), run_name="__main__")
# Store compliance is last: public privacy/support/deletion and AI consent must
# survive every product/UI patch that ran above.
runpy.run_path(str(ROOT / "scripts" / "install_store_readiness.py"), run_name="__main__")
# Release lint is intentionally fixed in source instead of being baselined or
# suppressed, so Google Play validation still catches real scanner errors.
runpy.run_path(str(ROOT / "scripts" / "patch_android_release_lint.py"), run_name="__main__")
# Pin current ARCore and make it an optional enhancement: KAYI itself remains
# installable on devices without native AR support, while the scanner performs
# the required runtime availability/install handling when launched.
runpy.run_path(str(ROOT / "scripts" / "patch_arcore_release.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "patch_arcore_optional.py"), run_name="__main__")
# Legacy test cases must opt in exactly as a real user would; production guards
# remain mandatory and are never bypassed for tests.
runpy.run_path(str(ROOT / "scripts" / "patch_store_test_contract.py"), run_name="__main__")
# The deployment smoke itself must verify the same public pages Store reviewers
# and Google account-deletion crawlers will use after rollout.
runpy.run_path(str(ROOT / "scripts" / "patch_store_browser_smoke.py"), run_name="__main__")
# Last-mile UX contract: no specialist or store overlay is allowed to reintroduce
# giant checkboxes, English form labels, dead quote-position controls or missing
# project document download/navigation affordances.
runpy.run_path(str(ROOT / "scripts" / "ui_regression_hardening.py"), run_name="__main__")
# Fix the original +Position binding at its source. The original JS searched for
# the button inside the table even though the button is in the table card header.
runpy.run_path(str(ROOT / "scripts" / "document_position_binding_fix.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "project_row_navigation_hardening.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "catalog_interaction_hardening.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "catalog_browser_smoke_patch.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "finalize_ui_regression_hardening.py"), run_name="__main__")
# Final requested UX polish runs after every prior layer: progressive customer
# creation, readable 3D typography, fresh CSRF state and a real in-planner KI
# assistant must never be overwritten by an older template/asset.
runpy.run_path(str(ROOT / "scripts" / "install_customer_3d_polish.py"), run_name="__main__")
# Because the final 3D layer adds a new OpenAI-backed endpoint after the general
# store-readiness patch, enforce the same explicit third-party KI consent here.
runpy.run_path(str(ROOT / "scripts" / "patch_customer_3d_ai_consent.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "install_customer_3d_tests.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "customer_3d_browser_smoke_patch.py"), run_name="__main__")
# Normalize the one field tag that older German/runtime patches legitimately
# rewrite before the last handoff layer. This keeps final anchors deterministic.
runpy.run_path(str(ROOT / "scripts" / "normalize_field_handoff_anchor.py"), run_name="__main__")
# Global assistant and customer handoff are intentionally the last product layer:
# profile controls, KI omnibox, real field recording, signature and generated PDF
# must survive every previous UI, privacy and room-planner patch.
runpy.run_path(str(ROOT / "scripts" / "install_global_ai_field_handoff.py"), run_name="__main__")
# The assistant-control/search hardening is deliberately after the global KI overlay:
# typed date/time/checkbox updates and real-record search must be the final behavior.
runpy.run_path(str(ROOT / "scripts" / "run_ai_controls_search_checkbox_fix.py"), run_name="__main__")
# Stateful entity memory is the final KI behavior: short follow-ups such as
# "client" or "project" must resolve against the immediately preceding real search.
runpy.run_path(str(ROOT / "scripts" / "fix_ai_stateful_entity_chat.py"), run_name="__main__")
# Readability is the final visual contract. It deliberately runs after all product
# overlays so no earlier compact styles can shrink labels, helpers or catalog text.
runpy.run_path(str(ROOT / "scripts" / "typography_readability_pass.py"), run_name="__main__")
# Read-only diagnostic of legacy routes still present behind KAYI Next. This does
# not reapply old fixes; it reports what survived in the actual assembled source.
runpy.run_path(str(ROOT / "scripts" / "audit_legacy_regressions.py"), run_name="__main__")
print("KAYI Next installed and verified with global KI, readable typography, profile menu, field voice/signature/PDF handoff, specialist flows, German UI and store readiness.")