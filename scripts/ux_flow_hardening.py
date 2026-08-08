from __future__ import annotations

import base64
import gzip
import hashlib
import re
import subprocess
from pathlib import Path


PATCH_DIR = Path("scripts/ux_flow_hardening_patch")
EXPECTED_GZIP_SHA256 = "2ef39ae8ab0ad494805112e17b27603937034fcae1d580b8470aeef874f9932c"
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
    if not parts:
        raise RuntimeError("UX-flow hardening patch parts are missing")
    payload = base64.b64decode(
        "".join(part.read_text(encoding="utf-8").strip() for part in parts),
        validate=True,
    )
    actual = hashlib.sha256(payload).hexdigest()
    if actual != EXPECTED_GZIP_SHA256:
        raise RuntimeError(
            f"UX-flow hardening patch integrity check failed: expected {EXPECTED_GZIP_SHA256}, got {actual}"
        )
    patch_bytes = gzip.decompress(payload)
    PATCH_PATH.write_bytes(patch_bytes)
    subprocess.run(
        ["git", "apply", "--whitespace=nowarn", str(PATCH_PATH)],
        check=True,
    )


def _update_room_editor_regression() -> None:
    """Keep 3D regression coverage while removing 3D from core project creation."""
    path = Path("tests/test_room_model_editor.py")
    text = path.read_text(encoding="utf-8")
    new_name = "test_project_wizard_keeps_material_and_3d_tools_outside_core_creation_flow"
    if new_name in text:
        return
    old = '''    def test_project_wizard_renders_responsive_material_sources_and_inline_editor(self):
        response = self.client.get(reverse("project-create"))
        self.assertContains(response, 'class="material-source-grid"')
        self.assertContains(response, 'data-inline-room-model="1"')
        self.assertContains(response, 'data-model-ai-apply')
        self.assertContains(response, 'data-model-openings="front"')
        self.assertContains(response, reverse("project-room-model-suggestions"))
        self.assertContains(response, reverse("project-wizard-price-preview"))
'''
    new = '''    def test_project_wizard_keeps_material_and_3d_tools_outside_core_creation_flow(self):
        response = self.client.get(reverse("project-create"))
        self.assertContains(response, "3-Schritte-Projektassistent")
        self.assertNotContains(response, 'class="material-source-grid"')
        self.assertNotContains(response, 'data-inline-room-model="1"')
        self.assertNotContains(response, 'data-model-ai-apply')

        project = self.client.get(reverse("project-detail", args=[self.project.pk]))
        self.assertContains(project, "3D-Modell optional")
        self.assertContains(project, reverse("configurator") + f"?project={self.project.pk}")

        configurator = self.client.get(
            reverse("configurator") + f"?project={self.project.pk}&measurement={self.measurement.pk}"
        )
        self.assertContains(configurator, "data-room-model-editor")
        self.assertContains(configurator, reverse("configurator-model-save"))
        self.assertContains(configurator, reverse("project-room-model-suggestions"))
'''
    if old not in text:
        raise RuntimeError("Could not locate legacy inline 3D wizard regression test")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


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
_update_room_editor_regression()
_guard()
print("KAYI UX-flow hardening applied and verified.")
