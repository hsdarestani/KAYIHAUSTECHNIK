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

    # java.time.Instant and java.nio.file APIs are API 26. KAYI keeps
    # Android 7/API 24 support, so use only java.io APIs available on minSdk 24.
    text = text.replace(
        "Instant.now().toString()",
        'new java.text.SimpleDateFormat("yyyy-MM-dd\'T\'HH:mm:ss.SSSZ", java.util.Locale.US).format(new java.util.Date())',
    )
    for old_import in (
        "import java.time.Instant;\n",
        "import java.time.Instant;\r\n",
        "import java.nio.file.Files;\n",
        "import java.nio.file.Files;\r\n",
        "import java.nio.file.Path;\n",
        "import java.nio.file.Path;\r\n",
        "import java.nio.file.StandardOpenOption;\n",
        "import java.nio.file.StandardOpenOption;\r\n",
    ):
        text = text.replace(old_import, "")
    text = re.sub(r"(?m)^[ \t]*import\s+java\.nio\.file\.[^;]+;[ \t]*\r?\n?", "", text)

    if "import java.io.FileOutputStream;" not in text:
        text = text.replace("import java.io.File;\n", "import java.io.File;\nimport java.io.FileOutputStream;\n", 1)

    text = text.replace("java.nio.file.Files.write(", "writeBytes(")
    text = text.replace("Files.write(", "writeBytes(")
    text = text.replace(".toPath(),", ",")

    # Generated scanner helpers still use Path/readAllBytes on some source
    # payloads. Convert those helper contracts to File as well.
    text = text.replace(
        "static void writeString(java.nio.file.Path path, String value) throws java.io.IOException {",
        "static void writeString(File file, String value) throws java.io.IOException {",
    )
    text = text.replace("writeBytes(path,", "writeBytes(file,")
    text = text.replace(
        "static String readString(java.nio.file.Path path) throws java.io.IOException {",
        "static String readString(File file) throws java.io.IOException {",
    )
    text = text.replace("java.nio.file.Files.readAllBytes(path)", "readBytes(file)")

    helper = '''\n    private static void writeBytes(File file, byte[] value) throws Exception {\n        try (FileOutputStream stream = new FileOutputStream(file)) {\n            stream.write(value);\n            stream.flush();\n        }\n    }\n\n    private static byte[] readBytes(File file) throws java.io.IOException {\n        try (java.io.FileInputStream input = new java.io.FileInputStream(file);\n             java.io.ByteArrayOutputStream output = new java.io.ByteArrayOutputStream()) {\n            byte[] buffer = new byte[8192];\n            int count;\n            while ((count = input.read(buffer)) != -1) {\n                output.write(buffer, 0, count);\n            }\n            return output.toByteArray();\n        }\n    }\n'''
    if "private static void writeBytes(" not in text:
        class_match = re.search(r"public\s+class\s+ArCoreRoomScanActivity[^\{]*\{", text)
        if not class_match:
            raise RuntimeError("Could not locate Android scanner class declaration for API24 compatibility patch")
        text = text[: class_match.end()] + helper + text[class_match.end() :]
    elif "private static byte[] readBytes(" not in text:
        class_match = re.search(r"public\s+class\s+ArCoreRoomScanActivity[^\{]*\{", text)
        if not class_match:
            raise RuntimeError("Could not locate Android scanner class declaration for API24 compatibility read helper")
        read_helper = '''\n    private static byte[] readBytes(File file) throws java.io.IOException {\n        try (java.io.FileInputStream input = new java.io.FileInputStream(file);\n             java.io.ByteArrayOutputStream output = new java.io.ByteArrayOutputStream()) {\n            byte[] buffer = new byte[8192];\n            int count;\n            while ((count = input.read(buffer)) != -1) {\n                output.write(buffer, 0, count);\n            }\n            return output.toByteArray();\n        }\n    }\n'''
        text = text[: class_match.end()] + read_helper + text[class_match.end() :]

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
        forbidden = ("Instant.now()", "java.time.Instant", "java.nio.file.", "Files.write(", ".toPath()")
        remaining = [item for item in forbidden if item in scanner_text]
        if remaining:
            offenders = [
                f"{number}: {line.strip()}"
                for number, line in enumerate(scanner_text.splitlines(), start=1)
                if any(item in line for item in remaining)
            ]
            raise RuntimeError(
                f"Android scanner still uses API26-only file/time calls despite minSdk 24: {remaining}; lines={offenders}"
            )
        if "private static void writeBytes(" not in scanner_text or "private static byte[] readBytes(" not in scanner_text:
            raise RuntimeError("Android scanner API24-compatible byte readers/writers were not installed")


copy_tree(OVERLAY / "erp", ROOT / "erp")
copy_tree(OVERLAY / "templates", ROOT / "templates")
copy_tree(OVERLAY / "tests", ROOT / "tests")
patch_urls()
patch_user_ai_guards()
patch_privacy_ui()
patch_android_scanner_compatibility()
guard()
print("KAYI store readiness layer installed: public privacy/support/deletion, explicit AI consent, native store URLs and Android 7-compatible room scanner I/O.")