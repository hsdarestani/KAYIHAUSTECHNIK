from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "overlays" / "customer_3d_polish"
VERSION = "20260810-7"
MARKER = "KAYI customer/3D polish 20260810"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Missing customer/3D polish target: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def append_once(rel: str, addition_path: str, marker: str) -> None:
    text = read(rel)
    if marker in text:
        return
    addition = (OVERLAY / addition_path).read_text(encoding="utf-8")
    write(rel, text.rstrip() + "\n\n" + addition.strip() + "\n")


def install_customer_form() -> None:
    source = OVERLAY / "templates" / "rebuild" / "customer_form.html"
    target = ROOT / "templates" / "rebuild" / "customer_form.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    append_once("static/css/kayi-next.css", "static/css/customer-form-polish.css", "KAYI customer form progressive disclosure 20260810")


def install_room_ai_service() -> None:
    source = OVERLAY / "erp" / "services" / "room_ai.py"
    target = ROOT / "erp" / "services" / "room_ai.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)

    views_path = "erp/room_planner_views.py"
    views = read(views_path)
    if "from django.views.decorators.cache import never_cache" not in views:
        views = views.replace(
            "from django.views.decorators.http import require_POST\n",
            "from django.views.decorators.cache import never_cache\nfrom django.views.decorators.csrf import ensure_csrf_cookie\nfrom django.views.decorators.http import require_POST\n",
            1,
        )
    if "from .services.room_ai import adjust_room_scene" not in views:
        views = views.replace(
            "from .services.permissions import can_write\n",
            "from .services.permissions import can_write\nfrom .services.room_ai import adjust_room_scene\n",
            1,
        )
    old_decorator = "@login_required\ndef room_planner(request, project_pk):"
    new_decorator = "@login_required\n@ensure_csrf_cookie\n@never_cache\ndef room_planner(request, project_pk):"
    if new_decorator not in views:
        if old_decorator not in views:
            raise RuntimeError("Room planner GET decorator contract changed")
        views = views.replace(old_decorator, new_decorator, 1)

    ai_view = '''\n\n@login_required\n@require_POST\ndef room_planner_ai(request, project_pk):\n    if not can_write(request.user):\n        raise PermissionDenied("Keine Schreibberechtigung.")\n    org, project = _project(request, project_pk)\n    try:\n        payload = json.loads(request.body.decode("utf-8"))\n    except (UnicodeDecodeError, json.JSONDecodeError):\n        return JsonResponse({"error": "Ungültige JSON-Daten."}, status=400)\n    command = str(payload.get("command") or "").strip()\n    if not command:\n        return JsonResponse({"error": "Bitte beschreibe, was die KI im Raum ändern soll."}, status=400)\n    measurement = _measurement_for(project, org, payload.get("measurement_id")) if payload.get("measurement_id") else None\n    current_state, _ = _state_for(measurement)\n    posted_state = payload.get("state")\n    if isinstance(posted_state, dict) and posted_state.get("room"):\n        try:\n            current_state = normalize_room_state(posted_state, measurement, getattr(measurement, "native_scan", None) if measurement else None)\n        except ValidationError:\n            return JsonResponse({"error": "Der aktuelle 3D-Raum enthält ungültige Geometriedaten."}, status=400)\n    try:\n        result = adjust_room_scene(org, command, current_state, measurement=measurement)\n    except ValueError as exc:\n        return JsonResponse({"error": str(exc)}, status=400)\n    except Exception:\n        logger.exception("KAYI Room Planner KI command failed")\n        return JsonResponse({"error": "Der KI-Raumassistent ist momentan nicht erreichbar. Bitte erneut versuchen."}, status=502)\n    return JsonResponse({\n        "state": result["state"],\n        "summary": result.get("summary") or "KI-Vorschlag erstellt.",\n        "warnings": result.get("warnings") or [],\n    })\n'''
    if "def room_planner_ai(" not in views:
        anchor = "\n\n@login_required\n@require_POST\ndef room_planner_vision(request, project_pk):"
        if anchor not in views:
            raise RuntimeError("Room planner vision view anchor changed")
        views = views.replace(anchor, ai_view + anchor, 1)
    write(views_path, views)

    urls_path = "erp/room_planner_urls.py"
    urls = read(urls_path)
    route = '    path("projects/<int:project_pk>/room-planner/ki/", views.room_planner_ai, name="next-room-planner-ai"),\n'
    if route not in urls:
        anchor = '    path("projects/<int:project_pk>/room-planner/vision/", views.room_planner_vision, name="next-room-planner-vision"),\n'
        if anchor not in urls:
            raise RuntimeError("Room planner URL contract changed")
        urls = urls.replace(anchor, anchor + route, 1)
    write(urls_path, urls)


