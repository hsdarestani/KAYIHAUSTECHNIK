from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "design/native/full-app"
TARGET = ROOT / "native/www"

for name in ("index.html", "app.js", "styles.css"):
    source = SOURCE / name
    if not source.exists():
        raise RuntimeError(f"Native full-app source missing: {source.relative_to(ROOT)}")
    TARGET.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, TARGET / name)

prepare = ROOT / "scripts/prepare_native_store_shell.py"
text = prepare.read_text(encoding="utf-8")
old = '''    replace_required(INDEX, "<title>KAYI Haustechnik</title>", "<title>A+Bau</title>")
    replace_required(INDEX, '<div class="logo">K</div><h1>KAYI Haustechnik</h1><p>Natives Baustellen-Aufmaß</p>', '<div class="logo">A+</div><h1>A+Bau</h1><p>Baustellenmanagement wird geladen …</p>')
    replace_required(INDEX, 'src="app.js"', 'src="app.bundle.js"')'''
new = '''    replace_required(INDEX, "<title>KAYI Haustechnik</title>", "<title>A+Bau</title>") if "<title>KAYI Haustechnik</title>" in INDEX.read_text(encoding="utf-8") else None
    replace_required(INDEX, 'src="app.js"', 'src="app.bundle.js"') if 'src="app.js"' in INDEX.read_text(encoding="utf-8") else None'''
if old in text:
    text = text.replace(old, new, 1)
elif new not in text:
    raise RuntimeError("Native store preparation anchor missing")
prepare.write_text(text, encoding="utf-8")

test = ROOT / "tests/test_native_full_app_phase1.py"
test.write_text('''from pathlib import Path\nfrom django.test import SimpleTestCase\n\nROOT = Path(__file__).resolve().parents[1]\n\nclass NativeFullAppPhase1Tests(SimpleTestCase):\n    def test_native_app_is_role_aware_operations_shell(self):\n        app = (ROOT / "native/www/app.js").read_text(encoding="utf-8")\n        for marker in ("OFFICE_ROLES", "isOffice", "Büro & Administration", "Mitarbeiter", "renderCustomers", "renderCommercial", "renderTime", "renderScanner"):\n            self.assertIn(marker, app)\n        self.assertNotIn("function renderProjects(){const caps=", app)\n\n    def test_scanner_is_one_module_not_the_whole_app(self):\n        app = (ROOT / "native/www/app.js").read_text(encoding="utf-8")\n        self.assertIn("Der Scanner ist ein Werkzeug innerhalb des vollständigen A+Bau-Workflows.", app)\n        self.assertIn("data-route=\\\"scanner\\\"", app)\n        for endpoint in ("/api/projects/", "/api/events/", "/api/tasks/", "/api/customers/", "/api/quotes/", "/api/invoices/"):\n            self.assertIn(endpoint, app)\n\n    def test_mobile_shell_has_accessible_feedback_and_safe_areas(self):\n        html = (ROOT / "native/www/index.html").read_text(encoding="utf-8")\n        css = (ROOT / "native/www/styles.css").read_text(encoding="utf-8")\n        app = (ROOT / "native/www/app.js").read_text(encoding="utf-8")\n        self.assertIn('aria-live="polite"', html)\n        self.assertIn("safe-area-inset-bottom", css)\n        self.assertIn("role", app)\n        self.assertIn("toast-error", css)\n''', encoding="utf-8")

print("Installed Native Full App phase 1: role-aware shell, dashboards, navigation and scanner module.")
