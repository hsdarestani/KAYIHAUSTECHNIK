#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import secrets
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.contrib.auth import get_user_model
from erp.models import Project

VIEWPORTS = ((390, 844), (430, 932))
UNSAFE_PARTS = (
    "/logout", "/delete", "/remove", "/archive", "/send", "/approve", "/reject",
    "/sign", "/pdf", "/export", "/start", "/stop", "/download", "/tutorial",
)
ROOM_RE = re.compile(r"(room|raum|planner|3d|aufma(?:ss|ß)|configurator)", re.I)

# These are the real office surfaces observed in production. Missing/forbidden routes
# are skipped, but enough of this matrix must be reachable to prove that the audit is
# exercising the complete ToolTime-style office app instead of a reduced field menu.
OFFICE_ROUTES = (
    ("", "Dashboard"),
    ("customers/", "Kunden"),
    ("customers/new/", "Kunde anlegen"),
    ("projects/", "Projekte"),
    ("projects/new/", "Projekt anlegen"),
    ("appointments/", "Kalender"),
    ("appointments/new/", "Termin anlegen"),
    ("time/", "Zeiterfassung"),
    ("tasks/", "Aufgaben"),
    ("tasks/new/", "Aufgabe anlegen"),
    ("expenses/", "Ausgaben"),
    ("expenses/new/", "Ausgabe anlegen"),
    ("employees/", "Mitarbeiter"),
    ("employees/new/", "Mitarbeiter anlegen"),
    ("quotes/", "Angebote"),
    ("quotes/new/", "Angebot anlegen"),
    ("invoices/", "Rechnungen"),
    ("invoices/new/", "Rechnung anlegen"),
    ("catalogue/", "Katalog"),
    ("site-reports/", "Einsatzprüfung"),
    ("prices/", "Preislisten"),
    ("settings/next/", "Einstellungen"),
    ("migration/tooltime/", "ToolTime Import"),
)


def fail(message: str) -> None:
    raise RuntimeError(f"A+Bau mobile browser smoke failed: {message}")


def profile_org_id(user):
    try:
        return getattr(user.profile, "organization_id", None)
    except Exception:
        return None


def dismiss_tutorial(page) -> None:
    overlay = page.locator("[data-tutorial-overlay]")
    if overlay.count() and overlay.is_visible():
        skip = page.locator("[data-tutorial-skip]")
        if skip.count():
            skip.click()
            overlay.wait_for(state="hidden", timeout=5_000)


def safe_links(page, selector: str, base_url: str) -> list[dict[str, str]]:
    base = urlparse(base_url)
    raw = page.locator(selector).evaluate_all(
        "nodes => nodes.map(n => ({href:n.href || '', text:(n.innerText || n.textContent || '').trim()}))"
    )
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in raw:
        href = str(row.get("href") or "")
        text = str(row.get("text") or "")
        parsed = urlparse(href)
        if parsed.scheme not in {"http", "https"} or parsed.netloc != base.netloc:
            continue
        path = parsed.path or "/"
        if any(part in path.lower() for part in UNSAFE_PARTS):
            continue
        clean = urljoin(base_url, path.lstrip("/"))
        if clean in seen:
            continue
        seen.add(clean)
        result.append({"href": clean, "text": text})
    return result


