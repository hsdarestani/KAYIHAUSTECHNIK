#!/usr/bin/env python3
from __future__ import annotations

import os
import secrets
import sys
from urllib.parse import urljoin

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.contrib.auth import get_user_model

from erp.models import Project


def fail(message: str) -> None:
    raise RuntimeError(f"KAYI browser smoke failed: {message}")


def main() -> None:
    from playwright.sync_api import sync_playwright

    base_url = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/") + "/"
    username = os.environ.get("KAYI_SMOKE_USER", "demo")
    User = get_user_model()
    user = User.objects.select_related("profile").filter(username=username).first()
    if user is None:
        fail(f"smoke user {username!r} does not exist")

    old_password_hash = user.password
    temporary_password = secrets.token_urlsafe(24)
    user.set_password(temporary_password)
    user.save(update_fields=["password"])

    page_errors: list[str] = []
    browser = None
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

            checks = [
                ("", "Dashboard"),
                ("projects/new/", "3-Schritte-Projektassistent"),
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
            if steps.count() != 3:
                fail(f"project wizard rendered {steps.count()} steps instead of 3")
            if page.locator("section.wizard-step.active").get_attribute("data-step") != "1":
                fail("project wizard did not start at step 1")
            page.click("[data-wizard-next]")
            if page.locator("section.wizard-step.active").get_attribute("data-step") != "2":
                fail("project wizard could not advance to step 2")
            page.click("[data-wizard-next]")
            if page.locator("section.wizard-step.active").get_attribute("data-step") != "3":
                fail("project wizard could not advance to step 3")

            organization_id = getattr(getattr(user, "profile", None), "organization_id", None)
            project = Project.objects.filter(organization_id=organization_id).order_by("-pk").first() if organization_id else None
            if project is not None:
                response = page.goto(urljoin(base_url, f"projects/{project.pk}/"), wait_until="domcontentloaded", timeout=30_000)
                if response is None or response.status >= 500:
                    fail(f"project detail returned {response.status if response else 'no response'}")
                if "Nächste Schritte" not in page.content():
                    fail("project detail is missing the task-oriented next-step panel")

            if page_errors:
                fail("browser page errors: " + " | ".join(page_errors[:5]))
            context.close()
            browser.close()
            browser = None
    finally:
        if browser is not None:
            browser.close()
        user.password = old_password_hash
        user.save(update_fields=["password"])

    print("KAYI browser smoke passed: login, dashboard, 3-step wizard, reports, prices and project detail.")


if __name__ == "__main__":
    main()
