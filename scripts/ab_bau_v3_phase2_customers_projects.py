from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "design" / "v3" / "phase2"
CSS_SOURCE = ROOT / "design" / "v3" / "ab-bau-v3-phase2.css"
CSS_TARGET = ROOT / "static" / "css" / "ab-bau-v3-phase2.css"
BASE = ROOT / "templates" / "rebuild" / "base.html"
MARKER = "A+BAU V3 PHASE 2 CUSTOMERS PROJECTS 2026-09-08"
VERSION = "20260908-1"

TEMPLATES = {
    "customers.html": ROOT / "templates" / "rebuild" / "customers.html",
    "customer_detail.html": ROOT / "templates" / "rebuild" / "customer_detail.html",
    "customer_form.html": ROOT / "templates" / "rebuild" / "customer_form.html",
    "projects.html": ROOT / "templates" / "rebuild" / "projects.html",
    "project_detail.html": ROOT / "templates" / "rebuild" / "project_detail.html",
}


def read(path: Path) -> str:
    if not path.exists():
        raise RuntimeError(f"V3 Phase 2 target missing: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def install_templates() -> None:
    for name, target in TEMPLATES.items():
        source = SOURCE_DIR / name
        if not source.exists():
            raise RuntimeError(f"V3 Phase 2 source template missing: {source.relative_to(ROOT)}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def install_assets() -> None:
    if not CSS_SOURCE.exists():
        raise RuntimeError("V3 Phase 2 CSS source missing")
    CSS_TARGET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(CSS_SOURCE, CSS_TARGET)

    base = read(BASE)
    link = f'<link rel="stylesheet" href="/static/css/ab-bau-v3-phase2.css?v={VERSION}">'
    if link not in base:
        anchor = '<link rel="stylesheet" href="/static/css/ab-bau-v3.css?v=20260908-2">'
        if anchor in base:
            base = base.replace(anchor, anchor + "\n  " + link, 1)
        elif "</head>" in base:
            base = base.replace("</head>", f"  {link}\n</head>", 1)
        else:
            raise RuntimeError("V3 Phase 2 could not locate base stylesheet anchor")
        write(BASE, base)


def install_contract_test() -> None:
    test = r'''from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ABauV3Phase2Contract(SimpleTestCase):
    def read(self, rel):
        return (ROOT / rel).read_text(encoding="utf-8")

    def test_customer_directory_is_structural_v3_and_keeps_real_workflows(self):
        page = self.read("templates/rebuild/customers.html")
        for marker in (
            "data-ab-v3-customers",
            "ab-v3-directory-hero",
            "data-customer-modal",
            "data-customer-modal-show",
            "data-customer-row",
            "data-row-menu",
            "Debitorennummer",
            "Routing-ID",
            "Lieferanten-ID",
            "next-project-create",
        ):
            self.assertIn(marker, page)
        self.assertNotIn("Von ToolTime wechseln", page)

    def test_customer_cockpit_keeps_locations_commercial_and_document_context(self):
        page = self.read("templates/rebuild/customer_detail.html")
        for marker in (
            "data-ab-v3-customer-detail",
            "＋ Objekt hinzufügen",
            "Standardmäßig wird die Kundenadresse",
            'name="action" value="add_location"',
            "Umsatz (netto)",
            "Ausgaben (netto)",
            "Offener Rechnungsbetrag",
            "next-project-create",
            "next-expense-create",
            "next-quote-create",
            "next-invoice-create",
        ):
            self.assertIn(marker, page)
        self.assertNotIn("next-appointment-create", page)

    def test_project_directory_keeps_filters_create_and_column_controls(self):
        page = self.read("templates/rebuild/projects.html")
        for marker in (
            "data-ab-v3-projects",
            "data-tooltime-projects-exact",
            "data-project-table",
            "data-project-modal",
            "data-project-create-form",
            "data-column-toggle",
            "data-page-size",
            "next-project-detail",
            "next-appointment-create",
            "next-quote-create",
        ):
            self.assertIn(marker, page)

    def test_project_cockpit_preserves_room_planner_field_and_finance_contracts(self):
        page = self.read("templates/rebuild/project_detail.html")
        for marker in (
            "data-ab-v3-project-detail",
            "data-tooltime-project-detail",
            "next-room-planner",
            "Raum & 3D",
            "Aufmaß",
            "B&O Leistungsnachweis / Regiebericht",
            'data-tab="overview"',
            'data-tab="tasks"',
            'data-tab="documents"',
            'data-tab="finance"',
            'data-tab-panel="finance"',
            'data-row-href',
            'data-action="open-offer"',
            'data-action="open-invoice"',
            "Herunterladen",
        ):
            self.assertIn(marker, page)
        self.assertNotIn("{% url 'configurator' %}?project={{ project.pk }}", page)
        finance_pos = page.find('data-tab-panel="finance"')
        money_pos = page.find("Umsatz (netto)")
        guard_pos = page.rfind("{% if not field_user %}", 0, finance_pos + 1)
        self.assertGreaterEqual(finance_pos, 0)
        self.assertGreaterEqual(money_pos, 0)
        self.assertGreaterEqual(guard_pos, 0)
        self.assertLess(guard_pos, finance_pos)
        self.assertLess(guard_pos, money_pos)

    def test_direct_customer_create_and_phase2_asset_are_live(self):
        form = self.read("templates/rebuild/customer_form.html")
        css = self.read("static/css/ab-bau-v3-phase2.css")
        base = self.read("templates/rebuild/base.html")
        self.assertIn("data-ab-v3-customer-form", form)
        self.assertIn("A+BAU V3 — PHASE 2", css)
        self.assertIn("ab-bau-v3-phase2.css?v=20260908-1", base)
'''
    write(ROOT / "tests" / "test_ab_bau_v3_phase2_contract.py", test)
    compile(test, str(ROOT / "tests" / "test_ab_bau_v3_phase2_contract.py"), "exec")


def guard() -> None:
    base = read(BASE)
    css = read(CSS_TARGET)
    if "ab-bau-v3-phase2.css?v=20260908-1" not in base:
        raise RuntimeError("V3 Phase 2 stylesheet is not loaded after source assembly")
    if "A+BAU V3 — PHASE 2" not in css:
        raise RuntimeError("V3 Phase 2 stylesheet marker missing")

    required = {
        "customers.html": ("data-ab-v3-customers", "data-customer-modal", "data-customer-row"),
        "customer_detail.html": ("data-ab-v3-customer-detail", "＋ Objekt hinzufügen", 'name="action" value="add_location"'),
        "customer_form.html": ("data-ab-v3-customer-form", "Kunde anlegen"),
        "projects.html": ("data-ab-v3-projects", "data-project-modal", "data-project-table"),
        "project_detail.html": ("data-ab-v3-project-detail", "next-room-planner", 'data-tab-panel="finance"'),
    }
    for name, markers in required.items():
        text = read(TEMPLATES[name])
        for marker in markers:
            if marker not in text:
                raise RuntimeError(f"V3 Phase 2 guard missing in {name}: {marker}")
    customer_detail = read(TEMPLATES["customer_detail.html"])
    if "next-appointment-create" in customer_detail:
        raise RuntimeError("V3 Phase 2 customer detail restored the duplicate local appointment action")
    project_detail = read(TEMPLATES["project_detail.html"])
    if "configurator' %}?project={{ project.pk }}" in project_detail:
        raise RuntimeError("V3 Phase 2 project detail regressed to the legacy configurator")


def main() -> None:
    install_templates()
    install_assets()
    install_contract_test()
    guard()
    print(f"{MARKER}: customer and project directories/cockpits structurally rebuilt; server workflows preserved.")


if __name__ == "__main__":
    main()
