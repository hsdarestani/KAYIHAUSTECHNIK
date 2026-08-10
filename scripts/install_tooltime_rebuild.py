from __future__ import annotations

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


copy_tree(OVERLAY / "erp", ROOT / "erp")
copy_tree(OVERLAY / "templates", ROOT / "templates")
copy_tree(OVERLAY / "static", ROOT / "static")
copy_tree(OVERLAY / "tests", ROOT / "tests")
copy_tree(OVERLAY / "scripts", ROOT / "scripts")
patch_urls()
guard()
print("KAYI Next ToolTime-parity rebuild installed and verified.")