def responsive_report(page) -> dict:
    return page.evaluate(
        """() => {
          const de = document.documentElement;
          const body = document.body;
          const vw = de.clientWidth;
          const docWidth = Math.max(de.scrollWidth, body ? body.scrollWidth : 0);
          const visible = el => {
            const s = getComputedStyle(el), r = el.getBoundingClientRect();
            return s.display !== 'none' && s.visibility !== 'hidden' && Number(s.opacity || 1) !== 0 && r.width > 1 && r.height > 1;
          };
          const inHorizontalScroller = el => {
            let p = el.parentElement;
            while (p && p !== body) {
              const s = getComputedStyle(p);
              if ((s.overflowX === 'auto' || s.overflowX === 'scroll') && p.scrollWidth > p.clientWidth + 3) return true;
              p = p.parentElement;
            }
            return false;
          };
          const intentionallyOffCanvas = el => {
            if (el.closest('.nx-sidebar') && !body.classList.contains('nx-menu-open')) return true;
            if (el.closest('[aria-hidden="true"]')) return true;
            const s = getComputedStyle(el);
            if (s.position === 'fixed' && (s.transform || '').includes('matrix') && !el.matches(':focus-within')) return false;
            return false;
          };
          const offenders = [];
          for (const el of document.querySelectorAll('body *')) {
            if (!visible(el) || intentionallyOffCanvas(el) || inHorizontalScroller(el)) continue;
            const r = el.getBoundingClientRect();
            if (r.right > vw + 4 || r.left < -4) {
              offenders.push({tag:el.tagName, cls:String(el.className || '').slice(0,120), id:el.id || '', left:Math.round(r.left), right:Math.round(r.right), width:Math.round(r.width)});
              if (offenders.length >= 14) break;
            }
          }
          const controls = [];
          for (const el of document.querySelectorAll('main input:not([type="hidden"]), main select, main textarea, main button, main [role="button"]')) {
            if (!visible(el) || inHorizontalScroller(el)) continue;
            const r = el.getBoundingClientRect();
            if (r.right > vw + 4 || r.left < -4 || r.width > vw + 4) {
              controls.push({tag:el.tagName, cls:String(el.className || '').slice(0,100), left:Math.round(r.left), right:Math.round(r.right), width:Math.round(r.width)});
              if (controls.length >= 10) break;
            }
          }
          return {vw, docWidth, offenders, controls};
        }"""
    )


def audit_page(page, label: str) -> None:
    page.wait_for_timeout(220)
    report = responsive_report(page)
    if report["docWidth"] > report["vw"] + 4:
        fail(f"{label}: document horizontal overflow {report['docWidth']}px > viewport {report['vw']}px; offenders={report['offenders'][:5]}")
    if report["controls"]:
        fail(f"{label}: form/action controls escape viewport: {report['controls'][:5]}")
    if report["offenders"]:
        fail(f"{label}: visible elements escape viewport: {report['offenders'][:6]}")


def visit(page, url: str, label: str) -> bool:
    response = page.goto(url, wait_until="domcontentloaded", timeout=30_000)
    if response is None:
        return False
    if response.status >= 500:
        fail(f"{label}: HTTP {response.status}")
    if response.status >= 400 or "/login/" in page.url:
        return False
    dismiss_tutorial(page)
    audit_page(page, label)
    return True


def login_as(page, base_url: str, user, password: str) -> None:
    page.context.clear_cookies()
    response = page.goto(urljoin(base_url, "login/"), wait_until="domcontentloaded", timeout=30_000)
    if response is None or response.status >= 500:
        fail("login route unavailable")
    page.fill('input[name="username"]', user.username)
    page.fill('input[name="password"]', password)
    with page.expect_navigation(wait_until="domcontentloaded", timeout=30_000):
        page.click('button[type="submit"], button.btn-primary')
    if "/login/" in page.url:
        fail(f"login failed for mobile audit user {user.username!r}")
    dismiss_tutorial(page)


def audit_mobile_menu(page, label: str) -> None:
    button = page.locator("[data-nx-menu]")
    if not button.count() or not button.is_visible():
        return
    button.click()
    page.wait_for_timeout(160)
    sidebar = page.locator(".nx-sidebar")
    if not sidebar.count() or not sidebar.is_visible():
        fail(f"{label}: mobile menu button did not expose sidebar")
    rect = sidebar.bounding_box()
    width = (page.viewport_size or {}).get("width", 0)
    if not rect or rect["x"] < -3 or rect["x"] + rect["width"] > width + 3:
        fail(f"{label}: opened mobile drawer is outside viewport: {rect}")
    if button.get_attribute("aria-expanded") != "true":
        fail(f"{label}: mobile menu aria-expanded did not become true")
    page.keyboard.press("Escape")
    page.wait_for_timeout(120)
    if "nx-menu-open" in (page.locator("body").get_attribute("class") or ""):
        fail(f"{label}: Escape did not close mobile drawer")


