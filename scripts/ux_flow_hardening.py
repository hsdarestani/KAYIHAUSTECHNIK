from __future__ import annotations

import base64
import gzip
import hashlib
import re
import subprocess
from pathlib import Path


PATCH_DIR = Path("scripts/ux_flow_hardening_v3")
EXPECTED_GZIP_SHA256 = "1d3c07772465d4d2af971b303a044b7b423336b960d63d6f647745204ee89729"
EXPECTED_PATCH_SHA256 = "efdb2c19ddce841f7191e34caf5486fd5d552db88fce300bbb77af4955c7c2e4"
EXPECTED_PARTS = {
    "part01": (2000, "ae9236962ee65649420cb08dce3de829be2b3cd355016bd312487eff9bd60f19"),
    "part02": (2000, "787e283b25ceb900dc9e051909bd707d3b5a597a58c50694c359eb89c1648e73"),
    "part03": (2000, "7e60d7a427ab2477faa89a9da222a297474fb14a200067350b5856a3d95a56dc"),
    "part04": (2000, "c9a31125d759d56c674d304de80dd5caf8693939fd271b6e317bac4a2ce5c77c"),
    "part05": (2000, "65a0fb3d793d261aeab907fd42d32b915fb7fb394d513de47dd3767449c30d69"),
    "part06": (2000, "ecff0a2a476c0bacacccf65c9c68a4af70890e5091763efe075360cc3ac7572b"),
    "part07": (2000, "c9e9e8b8973f3224618f4388fafaff9e9d739edaf570aed6d6fdfce706984aee"),
    "part08": (2000, "1aa42b72bb8adf637ec2d40da97f84e06de57b0acc0ea454213ab29ba2459112"),
    "part09": (2000, "e7f4feece652d2d375c0b8d6598211917eaaf914faa2b8ead9f150a4bbb481df"),
    "part10": (2000, "d3e7ed3f6002e5d696b017b33a3f4b3bb2eb82b41fc468dba4db72a9a309ad07"),
    "part11": (2000, "3790650f7e6bf2220a7f7bad7bf787bcb858760202fdda86a14fbdb277b56e78"),
    "part12": (2000, "6fe1c0bf91a9bede1db4612687b66332d907ba1391ad03ee40ca78773efcdc50"),
    "part13": (2000, "a9e28d0f2612fb2edc5893e095c1ab5d4c1c0e846fad8f24ca1a70f8c0279d0b"),
    "part14": (2000, "6bc473fdb0fd7879cf2360104e47f4569a868a649fe3ed20d4ad16561e0c9198"),
    "part15": (152, "6bfda5dbeacee1b090fd3dd780f73cfd2d2a3d590735e177e3dc71d3a1221ced"),
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