def patch_room_template() -> None:
    path = "templates/rebuild/room_planner.html"
    text = read(path)
    if 'data-ai-url="{% url \'next-room-planner-ai\' project.pk %}"' not in text:
        anchor = '     data-vision-url="{% url \'next-room-planner-vision\' project.pk %}"\n'
        if anchor not in text:
            raise RuntimeError("Room planner root URL contract changed")
        text = text.replace(anchor, anchor + '     data-ai-url="{% url \'next-room-planner-ai\' project.pk %}"\n', 1)
    if "data-rp-csrf" not in text:
        anchor = '     data-readonly="{% if readonly %}1{% else %}0{% endif %}">\n'
        if anchor not in text:
            raise RuntimeError("Room planner root close contract changed")
        text = text.replace(anchor, anchor + '  <div hidden data-rp-csrf>{% csrf_token %}</div>\n', 1)

    ki_card = '''      <section class="rp-ki-card" data-rp-ki-card>\n        <div class="rp-ki-head"><span class="rp-ki-mark">✦</span><div><b>KI-Raumassistent</b><small>Änderungen direkt im aktuellen 3D-Raum beschreiben. Die KI erstellt zuerst einen prüfbaren Entwurf.</small></div></div>\n        <textarea data-rp-ai-command placeholder="z. B. Stelle das WC an die rechte Wand und das Waschbecken links neben die Tür."></textarea>\n        <div class="rp-ki-examples">\n          <button type="button" data-rp-ai-example="Stelle das WC an die rechte Wand und das Waschbecken links neben die Tür.">WC & Waschbecken</button>\n          <button type="button" data-rp-ai-example="Ordne die Sanitärobjekte sinnvoll an den vorhandenen Wänden an und vermeide Überschneidungen.">Sanitär anordnen</button>\n          <button type="button" data-rp-ai-example="Richte alle Objekte sauber am 5-cm-Raster und an den nächsten Wänden aus.">Sauber ausrichten</button>\n        </div>\n        <button type="button" class="nx-btn nx-btn-primary rp-ki-run" data-rp-run-ai>✦ KI-Vorschlag anwenden</button>\n        <div class="rp-ki-feedback" data-rp-ai-feedback hidden></div>\n      </section>\n'''
    if "data-rp-ki-card" not in text:
        anchor = '      <div class="rp-inspector-empty" data-rp-inspector-empty>\n'
        if anchor not in text:
            raise RuntimeError("Room planner inspector anchor changed")
        text = text.replace(anchor, ki_card + anchor, 1)

    text = text.replace("AI setzt", "KI setzt").replace("AI Objekte", "KI Objekte").replace("AI-Fotoerkennung", "KI-Fotoerkennung")
    text = re.sub(r"\bAI\b", "KI", text)
    text = re.sub(r"(room-planner\.(?:css|js)' %\}\?v=)[^\"']+", rf"\g<1>{VERSION}", text)
    write(path, text)


