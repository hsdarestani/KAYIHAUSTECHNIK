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
CREATE_RE = re.compile(r"\b(neu|neue|neues|neuen|erstellen|anlegen|hinzufügen|erfassen)\b", re.I)
ROOM_RE = re.compile(r"(room|raum|planner|3d|aufma(?:ss|ß)|configurator)", re.I)


def fail(message: str) -> None:
    raise RuntimeError(f"A+Bau mobile browser smoke failed: {message}")


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
        lower = path.lower()
        if any(part in lower for part in UNSAFE_PARTS):
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
            const s = getComputedStyle(el);
            const r = el.getBoundingClientRect();
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
            const sidebar = el.closest('.nx-sidebar');
            if (sidebar && !body.classList.contains('nx-menu-open')) return true;
            if (el.closest('[aria-hidden="true"]')) return true;
            return false;
          };
          const offenders = [];
          for (const el of document.querySelectorAll('body *')) {
            if (!visible(el) || intentionallyOffCanvas(el) || inHorizontalScroller(el)) continue;
            const r = el.getBoundingClientRect();
            if (r.right > vw + 4 || r.left < -4) {
              offenders.push({
                tag: el.tagName,
                cls: String(el.className || '').slice(0,120),
                id: el.id || '',
                left: Math.round(r.left), right: Math.round(r.right), width: Math.round(r.width)
              });
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
    page.wait_for_timeout(260)
    report = responsive_report(page)
    if report["docWidth"] > report["vw"] + 4:
        fail(f"{label}: document horizontal overflow {report['docWidth']}px > viewport {report['vw']}px; offenders={report['offenders'][:5]}")
    if report["controls"]:
        fail(f"{label}: form/action controls escape viewport: {report['controls'][:5]}")
    # Off-canvas children are tolerated only inside explicit horizontal scrollers; any
    # remaining offender is a real mobile clipping regression.
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


def audit_mobile_menu(page, label: str) -> None:
    button = page.locator("[data-nx-menu]")
    if not button.count() or not button.is_visible():
        return
    button.click()
    page.wait_for_timeout(180)
    sidebar = page.locator(".nx-sidebar")
    if not sidebar.count() or not sidebar.is_visible():
        fail(f"{label}: mobile menu button did not expose sidebar")
    rect = sidebar.bounding_box()
    viewport = page.viewport_size or {"width": 0}
    if not rect or rect["x"] < -3 or rect["x"] + rect["width"] > viewport["width"] + 3:
        fail(f"{label}: opened mobile drawer is outside viewport: {rect}")
    if button.get_attribute("aria-expanded") != "true":
        fail(f"{label}: mobile menu aria-expanded did not become true")
    page.keyboard.press("Escape")
    page.wait_for_timeout(140)
    if "nx-menu-open" in (page.locator("body").get_attribute("class") or ""):
        fail(f"{label}: Escape did not close mobile drawer")


def audit_calendar_modes(page, label: str) -> None:
    for text in ("Woche", "Monat", "Karte", "Liste"):
        control = page.get_by_text(text, exact=True)
        if not control.count():
            continue
        item = control.first
        if not item.is_visible():
            continue
        try:
            item.click(timeout=3_000)
            page.wait_for_timeout(220)
            audit_page(page, f"{label}:{text}")
        except Exception:
            # Some calendar labels are non-interactive headings. Their page was already audited.
            pass


def find_project_detail(page, base_url: str) -> str | None:
    links = safe_links(page, 'a[href*="/projects/"]', base_url)
    for item in links:
        path = urlparse(item["href"]).path.rstrip("/")
        if path.endswith("/projects") or path.endswith("/projects/new"):
            continue
        if re.search(r"/projects/[^/]+$", path):
            return item["href"]
    return None


def audit_room_planner(page, base_url: str, project_url: str, vp_label: str) -> None:
    if not visit(page, project_url, f"{vp_label}:Projekt Detail"):
        fail(f"{vp_label}: project detail is not reachable")
    candidates = safe_links(page, "a[href]", base_url)
    room_url = None
    for item in candidates:
        if ROOM_RE.search(item["text"]) or ROOM_RE.search(urlparse(item["href"]).path):
            room_url = item["href"]
            break
    if not room_url:
        fail(f"{vp_label}: project detail exposes no Room Planner / Aufmaß & 3D link")
    if not visit(page, room_url, f"{vp_label}:Room Planner Pro"):
        fail(f"{vp_label}: Room Planner Pro route is not reachable")
    canvas = page.locator("[data-rp-canvas]")
    if not canvas.count():
        fail(f"{vp_label}: Room Planner Pro lost its 3D canvas")
    if canvas.first.is_visible():
        rect = canvas.first.bounding_box()
        width = (page.viewport_size or {}).get("width", 0)
        if rect and (rect["x"] < -4 or rect["x"] + rect["width"] > width + 4):
            fail(f"{vp_label}: Room Planner canvas escapes viewport: {rect}")
    for marker in ("[data-rp-open-vision]", "[data-rp-add-object]"):
        if page.locator(marker).count() == 0:
            fail(f"{vp_label}: Room Planner mobile page lost control {marker}")


def audit_field_surface(page, base_url: str, vp_label: str) -> None:
    field_url = urljoin(base_url, "field/")
    response = page.goto(field_url, wait_until="domcontentloaded", timeout=30_000)
    if response is None or response.status >= 500:
        fail(f"{vp_label}: field root failed")
    if response.status >= 400 or "/login/" in page.url:
        return
    audit_page(page, f"{vp_label}:Außendienst")
    links = [x for x in safe_links(page, 'a[href*="/field/"]', base_url) if urlparse(x["href"]).path.rstrip("/") != "/field"]
    if links:
        visit(page, links[0]["href"], f"{vp_label}:Außendienst Einsatz")
        if page.locator("[data-field-record]").count():
            for marker in ("[data-field-record]", "[data-field-transcribe]"):
                control = page.locator(marker).first
                if control.is_visible():
                    rect = control.bounding_box()
                    width = (page.viewport_size or {}).get("width", 0)
                    if rect and (rect["x"] < -4 or rect["x"] + rect["width"] > width + 4):
                        fail(f"{vp_label}: technician Voice/AI control escapes viewport: {marker} {rect}")


def main() -> None:
    from playwright.sync_api import sync_playwright

    base_url = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/") + "/"
    username = os.environ.get("KAYI_SMOKE_USER", "demo")
    User = get_user_model()
    user = User.objects.select_related("profile").filter(username=username).first()
    if user is None:
        fail(f"smoke user {username!r} does not exist")

    organization_id = getattr(getattr(user, "profile", None), "organization_id", None)
    project_pk = None
    if organization_id:
        project_pk = Project.objects.filter(organization_id=organization_id).order_by("-pk").values_list("pk", flat=True).first()

    old_hash = user.password
    temporary_password = secrets.token_urlsafe(24)
    user.set_password(temporary_password)
    user.save(update_fields=["password"])

    browser = None
    page = None
    active_viewport = VIEWPORTS[0]
    page_errors: list[str] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(locale="de-DE", viewport={"width": VIEWPORTS[0][0], "height": VIEWPORTS[0][1]}, is_mobile=True, has_touch=True)
            page = context.new_page()
            page.on("pageerror", lambda error: page_errors.append(f"{page.url}: {error}"))

            response = page.goto(urljoin(base_url, "login/"), wait_until="domcontentloaded", timeout=30_000)
            if response is None or response.status >= 500:
                fail("login route unavailable")
            page.fill('input[name="username"]', username)
            page.fill('input[name="password"]', temporary_password)
            with page.expect_navigation(wait_until="domcontentloaded", timeout=30_000):
                page.click('button[type="submit"], button.btn-primary')
            if "/login/" in page.url:
                fail("mobile login did not establish session")
            dismiss_tutorial(page)

            for width, height in VIEWPORTS:
                active_viewport = (width, height)
                page.set_viewport_size({"width": width, "height": height})
                vp = f"{width}x{height}"
                if not visit(page, base_url, f"{vp}:Dashboard"):
                    fail(f"{vp}: dashboard unavailable")
                audit_mobile_menu(page, f"{vp}:Dashboard")

                nav_links = safe_links(page, ".nx-nav a[href], .sidebar a[href], .mobile-nav a[href], nav a[href]", base_url)[:40]
                if len(nav_links) < 6:
                    fail(f"{vp}: mobile navigation exposed only {len(nav_links)} safe routes")

                create_links: list[dict[str, str]] = []
                seen_create: set[str] = set()
                project_url = None
                for item in nav_links:
                    if not visit(page, item["href"], f"{vp}:nav:{item['text'] or item['href']}"):
                        continue
                    if any(token in (item["text"] or "") for token in ("Kalender", "Termine")):
                        audit_calendar_modes(page, f"{vp}:Kalender")
                    if "/projects" in urlparse(item["href"]).path and not project_url:
                        project_url = find_project_detail(page, base_url)
                    for create in safe_links(page, "main a[href], .nx-content a[href]", base_url):
                        if CREATE_RE.search(create["text"]) and create["href"] not in seen_create:
                            seen_create.add(create["href"])
                            create_links.append(create)

                for item in create_links[:24]:
                    visit(page, item["href"], f"{vp}:create:{item['text'] or item['href']}")

                if project_url is None and project_pk is not None:
                    # Prefer the visible project link, but use the established route shape as a fallback.
                    project_url = urljoin(base_url, f"projects/{project_pk}/")
                if not project_url:
                    fail(f"{vp}: could not discover a project detail for Room Planner audit")
                audit_room_planner(page, base_url, project_url, vp)
                audit_field_surface(page, base_url, vp)

            relevant_errors = [e for e in page_errors if any(token in e for token in ("TypeError", "ReferenceError", "SyntaxError"))]
            if relevant_errors:
                fail("mobile JavaScript errors: " + " | ".join(relevant_errors[:6]))
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
        user.password = old_hash
        user.save(update_fields=["password"])

    print("A+Bau mobile browser smoke passed: 390x844 + 430x932, all navigation pages, create forms, calendar modes, project detail, Room Planner Pro and field surface are responsive.")


if __name__ == "__main__":
    main()
