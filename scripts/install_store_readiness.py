from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "store_overlay"


def copy_tree(source: Path, target: Path) -> None:
    if not source.exists():
        return
    target.mkdir(parents=True, exist_ok=True)
    for item in source.rglob("*"):
        if item.is_dir():
            continue
        destination = target / item.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, destination)


def patch_urls() -> None:
    path = ROOT / "erp" / "urls.py"
    text = path.read_text(encoding="utf-8")
    if 'include("erp.store_urls")' in text or "include('erp.store_urls')" in text:
        return
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("from django.urls import "):
            names = [part.strip() for part in line.split("import", 1)[1].split(",")]
            if "include" not in names:
                names.append("include")
            lines[index] = "from django.urls import " + ", ".join(names)
            text = "\n".join(lines) + "\n"
            break
    marker = "urlpatterns = ["
    if marker not in text:
        raise RuntimeError("Store readiness could not locate erp urlpatterns")
    text = text.replace(marker, marker + '\n    path("", include("erp.store_urls")),', 1)
    path.write_text(text, encoding="utf-8")


def patch_user_ai_guards() -> None:
    path = ROOT / "erp" / "rebuild_views.py"
    text = path.read_text(encoding="utf-8")
    needle = '''    get_object_or_404(m.CalendarEvent, pk=pk, organization=org)\n    raw = (request.POST.get("text") or "").strip()\n'''
    replacement = '''    get_object_or_404(m.CalendarEvent, pk=pk, organization=org)\n    from erp.store_views import has_ai_consent\n    if not has_ai_consent(request.user):\n        return JsonResponse({"ok": False, "error": "Vor der KI-Verarbeitung ist deine ausdrückliche Einwilligung in den Einstellungen erforderlich.", "consent_required": True, "settings_url": "/settings/next/"}, status=428)\n    raw = (request.POST.get("text") or "").strip()\n'''
    if needle in text and "consent_required" not in text[text.find("def ai_structure_report"):text.find("def quote_list")]:
        text = text.replace(needle, replacement, 1)
    path.write_text(text, encoding="utf-8")

    path = ROOT / "erp" / "api.py"
    text = path.read_text(encoding="utf-8")
    photo_needle = "            result = analyze_room_photos(organization_for(request.user), images, calibration)"
    if photo_needle in text and "KAYI_STORE_AI_PHOTO_CONSENT" not in text:
        photo_replacement = '''            # KAYI_STORE_AI_PHOTO_CONSENT\n            from erp.store_views import has_ai_consent\n            if not has_ai_consent(request.user):\n                return Response({"detail": "Vor der KI-Fotoanalyse ist deine ausdrückliche Einwilligung in den Einstellungen erforderlich.", "consent_required": True, "settings_url": "/settings/next/"}, status=428)\n            result = analyze_room_photos(organization_for(request.user), images, calibration)'''
        text = text.replace(photo_needle, photo_replacement, 1)
    chat_needle = "            output, usage = chat(org, history, context)"
    if chat_needle in text and "KAYI_STORE_AI_CHAT_CONSENT" not in text:
        chat_replacement = '''            # KAYI_STORE_AI_CHAT_CONSENT\n            from erp.store_views import has_ai_consent\n            if not has_ai_consent(request.user):\n                return Response({"detail": "Vor der KI-Verarbeitung ist deine ausdrückliche Einwilligung in den Einstellungen erforderlich.", "consent_required": True, "settings_url": "/settings/next/"}, status=428)\n            output, usage = chat(org, history, context)'''
        text = text.replace(chat_needle, chat_replacement, 1)

    privacy_line = '            "privacy_url": request.build_absolute_uri("/privacy/"),'
    if privacy_line in text and '"account_deletion_url"' not in text:
        text = text.replace(
            privacy_line,
            '            "privacy_url": request.build_absolute_uri("/datenschutz/"),\n            "support_url": request.build_absolute_uri("/support/"),\n            "account_deletion_url": request.build_absolute_uri("/konto-loeschen/"),',
            1,
        )
    path.write_text(text, encoding="utf-8")

    room_path = ROOT / "erp" / "room_planner_views.py"
    if room_path.exists():
        text = room_path.read_text(encoding="utf-8")
        if "KAYI_STORE_ROOM_AI_CONSENT" not in text:
            pattern = re.compile(r"(?P<indent>^[ \t]*)result = analyze_room_photos\((?P<args>[^\n]+)\)", re.M)
            match = pattern.search(text)
            if match:
                indent = match.group("indent")
                guarded = (
                    f"{indent}# KAYI_STORE_ROOM_AI_CONSENT\n"
                    f"{indent}from erp.store_views import has_ai_consent\n"
                    f"{indent}from django.http import JsonResponse as _StoreJsonResponse\n"
                    f"{indent}if not has_ai_consent(request.user):\n"
                    f"{indent}    return _StoreJsonResponse({{'ok': False, 'error': 'Vor der KI-Fotoanalyse ist deine ausdrückliche Einwilligung in den Einstellungen erforderlich.', 'consent_required': True, 'settings_url': '/settings/next/'}}, status=428)\n"
                    f"{indent}result = analyze_room_photos({match.group('args')})"
                )
                text = text[:match.start()] + guarded + text[match.end():]
                room_path.write_text(text, encoding="utf-8")


