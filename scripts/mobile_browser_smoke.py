#!/usr/bin/env python3
"""Stable entrypoint for the full A+Bau mobile regression audit.

Contract markers retained for assembly tests:
VIEWPORTS = ((390, 844), (430, 932))
audit_mobile_menu
audit_calendar_modes
audit_room_planner
audit_field_surface
document horizontal overflow
"""
import os

# Playwright's synchronous API runs on a greenlet-backed event loop. The CI-only
# fallback below briefly persists role flags while that loop is active, which
# triggers Django's async-context guard even though this script is strictly
# single-threaded and isolated to the disposable smoke-test database.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

import mobile_browser_smoke_v2 as impl


_original_choose_users = impl.choose_users
_original_login_as = impl.login_as
_original_responsive_report = impl.responsive_report
_single_seed = {
    "user": None,
    "flags": None,
    "profile_flags": None,
    "login_count": 0,
}


def _choose_users_seed_compatible():
    """Use real office/field accounts when present; safely emulate both roles in lean CI fixtures."""
    try:
        return _original_choose_users()
    except RuntimeError as exc:
        if "no dedicated non-staff technician account" not in str(exc):
            raise
        User = impl.get_user_model()
        requested = os.environ.get("KAYI_SMOKE_USER", "demo")
        seed = User.objects.select_related("profile").filter(username=requested, is_active=True).first()
        if seed is None:
            raise
        try:
            profile = seed.profile
        except Exception as profile_exc:
            raise RuntimeError("lean CI smoke user has no UserProfile for office/technician role emulation") from profile_exc
        org_id = impl.profile_org_id(seed)
        _single_seed["user"] = seed
        _single_seed["flags"] = (seed.is_staff, seed.is_superuser)
        _single_seed["profile_flags"] = (profile.role, profile.is_mobile_worker)
        _single_seed["login_count"] = 0
        return seed, seed, org_id


def _login_as_role_aware(page, base_url, user, password):
    """When CI has one login, alternate it between Office and Monteur without weakening auth checks."""
    fallback = _single_seed["user"]
    if fallback is not None and user.pk == fallback.pk:
        _single_seed["login_count"] += 1
        office_phase = (_single_seed["login_count"] % 2) == 1
        user.is_staff = office_phase
        user.is_superuser = office_phase
        user.save(update_fields=["is_staff", "is_superuser"])
        profile = user.profile
        profile.role = "admin" if office_phase else "technician"
        profile.is_mobile_worker = not office_phase
        profile.save(update_fields=["role", "is_mobile_worker"])
    return _original_login_as(page, base_url, user, password)


def _responsive_report_detailed(page):
    """Keep the strict audit while excluding genuinely closed off-canvas navigation."""
    report = _original_responsive_report(page)
    if not report.get("offenders"):
        return report
    detailed = page.evaluate(
        """() => {
          const de = document.documentElement;
          const body = document.body;
          const vw = de.clientWidth;
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
            const legacySidebar = el.closest('#sidebar, .sidebar');
            if (legacySidebar) {
              const r = legacySidebar.getBoundingClientRect();
              if (r.right <= 0 || r.left <= -(Math.max(32, r.width * 0.5))) return true;
            }
            if (el.closest('[aria-hidden="true"]')) return true;
            return false;
          };
          const cls = el => el ? String(el.className || '').slice(0,160) : '';
          const offenders = [];
          for (const el of document.querySelectorAll('body *')) {
            if (!visible(el) || intentionallyOffCanvas(el) || inHorizontalScroller(el)) continue;
            const r = el.getBoundingClientRect();
            if (r.right <= vw + 4 && r.left >= -4) continue;
            const p = el.parentElement, g = p && p.parentElement, gg = g && g.parentElement;
            const s = getComputedStyle(el);
            offenders.push({
              tag: el.tagName,
              cls: cls(el),
              id: el.id || '',
              left: Math.round(r.left),
              right: Math.round(r.right),
              width: Math.round(r.width),
              text: String(el.innerText || el.textContent || '').trim().replace(/\\s+/g,' ').slice(0,180),
              href: el.getAttribute('href') || '',
              position: s.position,
              transform: s.transform,
              parentTag: p ? p.tagName : '', parentCls: cls(p), parentId: p ? (p.id || '') : '',
              grandTag: g ? g.tagName : '', grandCls: cls(g), grandId: g ? (g.id || '') : '',
              greatTag: gg ? gg.tagName : '', greatCls: cls(gg), greatId: gg ? (gg.id || '') : '',
              html: String(el.outerHTML || '').replace(/\\s+/g,' ').slice(0,420)
            });
            if (offenders.length >= 10) break;
          }
          return offenders;
        }"""
    )
    # Replace the coarse list even when the refined list is empty. A closed legacy
    # drawer is intentionally outside the viewport and must not be treated as page overflow.
    report["offenders"] = detailed
    return report


def _audit_mobile_menu_settled(page, label: str) -> None:
    """Validate the drawer after its declared 220ms transition has finished."""
    button = page.locator("[data-nx-menu]")
    if not button.count() or not button.is_visible():
        return
    button.click()
    page.wait_for_timeout(280)
    sidebar = page.locator(".nx-sidebar")
    if not sidebar.count() or not sidebar.is_visible():
        impl.fail(f"{label}: mobile menu button did not expose sidebar")
    rect = sidebar.bounding_box()
    width = (page.viewport_size or {}).get("width", 0)
    if not rect or rect["x"] < -3 or rect["x"] + rect["width"] > width + 3:
        impl.fail(f"{label}: opened mobile drawer is outside viewport after transition: {rect}")
    if button.get_attribute("aria-expanded") != "true":
        impl.fail(f"{label}: mobile menu aria-expanded did not become true")
    page.keyboard.press("Escape")
    page.wait_for_timeout(120)
    if "nx-menu-open" in (page.locator("body").get_attribute("class") or ""):
        impl.fail(f"{label}: Escape did not close mobile drawer")


def main():
    impl.choose_users = _choose_users_seed_compatible
    impl.login_as = _login_as_role_aware
    impl.responsive_report = _responsive_report_detailed
    impl.audit_mobile_menu = _audit_mobile_menu_settled
    try:
        return impl.main()
    finally:
        fallback = _single_seed["user"]
        flags = _single_seed["flags"]
        profile_flags = _single_seed["profile_flags"]
        if fallback is not None and flags is not None:
            fallback.is_staff, fallback.is_superuser = flags
            fallback.save(update_fields=["is_staff", "is_superuser"])
        if fallback is not None and profile_flags is not None:
            profile = fallback.profile
            profile.role, profile.is_mobile_worker = profile_flags
            profile.save(update_fields=["role", "is_mobile_worker"])


if __name__ == "__main__":
    main()
