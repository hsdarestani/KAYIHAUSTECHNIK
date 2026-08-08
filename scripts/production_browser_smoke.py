#!/usr/bin/env python3
from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path
from urllib.parse import urljoin

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
            page.on("pageerror", lambda error: page_errors.append(str(error)))

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

            page.goto(urljoin(base_url, "projects/new/"), wait_until="networkidle", timeout=30_000)
            steps = page.locator("section.wizard-step")
            if steps.count() != 9:
                fail(f"project wizard rendered {steps.count()} steps instead of 9")
            if page.locator("section.wizard-step.active").get_attribute("data-step") != "1":
                fail("project wizard did not start at step 1")

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
                fail("browser page errors: " + " | ".join(page_errors[:5]))
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

    print("KAYI browser smoke passed: login, tutorial gate, dashboard, full 9-step wizard, reports, prices and project detail.")


if __name__ == "__main__":
    main()