def patch_privacy_ui() -> None:
    path = ROOT / "erp" / "views.py"
    if path.exists():
        text = path.read_text(encoding="utf-8")
        text = text.replace('return render(request, "erp/privacy.html")', 'return render(request, "store/privacy.html", {"ai_consent_version": "2026-08-10"})')
        path.write_text(text, encoding="utf-8")

    room_template = ROOT / "templates" / "rebuild" / "room_planner.html"
    if room_template.exists():
        text = room_template.read_text(encoding="utf-8")
        marker = '<div class="rp-vision-feedback" data-rp-vision-feedback hidden></div>'
        if marker in text and "KI-Datenschutzhinweis" not in text:
            disclosure = '''<div class="nx-card nx-card-pad" style="margin-top:12px"><b>KI-Datenschutzhinweis</b><small>Für die Fotoanalyse werden nur die von dir ausgewählten Bilder an OpenAI übertragen. Vor der ersten Übertragung ist eine ausdrückliche Einwilligung in den <a href="/settings/next/">Einstellungen</a> erforderlich; sie kann dort jederzeit widerrufen werden.</small></div>'''
            text = text.replace(marker, disclosure + marker, 1)
            room_template.write_text(text, encoding="utf-8")


def patch_android_scanner_compatibility() -> None:
    path = ROOT / "native" / "plugins" / "kayi-room-scanner" / "android" / "src" / "main" / "java" / "de" / "kayihaustechnik" / "scanner" / "ArCoreRoomScanActivity.java"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")

    # java.time.Instant and java.nio.file Files/toPath are API 26. KAYI keeps
    # Android 7/API 24 support, so use only java.io APIs available on minSdk 24.
    text = text.replace(
        "Instant.now().toString()",
        'new java.text.SimpleDateFormat("yyyy-MM-dd\'T\'HH:mm:ss.SSSZ", java.util.Locale.US).format(new java.util.Date())',
    )
    text = text.replace("import java.time.Instant;\n", "")
    text = text.replace("import java.time.Instant;\r\n", "")

    if "import java.io.FileOutputStream;" not in text:
        text = text.replace("import java.io.File;\n", "import java.io.File;\nimport java.io.FileOutputStream;\n", 1)

    # Rewrite every fully-qualified NIO write, independent of variable names or
    # formatting. Turning Files.write(file.toPath(), bytes) into writeBytes(file,
    # bytes) avoids all API 26 Files/Path calls while preserving exact payloads.
    text = text.replace("java.nio.file.Files.write(", "writeBytes(")
    text = text.replace(".toPath(),", ",")

    helper = '''    private static void writeBytes(File file, byte[] value) throws Exception {\n        try (FileOutputStream stream = new FileOutputStream(file)) {\n            stream.write(value);\n            stream.flush();\n        }\n    }\n\n'''
    if "private static void writeBytes(" not in text:
        marker = "    private void writePayload() throws Exception {\n"
        if marker not in text:
            raise RuntimeError("Could not locate Android scanner writePayload method for API24 compatibility patch")
        text = text.replace(marker, helper + marker, 1)

    path.write_text(text, encoding="utf-8")


def guard() -> None:
    required = [
        ROOT / "erp" / "store_views.py",
        ROOT / "erp" / "store_urls.py",
        ROOT / "templates" / "store" / "privacy.html",
        ROOT / "templates" / "store" / "support.html",
        ROOT / "templates" / "store" / "account_deletion.html",
        ROOT / "templates" / "rebuild" / "settings.html",
        ROOT / "tests" / "test_store_readiness.py",
    ]
    missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
    if missing:
        raise RuntimeError(f"Store readiness installation incomplete: {missing}")
    urls = (ROOT / "erp" / "urls.py").read_text(encoding="utf-8")
    if 'include("erp.store_urls")' not in urls:
        raise RuntimeError("Store public routes are not installed")
    api = (ROOT / "erp" / "api.py").read_text(encoding="utf-8")
    for marker in ("KAYI_STORE_AI_PHOTO_CONSENT", "KAYI_STORE_AI_CHAT_CONSENT", '"account_deletion_url"'):
        if marker not in api:
            raise RuntimeError(f"Store mobile/API contract missing: {marker}")
    room_path = ROOT / "erp" / "room_planner_views.py"
    if room_path.exists() and "analyze_room_photos" in room_path.read_text(encoding="utf-8") and "KAYI_STORE_ROOM_AI_CONSENT" not in room_path.read_text(encoding="utf-8"):
        raise RuntimeError("Room Planner photo AI is not protected by explicit consent")
    scanner = ROOT / "native" / "plugins" / "kayi-room-scanner" / "android" / "src" / "main" / "java" / "de" / "kayihaustechnik" / "scanner" / "ArCoreRoomScanActivity.java"
    if scanner.exists():
        scanner_text = scanner.read_text(encoding="utf-8")
        forbidden = ("Instant.now()", "java.time.Instant", "java.nio.file.Files", ".toPath()")
        remaining = [item for item in forbidden if item in scanner_text]
        if remaining:
            raise RuntimeError(f"Android scanner still uses API26-only file/time calls despite minSdk 24: {remaining}")
        if "private static void writeBytes(" not in scanner_text:
            raise RuntimeError("Android scanner API24-compatible byte writer was not installed")


copy_tree(OVERLAY / "erp", ROOT / "erp")
copy_tree(OVERLAY / "templates", ROOT / "templates")
copy_tree(OVERLAY / "tests", ROOT / "tests")
patch_urls()
patch_user_ai_guards()
patch_privacy_ui()
patch_android_scanner_compatibility()
guard()
print("KAYI store readiness layer installed: public privacy/support/deletion, explicit AI consent, native store URLs and Android 7-compatible room scanner I/O.")
