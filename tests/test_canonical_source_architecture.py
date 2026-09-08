from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class CanonicalSourceArchitectureTests(SimpleTestCase):
    def test_final_application_source_is_direct(self):
        for rel in (
            "manage.py",
            "config/settings.py",
            "erp/models.py",
            "templates/rebuild/base.html",
            "static/js/app.js",
            "native/package.json",
            "compose.yaml",
        ):
            self.assertTrue((ROOT / rel).exists(), rel)

    def test_routine_ci_and_deploy_do_not_run_legacy_assembly(self):
        for rel in (
            ".github/workflows/ci.yml",
            ".github/workflows/deploy.yml",
            ".github/workflows/native-scanner-ci.yml",
            "deploy/server-deploy.sh",
            "deploy/server-deploy-ab-bau.sh",
        ):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertNotIn("bash scripts/unpack-source.sh", text, rel)

    def test_legacy_rebuild_remains_available(self):
        rebuild = (ROOT / "scripts/rebuild-legacy-source.sh").read_text(encoding="utf-8")
        self.assertIn("bash scripts/unpack-source.sh", rebuild)
        workflow = (ROOT / ".github/workflows/legacy-source-verify.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("schedule:", workflow)
