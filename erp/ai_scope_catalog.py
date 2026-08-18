"""Compatibility alias for legacy owner-pricing installers.

The current runtime uses erp.ai_scope_planner. Older PR106 assembly code still
expects erp.ai_scope_catalog to exist while applying tenant-owned pricing hooks.
Keep this thin alias so the installer can run without reintroducing a second
scope implementation.
"""
from .ai_scope_planner import *  # noqa: F401,F403
