#!/usr/bin/env python3
from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.contrib.auth import get_user_model
from erp.models import UserProfile

SCREENSHOT_PATH = Path("/tmp/kayi-next-browser-smoke.png")


def fail(message: str) -> None:
    raise RuntimeError(f"KAYI Next browser smoke failed: {message}")


def assert_page(page, base_url: str, path: str, markers: tuple[str, ...]) -> None:
    response = page.goto(urljoin(base_url, path.lstrip("/")), wait_until="domcontentloaded", timeout=30_000)
    if response is None or response.status >= 500:
        fail(f"{path} returned {response.status if response else 'no response'}")
    if "/login/" in page.url:
        fail(f"{path} unexpectedly redirected to login")
    html = page.content()
    for marker in markers:
        if marker not in html:
            fail(f"{path} is missing {marker!r}")


def main() -> None:
    from playwright.sync_api import sync_playwright

    base_url = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/") + "/"
    username = os.environ.get("KAYI_SMOKE_USER", "demo")
    User = get_user_model()
    user = User.objects.select_related("profile").filter(username=username).first()
    if user is None:
        fail(f"smoke user {username!r} does not exist")
    profile = getattr(user, "profile", None)
    if profile is None:
        fail(f"smoke user {username!r} has no KAYI profile")

    old_password_hash = user.password
    old_role = profile.role
    old_mobile_worker = profile.is_mobile_worker
    temporary_password = secrets.token_urlsafe(24)
    user.set_password(temporary_password)
    user.save(update_fields=["password"])

    # The demo account may intentionally be seeded as a mobile worker. Browser
    # smoke must validate both surfaces explicitly instead of assuming one role.
    profile.role = UserProfile.Role.OFFICE
    profile.is_mobile_worker = False
    profile.save(update_fields=["role", "is_mobile_worker", "updated_at"])

    browser = None
    page = None
    page_errors: list[str] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(locale="de-DE", viewport={"width": 1440, "height": 1000})
            page = context.new_page()
            page.on("pageerror", lambda error: page_errors.append(f"{page.url}: {error}"))

            response = page.goto(urljoin(base_url, "login/"), wait_until="domcontentloaded", timeout=30_000)
            if response is None or response.status >= 500:
                fail("login route is unavailable")
            page.fill('input[name="username"]', username)
            page.fill('input[name="password"]', temporary_password)
            with page.expect_navigation(wait_until="domcontentloaded", timeout=30_000):
                page.click('button[type="submit"], button.btn-primary')
            if "/login/" in page.url:
                fail("login did not establish an authenticated session")

            overlay = page.locator("[data-tutorial-overlay]")
            if overlay.count() and overlay.is_visible():
                skip = page.locator("[data-tutorial-skip]")
                if skip.count():
                    skip.click()
                    overlay.wait_for(state="hidden", timeout=5_000)

            office_checks = [
                ("/", ("Was steht an?", "Von ToolTime wechseln", "kayi-next.css")),
                ("/customers/", ("Kunden", "Neuer Kunde")),
                ("/customers/new/", ("Neuen Kunden anlegen", "Nur das eintragen")),
                ("/projects/", ("Projekte", "Neues Projekt")),
                ("/projects/new/", ("Projekt anlegen", "Kein Wizard", "Aufmaß / 3D")),
                ("/appointments/", ("Termine", "Neuer Termin")),
                ("/appointments/new/", ("Neuer Termin", "Baustellendokumentation")),
                ("/time/", ("Zeiterfassung", "Letzte Buchungen")),
                ("/tasks/", ("Aufgaben", "Neue Aufgabe")),
                ("/tasks/new/", ("Neue Aufgabe", "Speichern")),
                ("/expenses/", ("Ausgaben", "Ausgabe erfassen")),
                ("/expenses/new/", ("Ausgabe erfassen", "Speichern")),
                ("/employees/", ("Mitarbeiter", "Mitarbeiter")),
                ("/employees/new/", ("Mitarbeiter anlegen", "Speichern")),
                ("/quotes/", ("Angebote", "Neues Angebot")),
                ("/invoices/", ("Rechnungen", "Neue Rechnung")),
                ("/migration/tooltime/", ("Von ToolTime zu KAYI", "Import starten")),
            ]
            for path, markers in office_checks:
                assert_page(page, base_url, path, markers)

            page.goto(urljoin(base_url, "projects/new/"), wait_until="domcontentloaded", timeout=30_000)
            html = page.content()
            if "9-Schritte-Projektassistent" in html or "wizard-step" in html:
                fail("legacy project wizard is still the primary creation flow")
            visible_controls = page.locator('form input:not([type="hidden"]), form select, form textarea')
            if visible_controls.count() < 4:
                fail("new project flow has too few controls and appears broken")

            # Switch the same authenticated account to the field role and verify
            # the separate ToolTime-style Monteur product surface.
            profile.role = UserProfile.Role.TECHNICIAN
            profile.is_mobile_worker = True
            profile.save(update_fields=["role", "is_mobile_worker", "updated_at"])
            response = page.goto(base_url, wait_until="domcontentloaded", timeout=30_000)
            if response is None or response.status >= 500:
                fail("technician root is unavailable")
            if not page.url.rstrip("/").endswith("/field"):
                fail(f"technician root did not redirect to /field/: {page.url}")
            field_html = page.content()
            for marker in ("Meine Einsätze", "Geplant", "Überfällig", "Dokumentiert", "nx-field-bottom"):
                if marker not in field_html:
                    fail(f"technician field surface is missing {marker!r}")
            if page.locator(".nx-mobile-tabs").count() != 1:
                fail("field home is missing ToolTime-style status tabs")
            if "Angebote" in page.locator(".nx-sidebar").inner_text() or "Rechnungen" in page.locator(".nx-sidebar").inner_text():
                fail("technician navigation exposes office finance modules")

            if page_errors:
                fail("browser page errors: " + " | ".join(page_errors[:8]))
            context.close()
            browser.close()
            browser = None
    except Exception:
        if page is not None:
            try:
                page.screenshot(path=str(SCREENSHOT_PATH), full_page=True)
                print(f"Failure screenshot: {SCREENSHOT_PATH}", file=sys.stderr)
                print(f"Failure URL: {page.url}", file=sys.stderr)
            except Exception:
                pass
        raise
    finally:
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        user.password = old_password_hash
        user.save(update_fields=["password"])
        profile.role = old_role
        profile.is_mobile_worker = old_mobile_worker
        profile.save(update_fields=["role", "is_mobile_worker", "updated_at"])

    print("KAYI Next browser smoke passed: office flow, project creation, planning, technician role, tasks, expenses, team, commercial documents and ToolTime migration.")


if __name__ == "__main__":
    main()
