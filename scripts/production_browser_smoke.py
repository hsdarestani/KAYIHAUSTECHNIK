#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import secrets
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

# Executing `python scripts/production_browser_smoke.py` makes `scripts/` the
# first import root. Add the repository root explicitly so Django's `config`
# package is importable in CI and inside the production smoke container.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.contrib.auth import get_user_model

from erp.models import Project


SCREENSHOT_PATH = Path("/tmp/kayi-browser-smoke.png")
FORM_CONTROL_SELECTOR = (
    'input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="reset"]),'
    'select,textarea'
)
UNSAFE_PATH_PARTS = (
    "/logout", "/delete", "/remove", "/archive", "/send", "/approve", "/reject",
    "/sign", "/pdf", "/export", "/start", "/stop", "/download", "/tutorial",
)
CREATE_LINK_RE = re.compile(r"\b(neu|neue|neues|neuen|erstellen|anlegen|hinzufügen|erfassen)\b", re.I)


def fail(message: str) -> None:
    raise RuntimeError(f"KAYI browser smoke failed: {message}")


def dismiss_first_run_tutorial(page) -> None:
    """Complete the real first-run tutorial gate before testing app controls."""
    overlay = page.locator("[data-tutorial-overlay]")
    if overlay.count() == 0:
        return
    page.wait_for_timeout(650)
    if overlay.is_visible():
        skip = page.locator("[data-tutorial-skip]")
        if skip.count() == 0:
            fail("first-run tutorial opened without a skip control")
        skip.click()
        overlay.wait_for(state="hidden", timeout=5_000)


def safe_links(page, selector: str, base_url: str) -> list[dict[str, str]]:
    base = urlparse(base_url)
    raw = page.locator(selector).evaluate_all(
        """nodes => nodes.map(node => ({href: node.href || '', text: (node.innerText || '').trim()}))"""
    )
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw:
        href = str(item.get("href") or "")
        text = str(item.get("text") or "")
        parsed = urlparse(href)
        if not href or parsed.scheme not in {"http", "https"}:
            continue
        if parsed.netloc != base.netloc:
            continue
        path = parsed.path or "/"
        lowered = path.lower()
        if any(part in lowered for part in UNSAFE_PATH_PARTS):
            continue
        clean = urljoin(base_url, path.lstrip("/"))
        if clean in seen:
            continue
        seen.add(clean)
        result.append({"href": clean, "text": text})
    return result


def audit_forms(page, label: str) -> tuple[int, int]:
    """Require every meaningful app form to be explicitly polished or explicitly exempted."""
    page.wait_for_timeout(180)
    forms = page.locator("form")
    audited = 0
    polished = 0
    for index in range(forms.count()):
        form = forms.nth(index)
        controls = form.locator(FORM_CONTROL_SELECTOR)
        if controls.count() == 0:
            continue
        audited += 1
        state = form.get_attribute("data-kayi-form-audit")
        if not state:
            fail(f"{label}: form #{index + 1} was not classified by the global form system")
        if state != "polished":
            continue
        polished += 1
        classes = form.get_attribute("class") or ""
        if "kayi-form-polished" not in classes:
            fail(f"{label}: polished form #{index + 1} is missing its visual class")
        visual_control = form.locator(
            'input:not([type="checkbox"]):not([type="radio"]):not([type="hidden"]):not([type="submit"]):not([type="button"]), select, textarea'
        ).first
        if visual_control.count():
            metrics = visual_control.evaluate(
                """el => { const s = getComputedStyle(el); return {h: el.getBoundingClientRect().height, r: parseFloat(s.borderRadius) || 0}; }"""
            )
            if metrics["h"] < 39:
                fail(f"{label}: polished control is too short ({metrics['h']:.1f}px)")
            if metrics["r"] < 7:
                fail(f"{label}: polished control lost rounded field styling")
    return audited, polished


