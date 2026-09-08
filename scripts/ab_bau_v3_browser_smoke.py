"""Exercise the assembled V3 shell and structural workspaces in Chromium.

Uses a short-lived Django session against the local CI server. No business records
or account passwords are changed.
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from erp.models import UserProfile
from playwright.sync_api import expect, sync_playwright


def main():
    base = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
    if urlparse(base).hostname not in {"127.0.0.1", "localhost"}:
        raise RuntimeError("V3 CI smoke requires a local test server")
    demo = get_user_model().objects.select_related("profile").get(username=os.environ.get("KAYI_SMOKE_USER", "demo"))
    user = get_user_model().objects.create_user(username=f"v3-smoke-{uuid.uuid4().hex}")
    profile = user.profile
    profile.organization = demo.profile.organization
    profile.role = UserProfile.Role.OFFICE
    profile.is_mobile_worker = False
    profile.save()
    client = Client()
    client.force_login(user)
    session = client.session
    routes = [reverse(name) for name in (
        "next-project-create", "next-appointment-create", "next-customer-create",
        "next-quote-create", "next-invoice-create", "next-expense-create",
        "next-task-create", "next-tooltime-migration",
    )]
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            for width, height in [(1440, 1000), (390, 844), (430, 932)]:
                context = browser.new_context(viewport={"width": width, "height": height}, locale="de-DE")
                context.add_cookies([{"name": settings.SESSION_COOKIE_NAME,
                                     "value": session.session_key, "url": base}])
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                try:
                    response = page.goto(base + "/", wait_until="networkidle")
                    assert response.status == 200
                    skip = page.locator("[data-tutorial-skip]:visible")
                    if skip.count():
                        skip.first.click()
                    expect(page.locator("[data-ab-v3-dashboard]")).to_be_visible()
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), "Dashboard overflows viewport"

                    # On mobile the off-canvas sidebar's create control still has layout
                    # and therefore matches Playwright's :visible even while it is outside
                    # the viewport. Exercise the dedicated mobile FAB there; on desktop,
                    # exercise the persistent sidebar command trigger.
                    trigger = page.locator(".ab-v3-mobile-fab" if width <= 980 else ".ab-v3-create")
                    expect(trigger).to_be_visible()
                    trigger.click()
                    dialog = page.get_by_role("dialog", name="Schnell erstellen")
                    search = page.get_by_role("textbox", name="Aktion suchen")
                    expect(dialog).to_be_visible()
                    expect(search).to_be_focused()
                    links = dialog.locator("[data-ab-v3-command-item]")
                    assert sorted(links.evaluate_all("(nodes) => nodes.map(node => node.getAttribute('href'))")) == sorted(routes)
                    search.fill("Rechnung")
                    expect(dialog.locator("[data-ab-v3-command-item]:visible")).to_have_count(1)
                    search.fill("zz-no-matching-action")
                    expect(dialog.get_by_role("status")).to_be_visible()
                    expect(dialog.locator("[data-ab-v3-command-item]:visible")).to_have_count(0)
                    search.fill("")
                    search.press("Shift+Tab")
                    expect(links.last).to_be_focused()
                    links.last.press("Tab")
                    expect(search).to_be_focused()
                    page.screenshot(path=f"/tmp/kayi-v3-command-{width}.png")
                    search.press("Escape")
                    expect(dialog).not_to_be_visible()
                    expect(trigger).to_be_focused()
                    assert not page.locator("[data-ab-v3-dashboard]").evaluate("(node) => !!node.closest('[inert]')")

                    # The command palette's customer destination must now land on the
                    # V3 direct-create surface instead of an arbitrary legacy form.
                    page.keyboard.press("Control+k")
                    expect(dialog).to_be_visible()
                    search.fill("Kunde anlegen")
                    search.press("Enter")
                    page.wait_for_url(base + reverse("next-customer-create"))
                    expect(page.locator("[data-ab-v3-customer-form]")).to_be_visible()
                    expect(page.get_by_role("heading", name="Kunde anlegen")).to_be_visible()
                    expect(page.get_by_label("Firmenname")).to_be_visible()
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), "Customer create overflows viewport"

                    # Phase 2 directories are real interactive surfaces, not screenshot
                    # shells: both create dialogs must open/close in desktop and mobile.
                    page.goto(base + reverse("next-customers"), wait_until="networkidle")
                    expect(page.locator("[data-ab-v3-customers]")).to_be_visible()
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), "Customer directory overflows viewport"
                    page.locator("[data-customer-modal-show]").click()
                    customer_dialog = page.locator("[data-customer-modal]")
                    expect(customer_dialog).to_be_visible()
                    expect(customer_dialog.get_by_label("Firmenname")).to_be_visible()
                    customer_dialog.locator("[data-customer-modal-close]").last.click()
                    expect(customer_dialog).not_to_be_visible()

                    page.goto(base + reverse("next-projects"), wait_until="networkidle")
                    expect(page.locator("[data-ab-v3-projects]")).to_be_visible()
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), "Project directory overflows viewport"
                    page.locator("[data-project-modal-open]").click()
                    project_dialog = page.locator("[data-project-modal]")
                    expect(project_dialog).to_be_visible()
                    expect(project_dialog.get_by_label("Projekttitel")).to_be_visible()
                    project_dialog.locator("[data-project-modal-close]").last.click()
                    expect(project_dialog).not_to_be_visible()

                    # All global command destinations remain server-backed and reachable.
                    for route in routes:
                        result = context.request.get(base + route)
                        assert result.status == 200, (route, result.status)
                        assert "/login/" not in result.url, route

                    page.goto(base + "/", wait_until="networkidle")
                    page.screenshot(path=f"/tmp/kayi-v3-dashboard-{width}.png", full_page=True)
                    assert not errors, errors
                    print(f"V3 {width}x{height}: dashboard, Phase-2 directories, create dialogs, command routes, keyboard and focus passed")
                except Exception:
                    page.screenshot(path=f"/tmp/kayi-v3-failure-{width}.png", full_page=True)
                    raise
                finally:
                    context.close()
            browser.close()
    finally:
        session.delete()
        user.delete()


if __name__ == "__main__":
    main()