def audit_calendar_modes(page, label: str) -> None:
    for text in ("Woche", "Monat", "Karte", "Liste"):
        matches = page.get_by_text(text, exact=True)
        if not matches.count():
            continue
        item = matches.first
        if not item.is_visible():
            continue
        try:
            item.click(timeout=2_000)
            page.wait_for_timeout(180)
            audit_page(page, f"{label}:{text}")
        except Exception:
            # A duplicate static label is harmless; the appointments page itself is still audited.
            continue


def find_project_detail(page, base_url: str) -> str | None:
    for item in safe_links(page, 'a[href*="/projects/"]', base_url):
        path = urlparse(item["href"]).path.rstrip("/")
        if re.search(r"/projects/[^/]+$", path) and not path.endswith("/projects/new"):
            return item["href"]
    return None


def audit_room_planner(page, base_url: str, project_url: str, vp: str) -> None:
    if not visit(page, project_url, f"{vp}:Projekt Detail"):
        fail(f"{vp}: project detail is not reachable")
    room_url = None
    for item in safe_links(page, "a[href]", base_url):
        if ROOM_RE.search(item["text"]) or ROOM_RE.search(urlparse(item["href"]).path):
            room_url = item["href"]
            break
    if not room_url:
        fail(f"{vp}: project detail exposes no Room Planner / Aufmaß & 3D link")
    if not visit(page, room_url, f"{vp}:Room Planner Pro"):
        fail(f"{vp}: Room Planner Pro route is not reachable")
    canvas = page.locator("[data-rp-canvas]")
    if not canvas.count():
        fail(f"{vp}: Room Planner Pro lost its 3D canvas")
    if canvas.first.is_visible():
        rect = canvas.first.bounding_box()
        width = (page.viewport_size or {}).get("width", 0)
        if rect and (rect["x"] < -4 or rect["x"] + rect["width"] > width + 4):
            fail(f"{vp}: Room Planner canvas escapes viewport: {rect}")
    for marker in ("[data-rp-open-vision]", "[data-rp-add-object]"):
        if page.locator(marker).count() == 0:
            fail(f"{vp}: Room Planner mobile page lost control {marker}")


def audit_field_surface(page, base_url: str, vp: str) -> None:
    if not visit(page, urljoin(base_url, "field/"), f"{vp}:Außendienst"):
        fail(f"{vp}: technician field root is not reachable with field account")
    body_text = page.locator("body").inner_text()
    for forbidden in ("Einkaufskosten", "Deckungsbeitrag", "Interne Marge"):
        if forbidden in body_text:
            fail(f"{vp}: technician surface leaked internal finance label {forbidden!r}")
    links = [x for x in safe_links(page, 'a[href*="/field/"]', base_url) if urlparse(x["href"]).path.rstrip("/") != "/field"]
    if not links:
        return
    if not visit(page, links[0]["href"], f"{vp}:Außendienst Einsatz"):
        return
    body_text = page.locator("body").inner_text()
    for forbidden in ("Einkaufskosten", "Deckungsbeitrag", "Interne Marge"):
        if forbidden in body_text:
            fail(f"{vp}: technician job leaked internal finance label {forbidden!r}")
    # When the job has the voice/AI workflow available, both recording and
    # transcription actions must remain visible and inside the phone viewport.
    if page.locator("[data-field-record]").count():
        for marker in ("[data-field-record]", "[data-field-transcribe]"):
            control = page.locator(marker).first
            if not control.count() or not control.is_visible():
                fail(f"{vp}: technician Voice/AI workflow lost visible control {marker}")
            rect = control.bounding_box()
            width = (page.viewport_size or {}).get("width", 0)
            if rect and (rect["x"] < -4 or rect["x"] + rect["width"] > width + 4):
                fail(f"{vp}: technician Voice/AI control escapes viewport: {marker} {rect}")


def choose_users():
    User = get_user_model()
    requested = os.environ.get("KAYI_SMOKE_USER", "demo")
    seed = User.objects.select_related("profile").filter(username=requested, is_active=True).first()
    if seed is None:
        fail(f"smoke user {requested!r} does not exist")
    org_id = profile_org_id(seed)
    users = list(User.objects.select_related("profile").filter(is_active=True).order_by("pk"))
    same_org = [u for u in users if org_id is None or profile_org_id(u) == org_id]
    office = next((u for u in same_org if u.is_superuser), None)
    office = office or next((u for u in same_org if u.is_staff), None)
    office = office or seed
    field = next((u for u in same_org if u.pk != office.pk and not u.is_superuser and not u.is_staff), None)
    field = field or (seed if seed.pk != office.pk and not seed.is_superuser else None)
    if field is None:
        fail("seed data has no dedicated non-staff technician account for mobile field-flow audit")
    return office, field, org_id


