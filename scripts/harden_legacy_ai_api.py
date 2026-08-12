from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A_BAU_LEGACY_AI_ADMIN_GUARD 2026-08-12"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Legacy KI hardening target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.write_text(text, encoding="utf-8")


def patch_fail_closed_global_paths() -> None:
    rel = "erp/ai_role_permissions.py"
    text = read(rel)
    old = '''def assistant_path_allowed(user, organization, path: str) -> bool:
    route = route_for_path(path)
    if not route or route in allowed_navigation_routes(user):
        return True
'''
    new = '''def assistant_path_allowed(user, organization, path: str) -> bool:
    route = route_for_path(path)
    # Unknown/legacy pages are fail-closed for non-admins. Office may still use
    # the generic assistant on known office pages only; unrestricted fallback is
    # deliberately reserved for Admin because we cannot prove record scope on an
    # unrecognized route.
    if not route:
        return role_for(user) == ADMIN
    if route in allowed_navigation_routes(user):
        return True
'''
    if new not in text:
        if old not in text:
            raise RuntimeError("Global KI path-scope anchor changed")
        text = text.replace(old, new, 1)
    write(rel, text)


def _guard_before_call(text: str, call_pattern: str, label: str) -> tuple[str, int]:
    pattern = re.compile(rf"(?m)^(?P<indent>[ \t]*)(?P<call>{call_pattern})$")

    def replacement(match: re.Match[str]) -> str:
        indent = match.group("indent")
        call = match.group("call")
        guard = (
            f"{indent}# {MARKER} · {label}\n"
            f"{indent}from . import ai_role_permissions as _ai_perm\n"
            f"{indent}from django.http import JsonResponse as _AIRoleJsonResponse\n"
            f"{indent}if _ai_perm.role_for(request.user) != _ai_perm.ADMIN:\n"
            f"{indent}    return _AIRoleJsonResponse({{\"detail\": \"Dieser alte KI-Endpunkt ist nur für Administratoren freigeschaltet. Bitte die rollenbasierte KAYI KI verwenden.\"}}, status=403)\n"
            f"{indent}{call}"
        )
        return guard

    return pattern.subn(replacement, text, count=1)


def patch_legacy_api() -> None:
    rel = "erp/api.py"
    text = read(rel)
    if MARKER in text:
        return

    # Legacy generic chat accepts arbitrary context/history and predates KAYI's
    # record-level RBAC. It is intentionally admin-only instead of trying to infer
    # scope from an untrusted generic payload.
    text, chat_count = _guard_before_call(
        text,
        r"output,\s*usage\s*=\s*chat\(org,\s*history,\s*context\)",
        "generic chat",
    )
    if chat_count != 1:
        raise RuntimeError(f"Could not harden legacy AI chat call (matches={chat_count})")

    # The old photo analyzer is not project-bound at the endpoint boundary. Keep
    # it admin-only; technicians/project managers must use the scoped Room/3D KI
    # where project assignment is verified server-side.
    text, photo_count = _guard_before_call(
        text,
        r"result\s*=\s*analyze_room_photos\(organization_for\(request\.user\),\s*images,\s*calibration\)",
        "photo measurement",
    )
    if photo_count != 1:
        raise RuntimeError(f"Could not harden legacy AI photo analyzer (matches={photo_count})")

    write(rel, text)


def install_tests() -> None:
    test = r'''from pathlib import Path

from django.test import SimpleTestCase


class LegacyAIRoleGuardContractTests(SimpleTestCase):
    def test_legacy_ai_provider_calls_are_admin_guarded(self):
        source = Path("erp/api.py").read_text(encoding="utf-8")
        marker = "A_BAU_LEGACY_AI_ADMIN_GUARD 2026-08-12"
        self.assertGreaterEqual(source.count(marker), 2)
        self.assertIn("role_for(request.user) != _ai_perm.ADMIN", source)

        chat_guard = source.rfind(marker, 0, source.index("output, usage = chat(org, history, context)"))
        self.assertGreaterEqual(chat_guard, 0)
        self.assertLess(source.index("role_for(request.user) != _ai_perm.ADMIN", chat_guard), source.index("output, usage = chat(org, history, context)"))

        photo_call = "result = analyze_room_photos(organization_for(request.user), images, calibration)"
        photo_guard = source.rfind(marker, 0, source.index(photo_call))
        self.assertGreaterEqual(photo_guard, 0)
        self.assertLess(source.index("role_for(request.user) != _ai_perm.ADMIN", photo_guard), source.index(photo_call))

    def test_unknown_global_assistant_paths_fail_closed(self):
        permissions = Path("erp/ai_role_permissions.py").read_text(encoding="utf-8")
        self.assertIn("if not route:", permissions)
        self.assertIn("return role_for(user) == ADMIN", permissions)
        self.assertNotIn("if not route or route in allowed_navigation_routes(user):", permissions)
'''
    write("tests/test_legacy_ai_role_guard.py", test)


def guard() -> None:
    api = read("erp/api.py")
    permissions = read("erp/ai_role_permissions.py")
    tests = read("tests/test_legacy_ai_role_guard.py")
    required_api = [
        MARKER,
        "output, usage = chat(org, history, context)",
        "result = analyze_room_photos(organization_for(request.user), images, calibration)",
        "role_for(request.user) != _ai_perm.ADMIN",
    ]
    missing = [marker for marker in required_api if marker not in api]
    if "return role_for(user) == ADMIN" not in permissions:
        missing.append("ai_role_permissions.py: unknown path fail-closed")
    if "test_legacy_ai_provider_calls_are_admin_guarded" not in tests:
        missing.append("tests: legacy KI guard")
    if missing:
        raise RuntimeError("Legacy KI role guard failed: " + "; ".join(missing))


patch_fail_closed_global_paths()
patch_legacy_api()
install_tests()
guard()
print("A+Bau legacy KI APIs are admin-only; unknown global KI routes now fail closed for non-admins.")