def patch_room_assets() -> None:
    css_marker = "KAYI customer/3D polish 20260810"
    append_once("static/css/room-planner.css", "static/css/room-planner-polish.css", css_marker)

    js_path = "static/js/room-planner.js"
    js = read(js_path)
    js = js.replace("const KAYI_ROOM_PLANNER_PRO = '2026.08.10.1';", "const KAYI_ROOM_PLANNER_PRO = '2026.08.10.7';")
    js = js.replace("AI-Erkennung", "KI-Erkennung").replace("AI-Entwurf", "KI-Entwurf")

    save_old = "fetch(root.dataset.saveUrl,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},body:"
    save_new = "fetch(root.dataset.saveUrl,{method:'POST',credentials:'same-origin',headers:{'Accept':'application/json','X-Requested-With':'XMLHttpRequest','Content-Type':'application/json','X-CSRFToken':csrf()},body:"
    if save_new not in js:
        if save_old not in js:
            raise RuntimeError("Room planner save fetch contract changed")
        js = js.replace(save_old, save_new, 1)

    vision_old = "fetch(root.dataset.visionUrl,{method:'POST',headers:{'X-CSRFToken':csrf()},body:fd})"
    vision_new = "fetch(root.dataset.visionUrl,{method:'POST',credentials:'same-origin',headers:{'Accept':'application/json','X-Requested-With':'XMLHttpRequest','X-CSRFToken':csrf()},body:fd})"
    if vision_new not in js:
        if vision_old not in js:
            raise RuntimeError("Room planner vision fetch contract changed")
        js = js.replace(vision_old, vision_new, 1)

    polish = (OVERLAY / "static" / "js" / "room-planner-polish.js").read_text(encoding="utf-8")
    if "KAYI 3D KI assistant polish 20260810" not in js:
        js = js.rstrip() + "\n\n" + polish.strip() + "\n"
    write(js_path, js)


def patch_remaining_german_text() -> None:
    path = "static/js/app.js"
    text = read(path)
    text = text.replace("KAYI AI Live Edit", "KAYI KI Live Edit")
    write(path, text)


def bust_pwa_cache() -> None:
    replacements = {
        "kayi-shell-v18-20260810-de": "kayi-shell-v19-20260810-3dpolish",
        "kayi-shell-v19-20260810-de": "kayi-shell-v19-20260810-3dpolish",
    }
    for candidate in ROOT.rglob("service-worker.js"):
        try:
            text = candidate.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        original = text
        for old, new in replacements.items():
            text = text.replace(old, new)
        if text != original:
            candidate.write_text(text, encoding="utf-8")


def guard() -> None:
    customer = read("templates/rebuild/customer_form.html")
    room = read("templates/rebuild/room_planner.html")
    css = read("static/css/room-planner.css")
    js = read("static/js/room-planner.js")
    views = read("erp/room_planner_views.py")
    urls = read("erp/room_planner_urls.py")
    app_js = read("static/js/app.js")
    for needle in ["Abweichenden Einsatzort hinzufügen", "Etage", "Hinweise zum Zugang"]:
        if needle not in customer:
            raise RuntimeError(f"Customer form polish missing: {needle}")
    for needle in ["KI-Raumassistent", "data-rp-ai-command", "data-ai-url", "data-rp-csrf"]:
        if needle not in room:
            raise RuntimeError(f"Room planner KI UI missing: {needle}")
    if "AI setzt" in room or ">AI<" in room:
        raise RuntimeError("Visible English AI terminology remains in room planner template")
    if "KAYI AI Live Edit" in app_js:
        raise RuntimeError("Legacy tutorial still exposes English AI terminology")
    css_marker = "KAYI customer/3D polish 20260810"
    if css_marker not in css:
        raise RuntimeError("Room planner typography polish is missing")
    for needle in ["KAYI 3D KI assistant polish 20260810", "credentials:'same-origin'", "dataset.aiUrl"]:
        if needle not in js:
            raise RuntimeError(f"Room planner JS polish missing: {needle}")
    if "@ensure_csrf_cookie" not in views or "def room_planner_ai(" not in views:
        raise RuntimeError("Room planner CSRF/KI backend hardening is missing")
    if "next-room-planner-ai" not in urls:
        raise RuntimeError("Room planner KI route is missing")


install_customer_form()
install_room_ai_service()
patch_room_template()
patch_room_assets()
patch_remaining_german_text()
bust_pwa_cache()
guard()
print("KAYI customer form and professional 3D KI polish installed and verified.")
