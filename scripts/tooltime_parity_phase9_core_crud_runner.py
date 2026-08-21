from __future__ import annotations

import re
import types
from pathlib import Path

import tooltime_parity_phase10_appointments as phase10
import tooltime_parity_phase11_appointment_views as phase11
import tooltime_parity_phase12_appointment_map as phase12
import tooltime_parity_phase13_appointment_detail_edit as phase13
import tooltime_parity_phase14_appointment_detail_polish as phase14
import tooltime_parity_phase15_appointment_customer as phase15
import tooltime_parity_phase16_appointment_recurrence as phase16
import tooltime_phase10_ci_closeout as phase10_closeout
import tooltime_phase12_ci_closeout as phase12_closeout
import tooltime_phase15_ci_closeout as phase15_closeout
import tooltime_phase16_ci_closeout as phase16_closeout
import tooltime_phase9_ci_closeout as ci_closeout
import tooltime_phase9_regression_fix as regression_fix

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "tooltime_parity_phase9_core_crud.py"
MARKER = "A+BAU TOOLTIME PHASE 9 CORE CRUD BROWSER SMOKE"
PHASE10_SMOKE_MARKER = "A+BAU TOOLTIME PHASE 10 APPOINTMENT BROWSER SMOKE"


def load_phase9():
    text = SOURCE.read_text(encoding="utf-8")
    tail = "\npatch_forms_and_views()\ninstall_templates_and_css()\ninstall_tests()\npatch_browser_smoke()\nguard()\n"
    cut = text.rfind(tail)
    if cut < 0:
        raise RuntimeError("Phase 9 executable tail was not found")
    definitions = text[:cut]
    module = types.ModuleType("tooltime_parity_phase9_core_crud_module")
    module.__file__ = str(SOURCE)
    exec(compile(definitions, str(SOURCE), "exec"), module.__dict__)
    return module


def replace_office_check(text: str, path: str, replacement: str) -> str:
    pattern = re.compile(
        rf'^(?P<indent>[ \t]*)\(["\']{re.escape(path)}["\'],.*$',
        re.M,
    )
    text, count = pattern.subn(lambda match: match.group("indent") + replacement, text, count=1)
    if count != 1 and replacement not in text:
        raise RuntimeError(f"Phase 9 office check route missing: {path}")
    return text


def _insert_before_office_outer_except(text: str, block: str, label: str) -> str:
    office_start = text.find("def run_office_surface(")
    field_start = text.find("\ndef run_field_surface(", office_start)
    if office_start < 0 or field_start < 0:
        raise RuntimeError(f"{label} office/field smoke anchors missing")
    office = text[office_start:field_start]
    except_pos = office.rfind("\n        except Exception:")
    if except_pos < 0:
        raise RuntimeError(f"{label} outer office smoke exception anchor missing")
    insert_at = office_start + except_pos + 1
    return text[:insert_at] + block + text[insert_at:]


