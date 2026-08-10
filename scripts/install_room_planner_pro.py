from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "overlays" / "room_planner_pro"


def copy_tree(source: Path, target: Path) -> None:
    if not source.exists():
        raise RuntimeError(f"Missing Room Planner Pro overlay: {source}")
    target.mkdir(parents=True, exist_ok=True)
    for item in source.rglob("*"):
        if item.is_dir():
            continue
        relative = item.relative_to(source)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, destination)


def assemble_asset(name: str, target: Path) -> None:
    parts = sorted((OVERLAY / "assets").glob(name + ".part*"))
    if not parts:
        raise RuntimeError(f"Missing Room Planner Pro asset parts: {name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("".join(part.read_text(encoding="utf-8") for part in parts), encoding="utf-8")


def patch_room_state_canonicalization() -> None:
    path = ROOT / "erp" / "services" / "room_planner_state.py"
    text = path.read_text(encoding="utf-8")
    old = '''        maximum_offset = max(Decimal("0"), wall_length - opening_width)
        offset = min(_decimal(raw.get("offset_m", 0.5), f"openings[{index}].offset_m"), maximum_offset)
'''
    new = '''        maximum_offset = max(Decimal("0.000"), wall_length - opening_width).quantize(Decimal("0.001"))
        offset = min(_decimal(raw.get("offset_m", 0.5), f"openings[{index}].offset_m"), maximum_offset).quantize(Decimal("0.001"))
'''
    if new in text:
        return
    if old not in text:
        raise RuntimeError("Could not canonicalize Room Planner opening offsets")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_rebuild_urls() -> None:
    path = ROOT / "erp" / "rebuild_urls.py"
    text = path.read_text(encoding="utf-8")
    if 'include("erp.room_planner_urls")' in text or "include('erp.room_planner_urls')" in text:
        return
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("from django.urls import "):
            imports = [part.strip() for part in line.split("import", 1)[1].split(",")]
            if "include" not in imports:
                imports.insert(0, "include")
            if "path" not in imports:
                imports.append("path")
            lines[index] = "from django.urls import " + ", ".join(dict.fromkeys(imports))
            break
    else:
        lines.insert(0, "from django.urls import include")
    text = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
    marker = "urlpatterns = ["
    if marker not in text:
        raise RuntimeError("Could not locate urlpatterns in erp/rebuild_urls.py")
    text = text.replace(
        marker,
        marker + '\n    # KAYI Room Planner Pro: project-scoped WebGL room planning and AI scene reconstruction.\n    path("", include("erp.room_planner_urls")),',
        1,
    )
    path.write_text(text, encoding="utf-8")


def patch_production_smoke() -> None:
    path = ROOT / "scripts" / "production_browser_smoke.py"
    text = path.read_text(encoding="utf-8")
    marker = "# KAYI Room Planner Pro browser smoke"
    if marker in text:
        return
    anchor = '            if visible_controls.count() < 4:\n                fail("new project flow has too few controls and appears broken")\n'
    if anchor not in text:
        raise RuntimeError("Could not locate KAYI Next office smoke insertion point")
    block = anchor + '\n\n            # KAYI Room Planner Pro browser smoke: enter a real project through the\n            # production UI and require the WebGL engine to initialize without JS errors.\n            page.goto(urljoin(base_url, "projects/"), wait_until="domcontentloaded", timeout=30_000)\n            project_link = page.locator(\'a.nx-btn-ghost[href^="/projects/"]\').first\n            if project_link.count():\n                project_href = project_link.get_attribute("href")\n                page.goto(urljoin(base_url, (project_href or "").lstrip("/")), wait_until="domcontentloaded", timeout=30_000)\n                planner_link = page.locator(\'a[href*="/room-planner/"]\').first\n                if planner_link.count() != 1:\n                    fail("project workspace is missing the Raum & 3D action")\n                planner_href = planner_link.get_attribute("href")\n                response = page.goto(urljoin(base_url, (planner_href or "").lstrip("/")), wait_until="domcontentloaded", timeout=30_000)\n                if response is None or response.status >= 500:\n                    fail(f"Room Planner Pro returned {response.status if response else \'no response\'}")\n                if "Raumplanung 3D" not in page.content():\n                    fail("Room Planner Pro is missing its primary heading")\n                page.locator(\'[data-rp-canvas][data-ready="1"]\').wait_for(state="attached", timeout=20_000)\n                if page.locator(\'[data-rp-engine-error]:visible\').count():\n                    fail("Room Planner Pro WebGL engine displayed an initialization error")\n                if page.locator(\'[data-rp-add-object]\').count() < 20:\n                    fail("Room Planner Pro object library is incomplete")\n                vision_trigger = page.locator(\'[data-rp-open-vision]\').first\n                if vision_trigger.count() != 1:\n                    fail("Room Planner Pro AI photo action is missing")\n                vision_trigger.click()\n                page.locator(\'[data-rp-vision-dialog][open]\').wait_for(state="attached", timeout=5_000)\n                if page.locator(\'[data-rp-run-vision]\').count() != 1:\n                    fail("Room Planner Pro AI analysis action is missing")\n                page.locator(\'[data-rp-close-vision]\').first.click()\n'
    text = text.replace(anchor, block, 1)
    path.write_text(text, encoding="utf-8")


def guard() -> None:
    required = [
        ROOT / "erp" / "room_planner_urls.py",
        ROOT / "erp" / "room_planner_views.py",
        ROOT / "erp" / "services" / "room_planner_state.py",
        ROOT / "erp" / "services" / "room_vision.py",
        ROOT / "templates" / "rebuild" / "room_planner.html",
        ROOT / "templates" / "rebuild" / "project_detail.html",
        ROOT / "templates" / "rebuild" / "appointment_detail.html",
        ROOT / "static" / "css" / "room-planner.css",
        ROOT / "static" / "js" / "room-planner.js",
        ROOT / "tests" / "test_room_planner_pro.py",
        ROOT / "scripts" / "production_browser_smoke.py",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        raise RuntimeError(f"Room Planner Pro installation incomplete: {missing}")
    urls = (ROOT / "erp" / "rebuild_urls.py").read_text(encoding="utf-8")
    if 'include("erp.room_planner_urls")' not in urls:
        raise RuntimeError("Room Planner Pro URLs were not installed")
    state_service = (ROOT / "erp" / "services" / "room_planner_state.py").read_text(encoding="utf-8")
    if 'maximum_offset = max(Decimal("0.000")' not in state_service:
        raise RuntimeError("Room Planner Pro canonical geometry state was not installed")
    js = (ROOT / "static" / "js" / "room-planner.js").read_text(encoding="utf-8")
    if "KAYI_ROOM_PLANNER_PRO" not in js or "WebGLRenderer" not in js:
        raise RuntimeError("Professional WebGL room engine is missing")
    planner = (ROOT / "templates" / "rebuild" / "room_planner.html").read_text(encoding="utf-8")
    if "three@0.170.0" not in planner or "vollständigen Raum" not in planner:
        raise RuntimeError("Room Planner Pro template contract is incomplete")
    project = (ROOT / "templates" / "rebuild" / "project_detail.html").read_text(encoding="utf-8")
    appointment = (ROOT / "templates" / "rebuild" / "appointment_detail.html").read_text(encoding="utf-8")
    if "next-room-planner" not in project or "next-room-planner" not in appointment:
        raise RuntimeError("Room Planner Pro is not connected to project/field flow")
    smoke = (ROOT / "scripts" / "production_browser_smoke.py").read_text(encoding="utf-8")
    if "KAYI Room Planner Pro browser smoke" not in smoke:
        raise RuntimeError("Room Planner Pro production browser smoke was not installed")


copy_tree(OVERLAY / "erp", ROOT / "erp")
copy_tree(OVERLAY / "templates", ROOT / "templates")
copy_tree(OVERLAY / "tests", ROOT / "tests")
assemble_asset("room-planner.css", ROOT / "static" / "css" / "room-planner.css")
assemble_asset("room-planner.js", ROOT / "static" / "js" / "room-planner.js")
patch_room_state_canonicalization()
patch_rebuild_urls()
patch_production_smoke()
guard()
print("KAYI Room Planner Pro installed and verified.")
