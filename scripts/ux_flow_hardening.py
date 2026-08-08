from __future__ import annotations

import base64
import gzip
import hashlib
import re
import subprocess
from pathlib import Path


PATCH_DIR = Path("scripts/ux_flow_hardening_v2")
EXPECTED_GZIP_SHA256 = "1d3c07772465d4d2af971b303a044b7b423336b960d63d6f647745204ee89729"
EXPECTED_PATCH_SHA256 = "efdb2c19ddce841f7191e34caf5486fd5d552db88fce300bbb77af4955c7c2e4"
EXPECTED_PARTS = {
    "part01": (6000, "d00876331dcf7abecda2beeec2b9c378e714ed410f2c32dd47a55759a6799588"),
    "part02": (6000, "c3d3f00d08e10eaaf609af6a294ceb56cb18757e6462dd694925a00b262f3e95"),
    "part03": (6000, "3f0e219797965e63b286c3524f725f8660af8a76dca7788b5ad7dd33863fcec0"),
    "part04": (6000, "77090dfffbe6442b2033baaac8f80fd68aec5031cb9053975ae4e6e86663534c"),
    "part05": (4152, "990eeef82089c406445b3b3befa36dd7653cae20076de35fc8f6a01d801ac55f"),
}
PATCH_PATH = Path("/tmp/kayi-ux-flow-hardening.patch")


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _already_applied() -> bool:
    return (
        "3-Schritte-Projektassistent" in _read("templates/erp/project_wizard.html")
        and 'name="site-report-edit"' in _read("erp/urls.py")
        and 'order_by("-paid_at", "-pk")' in _read("erp/views.py")
        and "20260808-2100" in _read("templates/erp/base.html")
    )


def _apply_patch() -> None:
    parts = sorted(PATCH_DIR.glob("part*"))
    if [part.name for part in parts] != list(EXPECTED_PARTS):
        raise RuntimeError(f"Unexpected UX hardening part set: {[part.name for part in parts]!r}")

    encoded_parts: list[str] = []
    for part in parts:
        text = part.read_text(encoding="utf-8").strip()
        expected_length, expected_sha = EXPECTED_PARTS[part.name]
        actual_sha = hashlib.sha256(text.encode()).hexdigest()
        if len(text) != expected_length or actual_sha != expected_sha:
            raise RuntimeError(
                f"UX hardening {part.name} integrity failed: length={len(text)} sha={actual_sha}"
            )
        encoded_parts.append(text)

    payload = base64.b64decode("".join(encoded_parts), validate=True)
    actual = hashlib.sha256(payload).hexdigest()
    if actual != EXPECTED_GZIP_SHA256:
        raise RuntimeError(
            f"UX-flow hardening gzip integrity failed: expected {EXPECTED_GZIP_SHA256}, got {actual}"
        )
    patch_bytes = gzip.decompress(payload)
    patch_sha = hashlib.sha256(patch_bytes).hexdigest()
    if patch_sha != EXPECTED_PATCH_SHA256:
        raise RuntimeError(
            f"UX-flow hardening patch integrity failed: expected {EXPECTED_PATCH_SHA256}, got {patch_sha}"
        )
    PATCH_PATH.write_bytes(patch_bytes)
    subprocess.run(
        ["git", "apply", "--whitespace=nowarn", str(PATCH_PATH)],
        check=True,
    )


def _guard() -> None:
    wizard = _read("templates/erp/project_wizard.html")
    steps = re.findall(
        r'<section class="([^"]*\bwizard-step\b[^"]*)" data-step="([1-3])">',
        wizard,
    )
    if len(steps) != 3 or [number for classes, number in steps if "active" in classes.split()] != ["1"]:
        raise RuntimeError(f"Unexpected simplified wizard structure: {steps!r}")
    if "9-Schritte-Projektassistent" in wizard:
        raise RuntimeError("Legacy nine-step project wizard is still rendered")

    required_markers = {
        "erp/views.py": [
            '.order_by("-paid_at", "-pk")',
            'order_pdf = request.FILES.get("bando_order_pdf")',
            'preferred_price_source(org, Project.JobType.INSURANCE)',
            '"draft_site_report": draft_report',
        ],
        "erp/workflow_views.py": [
            "def site_report_edit(request, pk):",
            "site_reports__signed_at__isnull=False",
            "pending_project.draft_report",
        ],
        "erp/urls.py": ['name="site-report-edit"'],
        "templates/erp/project_detail.html": [
            "Nächste Schritte",
            "can_view_prices and project.job_type == 'insurance'",
            "site-report-edit",
        ],
        "templates/erp/site_report_list.html": [
            "ohne abgeschlossenen Leistungsnachweis",
            "Weiterbearbeiten",
        ],
        "static/js/app.js": [
            "const lastStep = Math.max(1, steps.length);",
            "/sw.js?v=20260808-2100",
        ],
        "static/js/sw.js": [
            'const CACHE = "kayi-shell-v19-20260808";',
            "20260808-2100",
        ],
        "templates/erp/base.html": ["20260808-2100"],
        "templates/registration/login.html": ["20260808-2100"],
        ".env.example": [
            "SECURE_SSL_REDIRECT=1",
            "COOKIE_SECURE=1",
            "OPENAI_MODEL=gpt-4.1-mini",
            "OPENAI_FALLBACK_MODEL=gpt-4.1-mini",
        ],
        "Dockerfile": ["RUN python manage.py makemigrations --check --dry-run"],
        "tests/test_workflow_release.py": [
            "test_bando_draft_stays_pending_and_can_be_continued",
            "3-Schritte-Projektassistent",
        ],
        "tests/test_room_model_editor.py": [
            "test_project_wizard_keeps_material_and_3d_tools_outside_core_creation_flow",
            "3D-Modell optional",
            "data-room-model-editor",
        ],
    }
    for filename, markers in required_markers.items():
        text = _read(filename)
        for marker in markers:
            if marker not in text:
                raise RuntimeError(f"UX-flow hardening guard failed for {filename}: {marker!r}")

    if "RUN python manage.py makemigrations erp --noinput" in _read("Dockerfile"):
        raise RuntimeError("Docker build still generates migrations at runtime")


if not _already_applied():
    _apply_patch()
_guard()
print("KAYI UX-flow hardening applied and verified.")
