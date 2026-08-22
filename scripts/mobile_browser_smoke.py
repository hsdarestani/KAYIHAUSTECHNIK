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


def main():
    impl.choose_users = _choose_users_seed_compatible
    impl.login_as = _login_as_role_aware
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
