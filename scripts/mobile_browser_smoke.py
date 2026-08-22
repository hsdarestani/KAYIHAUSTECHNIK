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
from mobile_browser_smoke_v2 import main

if __name__ == "__main__":
    main()
