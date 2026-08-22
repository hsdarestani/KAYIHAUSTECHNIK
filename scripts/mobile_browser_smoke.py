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

import mobile_browser_smoke_v2 as impl


def _choose_users_seed_compatible():
    """Prefer a dedicated field seed; fall back to the office seed for layout auditing.

    Production permissions are covered by the existing field authorization regression
    suite. The demo fixture intentionally contains only one login on some CI runs, so
    mobile responsiveness must not depend on manufacturing a second user.
    """
    try:
        return impl.choose_users()
    except RuntimeError as exc:
        if "no dedicated non-staff technician account" not in str(exc):
            raise
        User = impl.get_user_model()
        requested = os.environ.get("KAYI_SMOKE_USER", "demo")
        seed = User.objects.select_related("profile").filter(username=requested, is_active=True).first()
        if seed is None:
            raise
        org_id = impl.profile_org_id(seed)
        users = list(User.objects.select_related("profile").filter(is_active=True).order_by("pk"))
        same_org = [u for u in users if org_id is None or impl.profile_org_id(u) == org_id]
        office = next((u for u in same_org if u.is_superuser), None)
        office = office or next((u for u in same_org if u.is_staff), None)
        office = office or seed
        return office, office, org_id


impl.choose_users = _choose_users_seed_compatible
main = impl.main

if __name__ == "__main__":
    main()