def visit_and_audit(page, url: str, label: str) -> tuple[int, int, list[dict[str, str]]]:
    response = page.goto(url, wait_until="domcontentloaded", timeout=30_000)
    if response is None:
        return 0, 0, []
    if response.status >= 500:
        fail(f"{label} returned HTTP {response.status}")
    if response.status >= 400 or "/login/" in page.url:
        return 0, 0, []
    page.wait_for_timeout(220)
    audited, polished = audit_forms(page, label)
    create_links = [item for item in safe_links(page, "main a[href], .content a[href]", url) if CREATE_LINK_RE.search(item["text"])]
    return audited, polished, create_links


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
        project_pk = (
            Project.objects.filter(organization_id=organization_id)
            .order_by("-pk")
            .values_list("pk", flat=True)
            .first()
        )

    old_password_hash = user.password
    temporary_password = secrets.token_urlsafe(24)
    user.set_password(temporary_password)
    user.save(update_fields=["password"])

    page_errors: list[str] = []
    browser = None
    page = None
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(locale="de-DE", viewport={"width": 1440, "height": 1000})
            page = context.new_page()
            page.on("pageerror", lambda error: page_errors.append(f"{page.url}: {error}"))

            response = page.goto(urljoin(base_url, "login/"), wait_until="domcontentloaded", timeout=30_000)
            if response is None or response.status >= 500:
                fail(f"login route returned {response.status if response else 'no response'}")
            page.fill('input[name="username"]', username)
            page.fill('input[name="password"]', temporary_password)
            with page.expect_navigation(wait_until="domcontentloaded", timeout=30_000):
                page.click('button[type="submit"], button.btn-primary')
            if "/login/" in page.url:
                fail("login did not establish an authenticated session")
            dismiss_first_run_tutorial(page)

            checks = [
                ("", "Dashboard"),
                ("projects/new/", "9-Schritte-Projektassistent"),
                ("site-reports/", "Leistungsnachweise"),
                ("prices/", "Preislisten"),
            ]
            for path, marker in checks:
                response = page.goto(urljoin(base_url, path), wait_until="domcontentloaded", timeout=30_000)
                if response is None or response.status >= 500:
                    fail(f"/{path} returned {response.status if response else 'no response'}")
                if "/login/" in page.url:
                    fail(f"/{path} unexpectedly redirected to login")
                if marker and marker not in page.content():
                    fail(f"/{path} is missing expected marker {marker!r}")

            # Event form keeps its deliberately tailored design, but is part of the same audit contract.
            response = page.goto(urljoin(base_url, "events/new/"), wait_until="networkidle", timeout=30_000)
            if response is None or response.status >= 500:
                fail(f"/events/new/ returned {response.status if response else 'no response'}")
            if "/login/" in page.url:
                fail("/events/new/ unexpectedly redirected to login")
            if "Termin anlegen" not in page.locator("body").inner_text():
                fail("event creation screen is missing its heading")
            if page.locator("body.event-form-page").count() != 1:
                fail("event creation screen did not activate the refined page layout")
            if page.locator(".event-form-layout").count() != 1:
                fail("event creation screen is missing the refined two-column layout")
            if page.locator(".event-form-section").count() < 4:
                fail("event creation screen is missing one or more grouped form sections")
            event_text = page.locator("body").inner_text()
            for marker in ("Teilnehmer & Erinnerungen", "Beginn", "Ende", "Ganztägig"):
                if marker not in event_text:
                    fail(f"refined event form is missing German UI marker {marker!r}")
            audit_forms(page, "events/new")

            # Crawl the real application navigation and the safe create/new links exposed by those pages.
            page.goto(base_url, wait_until="domcontentloaded", timeout=30_000)
            dismiss_first_run_tutorial(page)
            nav_links = safe_links(page, ".sidebar a[href], .mobile-nav a[href]", base_url)[:22]
            discovered_create: list[dict[str, str]] = []
            seen_create: set[str] = set()
            total_audited = 0
            total_polished = 0
            for item in nav_links:
                audited, polished, create_links = visit_and_audit(page, item["href"], f"nav:{item['text'] or item['href']}")
                total_audited += audited
                total_polished += polished
                for create in create_links:
                    if create["href"] not in seen_create:
                        seen_create.add(create["href"])
                        discovered_create.append(create)
            for item in discovered_create[:16]:
                audited, polished, _ = visit_and_audit(page, item["href"], f"create:{item['text'] or item['href']}")
                total_audited += audited
                total_polished += polished
            if total_audited == 0:
                fail("application form crawl did not discover any meaningful forms")
            if total_polished == 0:
                fail("application form crawl did not exercise any generic polished forms")

            # The specialist nine-step project wizard must retain its own layout and behavior.
            page.goto(urljoin(base_url, "projects/new/"), wait_until="networkidle", timeout=30_000)
            steps = page.locator("section.wizard-step")
            if steps.count() != 9:
                fail(f"project wizard rendered {steps.count()} steps instead of 9")
            if page.locator("section.wizard-step.active").get_attribute("data-step") != "1":
                fail("project wizard did not start at step 1")
            wizard_form = page.locator("form").first
            if wizard_form.count() and not (wizard_form.get_attribute("data-kayi-form-audit") or "").startswith("skip:specialized"):
                fail("project wizard was not protected from generic form restructuring")

            wizard_html = page.content()
            for marker in (
                'class="material-source-grid"',
                'data-inline-room-model="1"',
                'data-model-ai-apply',
                'data-quote="gross"',
            ):
                if marker not in wizard_html:
                    fail(f"nine-step wizard is missing specialist tool marker {marker!r}")

            for expected_step in range(2, 10):
                page.click("[data-wizard-next]")
                active_step = page.locator("section.wizard-step.active").get_attribute("data-step")
                if active_step != str(expected_step):
                    fail(f"project wizard could not advance to step {expected_step}; active={active_step!r}")

            if project_pk is not None:
                response = page.goto(urljoin(base_url, f"projects/{project_pk}/"), wait_until="domcontentloaded", timeout=30_000)
                if response is None or response.status >= 500:
                    fail(f"project detail returned {response.status if response else 'no response'}")
                if "Nächste Schritte" not in page.content():
                    fail("project detail is missing the task-oriented next-step panel")

            if page_errors:
                fail("browser page errors: " + " | ".join(page_errors[:8]))
            context.close()
            browser.close()
            browser = None
    except Exception as exc:
        if page is not None:
            try:
                page.screenshot(path=str(SCREENSHOT_PATH), full_page=True)
            except Exception:
                pass
            print(f"Browser smoke failed at URL: {page.url}", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        raise
    finally:
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        user.password = old_password_hash
        user.save(update_fields=["password"])

    print("KAYI browser smoke passed: global form crawl, refined event form, dashboard, full 9-step wizard, reports, prices and project detail.")


if __name__ == "__main__":
    main()
