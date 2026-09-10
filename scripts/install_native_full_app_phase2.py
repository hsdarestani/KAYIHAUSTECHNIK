from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
app = (ROOT / "native/www/app.js").read_text(encoding="utf-8")
required = (
    "renderCustomerDetail", "renderCustomerForm", "saveCustomer",
    "renderProjectDetail", "renderProjectForm", "saveProject",
    "data-new-customer", "data-new-project", "Kunde wurde angelegt.",
    "Projekt wurde angelegt.",
)
for marker in required:
    if marker not in app:
        raise RuntimeError(f"Native Full App phase 2 marker missing: {marker}")

(ROOT / "tests/test_native_full_app_phase2.py").write_text('''from pathlib import Path\nfrom django.test import SimpleTestCase\n\nROOT = Path(__file__).resolve().parents[1]\n\nclass NativeFullAppPhase2Tests(SimpleTestCase):\n    def test_customer_crud_is_office_only_and_has_feedback(self):\n        app = (ROOT / "native/www/app.js").read_text(encoding="utf-8")\n        self.assertIn("function renderCustomerForm(){if(!isOffice())return forbidden()", app)\n        self.assertIn("async function saveCustomer", app)\n        self.assertIn("/api/customers/", app)\n        self.assertIn("Kunde wurde angelegt.", app)\n        self.assertIn("Kundendaten wurden gespeichert.", app)\n\n    def test_project_crud_is_office_only_and_scanner_stays_attached(self):\n        app = (ROOT / "native/www/app.js").read_text(encoding="utf-8")\n        self.assertIn("function renderProjectForm(){if(!isOffice())return forbidden()", app)\n        self.assertIn("async function saveProject", app)\n        self.assertIn("/api/projects/", app)\n        self.assertIn("data-scan-project", app)\n        self.assertIn("Projekt wurde angelegt.", app)\n\n    def test_forms_validate_and_send_json_to_scoped_api(self):\n        app = (ROOT / "native/www/app.js").read_text(encoding="utf-8")\n        for marker in ("formPayload", "Content-Type':'application/json", "method:id?'PATCH':'POST'", "Bitte Firma oder einen Namen eintragen."):\n            self.assertIn(marker, app)\n        css = (ROOT / "native/www/styles.css").read_text(encoding="utf-8")\n        for marker in ("Native Full App phase 2", ".entity-form", ".detail-card", "@media(max-width:520px)"):\n            self.assertIn(marker, css)\n''', encoding="utf-8")

print("Installed Native Full App phase 2: customer and project CRUD contracts.")
