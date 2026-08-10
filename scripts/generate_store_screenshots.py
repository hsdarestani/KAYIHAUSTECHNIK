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
from PIL import Image
from playwright.sync_api import sync_playwright

OUTPUT = ROOT / "store" / "generated" / "screenshots"


def login(page, base_url: str, username: str, password: str) -> None:
    page.goto(urljoin(base_url, "login/"), wait_until="domcontentloaded", timeout=30_000)
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', password)
    with page.expect_navigation(wait_until="domcontentloaded", timeout=30_000):
        page.click('button[type="submit"], button.btn-primary')
    if "/login/" in page.url:
        raise RuntimeError("Store screenshot login failed")
    overlay = page.locator("[data-tutorial-overlay]")
    if overlay.count() and overlay.is_visible():
        skip = page.locator("[data-tutorial-skip]")
        if skip.count():
            skip.click()


def normalize(path: Path) -> None:
    with Image.open(path) as im:
        im.convert("RGB").save(path, optimize=True)


def shot(page, path: Path) -> None:
    page.wait_for_timeout(600)
    path.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(path), full_page=False)
    normalize(path)


def capture_set(browser, base_url: str, username: str, password: str, folder: Path, css_width: int, css_height: int, scale: int) -> None:
    context = browser.new_context(
        locale="de-DE",
        viewport={"width": css_width, "height": css_height},
        device_scale_factor=scale,
        is_mobile=True,
        has_touch=True,
    )
    page = context.new_page()
    try:
        login(page, base_url, username, password)

        page.goto(base_url, wait_until="domcontentloaded", timeout=30_000)
        shot(page, folder / "01-dashboard.png")

        page.goto(urljoin(base_url, "projects/"), wait_until="domcontentloaded", timeout=30_000)
        shot(page, folder / "02-projekte.png")

        page.goto(urljoin(base_url, "appointments/"), wait_until="domcontentloaded", timeout=30_000)
        shot(page, folder / "03-termine.png")

        # Show a real project feature rather than a mock marketing screen.
        page.goto(urljoin(base_url, "projects/"), wait_until="domcontentloaded", timeout=30_000)
        hrefs = page.locator('a[href^="/projects/"]').evaluate_all(
            "els => els.map(e => e.getAttribute('href')).filter(h => /^\\/projects\\/\\d+\\/$/.test(h))"
        )
        if hrefs:
            page.goto(urljoin(base_url, hrefs[0].lstrip("/")), wait_until="domcontentloaded", timeout=30_000)
            planner = page.locator('a[href$="/room-planner/"]').first
            if planner.count():
                planner.click()
                page.wait_for_load_state("domcontentloaded")
                trigger = page.locator("[data-rp-open-vision]").first
                if trigger.count():
                    trigger.click()
                    page.wait_for_timeout(250)
        shot(page, folder / "04-raumplanung.png")
    finally:
        context.close()


def main() -> None:
    base_url = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/") + "/"
    username = os.environ.get("KAYI_SCREENSHOT_USER", "demo")
    User = get_user_model()
    user = User.objects.select_related("profile").filter(username=username).first()
    if user is None:
        raise RuntimeError(f"Screenshot user {username!r} does not exist; run seed_demo_data first")
    profile = getattr(user, "profile", None)
    if profile is None:
        raise RuntimeError("Screenshot user has no profile")

    old_password = user.password
    old_role = profile.role
    old_mobile = profile.is_mobile_worker
    temporary_password = secrets.token_urlsafe(28)
    user.set_password(temporary_password)
    user.save(update_fields=["password"])
    profile.role = UserProfile.Role.OFFICE
    profile.is_mobile_worker = False
    profile.save(update_fields=["role", "is_mobile_worker", "updated_at"])

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                # Apple 6.9-inch accepted size: 430x932 CSS points at 3x = 1290x2796.
                capture_set(browser, base_url, username, temporary_password, OUTPUT / "apple-6.9", 430, 932, 3)
                # Google portrait recommendation: 360x640 at 3x = 1080x1920.
                capture_set(browser, base_url, username, temporary_password, OUTPUT / "google-phone", 360, 640, 3)
            finally:
                browser.close()
    finally:
        user.password = old_password
        user.save(update_fields=["password"])
        profile.role = old_role
        profile.is_mobile_worker = old_mobile
        profile.save(update_fields=["role", "is_mobile_worker", "updated_at"])

    for path in sorted(OUTPUT.rglob("*.png")):
        with Image.open(path) as im:
            print(f"{path.relative_to(ROOT)}: {im.size[0]}x{im.size[1]} RGB={im.mode == 'RGB'}")


if __name__ == "__main__":
    main()