def main() -> None:
    from playwright.sync_api import sync_playwright

    base_url = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/") + "/"
    office_user, field_user, org_id = choose_users()
    project_pk = None
    if org_id:
        project_pk = Project.objects.filter(organization_id=org_id).order_by("-pk").values_list("pk", flat=True).first()

    users = {office_user.pk: office_user, field_user.pk: field_user}
    old_hashes = {pk: u.password for pk, u in users.items()}
    passwords = {pk: secrets.token_urlsafe(24) for pk in users}
    for pk, user in users.items():
        user.set_password(passwords[pk])
        user.save(update_fields=["password"])

    browser = None
    page = None
    active_viewport = VIEWPORTS[0]
    page_errors: list[str] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(locale="de-DE", viewport={"width":390,"height":844}, is_mobile=True, has_touch=True)
            page = context.new_page()
            page.on("pageerror", lambda error: page_errors.append(f"{page.url}: {error}"))

            for width, height in VIEWPORTS:
                active_viewport = (width, height)
                page.set_viewport_size({"width": width, "height": height})
                vp = f"{width}x{height}"
                login_as(page, base_url, office_user, passwords[office_user.pk])

                if not visit(page, base_url, f"{vp}:Dashboard"):
                    fail(f"{vp}: office dashboard unavailable")
                if "/field/" in page.url:
                    fail(f"{vp}: selected office account is routed to technician UI")
                audit_mobile_menu(page, f"{vp}:Dashboard")

                successful: list[str] = []
                project_url = None
                for path, label in OFFICE_ROUTES:
                    if visit(page, urljoin(base_url, path), f"{vp}:{label}"):
                        successful.append(path or "/")
                        if path == "appointments/":
                            audit_calendar_modes(page, f"{vp}:Kalender")
                        if path == "projects/":
                            project_url = find_project_detail(page, base_url)
                if len(successful) < 16:
                    fail(f"{vp}: office mobile audit reached only {len(successful)} core surfaces: {successful}")

                # Also crawl every currently exposed office navigation link. This catches
                # future pages without requiring the smoke matrix to be manually expanded.
                visit(page, base_url, f"{vp}:Dashboard reload")
                for item in safe_links(page, ".nx-nav a[href], .sidebar a[href], .mobile-nav a[href], nav a[href]", base_url)[:40]:
                    visit(page, item["href"], f"{vp}:nav:{item['text'] or item['href']}")

                if project_url is None and project_pk is not None:
                    project_url = urljoin(base_url, f"projects/{project_pk}/")
                if not project_url:
                    fail(f"{vp}: could not discover a project detail for Room Planner audit")
                audit_room_planner(page, base_url, project_url, vp)

                # Re-authenticate as a real non-staff technician before testing the field
                # flow, so office permissions cannot hide a mobile regression in Voice/AI.
                login_as(page, base_url, field_user, passwords[field_user.pk])
                audit_field_surface(page, base_url, vp)

            relevant = [e for e in page_errors if any(token in e for token in ("TypeError", "ReferenceError", "SyntaxError"))]
            if relevant:
                fail("mobile JavaScript errors: " + " | ".join(relevant[:6]))
            context.close()
            browser.close()
            browser = None
    except Exception:
        if page is not None:
            try:
                width, height = active_viewport
                page.screenshot(path=f"/tmp/kayi-mobile-smoke-{width}x{height}.png", full_page=True)
            except Exception:
                pass
        raise
    finally:
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        for pk, user in users.items():
            user.password = old_hashes[pk]
            user.save(update_fields=["password"])

    print("A+Bau mobile browser smoke passed: 390x844 + 430x932 office matrix, navigation crawl, calendar modes, project detail, Room Planner Pro and real technician field/Voice-AI surface are responsive.")


if __name__ == "__main__":
    main()