def robust_patch_browser_smoke(module) -> None:
    rel = "scripts/production_browser_smoke.py"
    text = module.read(rel)

    text = replace_office_check(
        text,
        "/customers/new/",
        '("/customers/new/", ("Neuer Kunde", "Details einblenden", "＋ Erstellen")),',
    )
    text = replace_office_check(
        text,
        "/projects/new/",
        '("/projects/new/", ("Neues Projekt", "Kunde suchen", "Abweichenden Ausführungsort verwenden", "＋ Erstellen")),',
    )
    text = replace_office_check(
        text,
        "/appointments/new/",
        '("/appointments/new/", ("Neuer Termin", "Kunde oder Projekt auswählen", "Arbeitsbericht", "Bilder")),',
    )

    if MARKER not in text:
        block = r'''            # A+BAU TOOLTIME PHASE 9 CORE CRUD BROWSER SMOKE
            page.goto(urljoin(base_url, "projects/new/"), wait_until="domcontentloaded", timeout=30_000)
            html = page.content()
            if "9-Schritte-Projektassistent" in html or "wizard-step" in html or "Aufmaß / 3D" in html or "Kein Wizard" in html:
                fail("legacy/non-ToolTime project creation content is still visible")
            if page.locator('input[name="title"]').count() != 1 or page.locator('select[name="customer"]').count() != 1:
                fail("ToolTime-like project title/customer controls are missing")
            alternate_toggle = page.locator('[data-alt-location-toggle]')
            alternate_panel = page.locator('[data-alt-location]')
            switch_row = page.locator('.tt-switch-row')
            if alternate_toggle.count() != 1 or alternate_panel.count() != 1 or switch_row.count() != 1:
                fail("project creation is missing the alternate-location switch")
            if alternate_panel.is_visible():
                fail("alternate location must be progressively disclosed")
            switch_row.click()
            page.wait_for_timeout(80)
            if not alternate_panel.is_visible() or not alternate_toggle.is_checked():
                fail("alternate-location switch does not reveal the location selector")
            switch_row.click()
            page.wait_for_timeout(80)
            if alternate_panel.is_visible() or alternate_toggle.is_checked():
                fail("alternate-location switch does not restore customer-address default")

            page.goto(urljoin(base_url, "customers/new/"), wait_until="domcontentloaded", timeout=30_000)
            customer_details = page.locator('[data-more-details]')
            location_details = page.locator('[data-location-details]')
            if customer_details.count() != 1 or location_details.count() != 1:
                fail("ToolTime-like customer progressive details are missing")
            if customer_details.get_attribute("open") is not None:
                fail("optional customer details should be collapsed initially")
            customer_details.locator('summary').click()
            page.wait_for_timeout(60)
            customer_number = page.locator('input[name="customer_number"]')
            if customer_number.count() != 1 or not customer_number.is_visible():
                fail("customer creation is missing the customer-number field")
'''
        text = _insert_before_office_outer_except(text, block, "Phase 9")

    if PHASE10_SMOKE_MARKER not in text:
        phase10_block = r'''            # A+BAU TOOLTIME PHASE 10 APPOINTMENT BROWSER SMOKE
            response = page.goto(urljoin(base_url, "appointments/new/"), wait_until="domcontentloaded", timeout=30_000)
            if response is None or response.status >= 500:
                fail(f"Phase 10 appointment create returned {response.status if response else 'no response'}")
            if page.locator('[data-appointment-create]').count() != 1:
                fail("Phase 10 appointment create shell is missing")
            if page.locator('[data-appointment-customer]').count() != 1 or page.locator('[data-appointment-project-select]').count() != 1:
                fail("Phase 10 customer/project selection controls are missing")
            if page.locator('[data-start-date]').count() != 1 or page.locator('[data-start-time]').count() != 1:
                fail("Phase 10 start date/time controls are missing")
            if page.locator('[data-end-date]').count() != 1 or page.locator('[data-end-time]').count() != 1:
                fail("Phase 10 end date/time controls are missing")
            if page.locator('[data-address-card]').count() != 1 or page.locator('[data-team-search]').count() != 1:
                fail("Phase 10 address/team controls are missing")
            phase10_text = page.locator("body").inner_text()
            for expected in ("Kunde oder Projekt auswählen", "Wiederholt sich nicht", "Arbeitsbericht", "Bilder"):
                if expected not in phase10_text:
                    fail(f"Phase 10 appointment create is missing {expected!r}")
'''
        text = _insert_before_office_outer_except(text, phase10_block, "Phase 10")

    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def run() -> None:
    module = load_phase9()
    module.patch_forms_and_views()
    module.install_templates_and_css()
    module.install_tests()
    regression_fix.run(module)
    ci_closeout.run(module)
    phase10.run(module)
    phase10_closeout.run(module)
    phase11.run(module)
    phase12.run(module)
    phase12_closeout.run(module)
    phase13.run(module)
    phase14.run(module)
    phase15.run(module)
    phase15_closeout.run(module)
    phase16.run(module)
    phase16_closeout.run(module)
    robust_patch_browser_smoke(module)
    module.guard()
    print("A+BAU TOOLTIME PHASE 9/10/11/12/13/14/15/16 RUNNER 2026-08-21: core CRUD, appointment creation, calendar/list/map planning, office-only appointment edit, detail polish, native customer-linked appointments and persistent recurrence layered into final assembly with linear migrations.")


if __name__ == "__main__":
    run()
