from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "overlays" / "global_ai_field_handoff"
VERSION = "20260810-8"
MARKER = "KAYI global KI + field handoff 20260810"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Missing global KI target: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def copy(rel: str) -> None:
    source = OVERLAY / rel
    target = ROOT / rel
    if not source.exists():
        raise RuntimeError(f"Missing global KI overlay: {rel}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def append_once(rel: str, overlay_rel: str, marker: str = MARKER) -> None:
    text = read(rel)
    if marker in text:
        return
    addition = (OVERLAY / overlay_rel).read_text(encoding="utf-8")
    write(rel, text.rstrip() + "\n\n" + addition.strip() + "\n")


def install_backend() -> None:
    copy("erp/assistant_views.py")
    urls_path = "erp/rebuild_urls.py"
    urls = read(urls_path)
    if "from . import assistant_views as assistant" not in urls:
        anchor = "from . import rebuild_views as views\n"
        if anchor not in urls:
            raise RuntimeError("KAYI Next URL import anchor changed")
        urls = urls.replace(anchor, anchor + "from . import assistant_views as assistant\n", 1)
    routes = [
        '    path("assistant/command/", assistant.assistant_command, name="next-assistant-command"),',
        '    path("appointments/<int:pk>/voice/", assistant.appointment_voice, name="next-appointment-voice"),',
        '    path("konto/abmelden/", assistant.account_logout, name="next-logout"),',
    ]
    anchor = '    path("settings/next/", views.settings_page, name="next-settings"),\n'
    if anchor not in urls:
        raise RuntimeError("KAYI Next settings route anchor changed")
    for route in routes:
        if route not in urls:
            urls = urls.replace(anchor, anchor + route + "\n", 1)
    write(urls_path, urls)


def patch_dependency() -> None:
    path = "requirements.txt"
    text = read(path)
    if "reportlab" not in text.lower():
        text = text.rstrip() + "\nreportlab>=4.4,<5\n"
    write(path, text)


def patch_base() -> None:
    path = "templates/rebuild/base.html"
    text = read(path)
    header = '''  <header class="nx-topbar">
      <button class="nx-menu-btn" type="button" data-nx-menu aria-label="Menü">☰</button>
      <form class="nx-search nx-ai-omnibox" data-global-assistant-form>
        <span class="nx-ai-star">✦</span><input data-global-assistant-input placeholder="KAYI KI: Beschreibe, was du suchst oder erledigen willst …" autocomplete="off"><button type="submit">↵</button>
      </form>
      <div class="nx-top-actions">
        {% if request.user.profile.role == 'technician' or request.user.profile.is_mobile_worker %}<a class="nx-btn nx-btn-ghost" href="{% url 'next-time' %}">◷ Zeit</a>{% else %}<a class="nx-btn nx-btn-ghost" href="{% url 'next-appointment-create' %}">＋ Termin</a><a class="nx-btn nx-btn-primary" href="{% url 'next-project-create' %}">＋ Projekt</a>{% endif %}
        <div class="nx-profile" data-profile>
          <button type="button" class="nx-avatar nx-avatar-button" data-profile-toggle aria-expanded="false" aria-label="Profilmenü">{{ request.user.username|slice:':2'|upper }}</button>
          <div class="nx-profile-menu" data-profile-menu hidden>
            <div class="nx-profile-name"><b>{{ request.user.get_full_name|default:request.user.username }}</b><small>{{ request.user.email|default:'KAYI Konto' }}</small></div>
            <a href="{% url 'next-settings' %}">⚙ Einstellungen</a>
            <a href="{% url 'next-field' %}">⌁ Monteur-App</a>
            <form method="post" action="{% url 'next-logout' %}">{% csrf_token %}<button type="submit">↪ Abmelden</button></form>
          </div>
        </div>
      </div>
    </header>'''
    if "data-global-assistant-form" not in text:
        text, count = re.subn(r"\s*<header class=\"nx-topbar\">.*?</header>", "\n" + header, text, count=1, flags=re.S)
        if count != 1:
            raise RuntimeError("KAYI Next topbar contract changed")

    drawer = '''
<button class="nx-assistant-fab" type="button" data-assistant-open aria-label="KAYI KI öffnen">✦</button>
<aside class="nx-assistant-drawer" data-assistant-drawer data-assistant-url="{% url 'next-assistant-command' %}" aria-hidden="true">
  <div class="nx-assistant-head"><div><div class="nx-kicker">KAYI KI</div><h3>Assistent für diese Seite</h3><p>Suchen, Felder ausfüllen, Selects wählen und Katalogpositionen vorbereiten.</p></div><button type="button" class="nx-assistant-close" data-assistant-close>×</button></div>
  <div class="nx-assistant-chat" data-assistant-chat><div class="nx-assistant-msg is-ai">Sag einfach, was du erledigen willst. Ich ändere nur den Entwurf – gespeichert oder versendet wird erst durch dich.</div></div>
  <div class="nx-assistant-suggestions"><button type="button" data-assistant-suggestion="Fülle die sichtbaren Felder anhand meiner Beschreibung aus.">Formular ausfüllen</button><button type="button" data-assistant-suggestion="Hilf mir, den richtigen Kunden oder das richtige Projekt zu finden.">Kunde / Projekt finden</button><button type="button" data-assistant-suggestion="Wähle passende Positionen aus dem sichtbaren Katalog aus.">Katalog wählen</button></div>
  <form class="nx-assistant-compose" data-assistant-form><textarea class="nx-control" data-assistant-input placeholder="z. B. Wähle Kunde Müller, Projekt Bad und Meier als Verantwortlichen …"></textarea><button class="nx-btn nx-btn-primary" type="submit">✦</button></form>
</aside>
'''
    if "data-assistant-drawer" not in text:
        anchor = '<script src="{% static \'js/kayi-next.js\' %}'
        index = text.find(anchor)
        if index < 0:
            raise RuntimeError("KAYI Next script anchor changed")
        text = text[:index] + drawer + text[index:]
    text = re.sub(r"(kayi-next\.(?:css|js)' %\}\?v=)[^\"']+", rf"\g<1>{VERSION}", text)
    write(path, text)


def patch_field_ui() -> None:
    path = "templates/rebuild/field_home.html"
    text = read(path)
    if "Vor Ort in einem Ablauf" not in text:
        anchor = '  <div data-tabs>\n'
        card = '''  <section class="nx-field-flow-card"><b>Vor Ort in einem Ablauf</b><p>Termin öffnen, Sprachnotiz aufnehmen, von KAYI KI in Bericht/Leistungen/Material strukturieren lassen, gemeinsam prüfen, unterschreiben und den Arbeitsnachweis direkt als PDF übergeben.</p><div class="nx-field-flow-steps"><span>1 · Aufnahme</span><span>2 · KI-Bericht</span><span>3 · Prüfen</span><span>4 · Unterschrift</span><span>5 · PDF</span></div></section>\n'''
        if anchor not in text:
            raise RuntimeError("Field home tabs anchor changed")
        text = text.replace(anchor, card + anchor, 1)
    write(path, text)

    path = "templates/rebuild/appointment_detail.html"
    text = read(path)
    text = text.replace("AI strukturieren", "KI strukturieren").replace("AI Fehler", "KI Fehler")
    if "data-field-voice" not in text:
        anchor = '        <textarea class="nx-control" name="report_text" data-voice-target'
        recording = '''        <div class="nx-voice-capture" data-field-voice data-transcribe-url="{% url 'next-appointment-voice' event.pk %}">
          <label class="nx-voice-consent"><input type="checkbox" data-field-voice-consent><span>Der Ansprechpartner stimmt der Vor-Ort-Sprachaufnahme und der KI-Auswertung zu.</span></label>
          <div class="nx-voice-controls"><button class="nx-btn nx-btn-primary" type="button" data-field-record>🎙 Vor-Ort-Sprachnotiz aufnehmen</button><button class="nx-btn" type="button" data-field-transcribe hidden>✦ Aufnahme mit KI auswerten</button><span class="nx-record-status" data-field-record-status>Noch keine Aufnahme.</span></div>
          <audio class="nx-voice-preview" data-field-voice-preview controls hidden></audio>
          <input type="file" name="voice_note" accept="audio/*" data-field-voice-file hidden><input type="hidden" name="voice_transcript">
        </div>
'''
        if anchor not in text:
            raise RuntimeError("Appointment report textarea anchor changed")
        text = text.replace(anchor, recording + anchor, 1)
    if "data-customer-reviewed" not in text:
        anchor = '      <div class="nx-doc-section">\n        <div class="nx-doc-title"><div><b>Kundenunterschrift</b>'
        review = '''      <div class="nx-doc-section"><div class="nx-handoff-review"><label><input type="checkbox" name="customer_reviewed" value="1" data-customer-reviewed required><span><b>Gemeinsam geprüft</b><br>Arbeitsbericht, ausgeführte Leistungen und Material wurden mit dem Ansprechpartner vor Ort durchgegangen.</span></label></div></div>\n'''
        if anchor not in text:
            raise RuntimeError("Appointment signature anchor changed")
        text = text.replace(anchor, review + anchor, 1)
    text = text.replace("✓ Einsatz dokumentieren", "✓ Einsatz abschließen & PDF erstellen")
    if "data-handoff-result" not in text:
        result = '''      <div class="nx-handoff-result" data-handoff-result hidden><b>✓ Einsatz abgeschlossen</b><p>Der unterschriebene Arbeitsnachweis wurde im Projekt gespeichert und steht als PDF zur Übergabe bereit.</p><div class="nx-actions"><a class="nx-btn nx-btn-primary" data-handoff-pdf target="_blank" download>PDF öffnen / herunterladen</a><button class="nx-btn" type="button" data-handoff-share>PDF teilen</button></div></div>\n'''
        anchor = '    </form>\n'
        if anchor not in text:
            raise RuntimeError("Appointment documentation form close changed")
        text = text.replace(anchor, result + anchor, 1)
    write(path, text)


def patch_field_backend() -> None:
    path = "erp/rebuild_views.py"
    text = read(path)
    marker = "KAYI_FIELD_HANDOFF_VALIDATION"
    if marker not in text:
        anchor = '    customer_name = (request.POST.get("customer_name") or "").strip()\n'
        addition = '''    # KAYI_FIELD_HANDOFF_VALIDATION\n    voice_transcript = (request.POST.get("voice_transcript") or "").strip()\n    customer_reviewed = request.POST.get("customer_reviewed") == "1"\n    signature_data = request.POST.get("signature_data") or ""\n    if not customer_reviewed:\n        return JsonResponse({"ok": False, "error": "Bitte Bericht, Leistungen und Material gemeinsam mit dem Kunden prüfen."}, status=400)\n    if not signature_data.startswith("data:image/png;base64,"):\n        return JsonResponse({"ok": False, "error": "Bitte den Ansprechpartner vor Ort unterschreiben lassen."}, status=400)\n    try:\n        base64.b64decode(signature_data.split(",", 1)[1], validate=True)\n    except Exception:\n        return JsonResponse({"ok": False, "error": "Die Unterschrift ist ungültig. Bitte erneut unterschreiben."}, status=400)\n'''
        if anchor not in text:
            raise RuntimeError("Appointment customer name anchor changed")
        text = text.replace(anchor, anchor + addition, 1)
        payload_anchor = '        "customer_name": customer_name,\n        "source": "kayi-next-field",\n'
        payload_new = '        "customer_name": customer_name,\n        "voice_transcript": voice_transcript,\n        "customer_reviewed": customer_reviewed,\n        "source": "kayi-next-field",\n'
        if payload_anchor not in text:
            raise RuntimeError("Appointment report payload anchor changed")
        text = text.replace(payload_anchor, payload_new, 1)

        photo_anchor = '''        photo.file.save(upload.name, upload, save=False)\n        photo.save()\n\n    signature_data = request.POST.get("signature_data") or ""\n'''
        voice_block = '''        photo.file.save(upload.name, upload, save=False)\n        photo.save()\n\n    voice_upload = request.FILES.get("voice_note")\n    if voice_upload is not None:\n        voice_document = m.Document(\n            organization=org, customer=event.project.customer, project=event.project,\n            title=f"Vor-Ort-Sprachnotiz · {event.title}", category="other",\n            mime_type=getattr(voice_upload, "content_type", "") or "audio/webm",\n            size=getattr(voice_upload, "size", 0) or 0,\n            metadata={"event_id": event.pk, "kind": "field_voice_note", "transcript": voice_transcript, "source": "kayi-next-field"},\n            uploaded_by=request.user,\n        )\n        voice_document.file.save(getattr(voice_upload, "name", "einsatz.webm") or "einsatz.webm", voice_upload, save=False)\n        voice_document.save()\n\n    signature_data = request.POST.get("signature_data") or ""\n'''
        if photo_anchor not in text:
            raise RuntimeError("Appointment photo/signature anchor changed")
        text = text.replace(photo_anchor, voice_block, 1)

        status_anchor = '''    if event.project.status in {"inquiry", "planning", "quoted", "confirmed"}:\n'''
        pdf_block = '''    from .assistant_views import build_field_report_pdf\n    pdf_document = build_field_report_pdf(\n        organization=org, event=event, user=request.user, report_text=report_text, services=services, material=material,\n        customer_name=customer_name, voice_transcript=voice_transcript, signature_data=signature_data,\n        photo_names=[upload.name for upload in request.FILES.getlist("photos")],\n    )\n\n'''
        if status_anchor not in text:
            raise RuntimeError("Appointment project status anchor changed")
        text = text.replace(status_anchor, pdf_block + status_anchor, 1)
        old_return = '    return JsonResponse({"ok": True, "redirect": f"/appointments/{event.pk}/"})\n'
        new_return = '    return JsonResponse({"ok": True, "redirect": f"/appointments/{event.pk}/", "pdf_url": pdf_document.file.url, "pdf_document_id": pdf_document.pk})\n'
        if old_return not in text:
            raise RuntimeError("Appointment document response anchor changed")
        text = text.replace(old_return, new_return, 1)
    write(path, text)


def patch_assets() -> None:
    append_once("static/css/kayi-next.css", "static/css/global-assistant.css")
    js_path = "static/js/kayi-next.js"
    js = read(js_path)
    redirect_old = '        window.location.href = result.redirect || window.location.href;\n'
    redirect_new = '        if (result.pdf_url && window.KAYIFieldHandoff?.showResult(result)) return;\n        window.location.href = result.redirect || window.location.href;\n'
    if redirect_new not in js:
        if redirect_old not in js:
            raise RuntimeError("Documentation result redirect anchor changed")
        js = js.replace(redirect_old, redirect_new, 1)
    addition = (OVERLAY / "static" / "js" / "global-assistant.js").read_text(encoding="utf-8")
    if MARKER not in js:
        js = js.rstrip() + "\n\n" + addition.strip() + "\n"
    write(js_path, js)


def install_tests() -> None:
    source = OVERLAY / "tests" / "test_global_ai_field_handoff.py"
    target = ROOT / "tests" / "test_global_ai_field_handoff.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def patch_browser_smoke() -> None:
    path = "scripts/production_browser_smoke.py"
    text = read(path)
    marker = "KAYI global KI profile smoke"
    if marker not in text:
        anchor = '''            login(page, base_url, username, password)\n            office_checks = [\n'''
        block = '''            login(page, base_url, username, password)\n            # KAYI global KI profile smoke\n            if page.locator('[data-global-assistant-form]').count() != 1 or page.locator('[data-assistant-drawer]').count() != 1:\n                fail("global KAYI KI assistant is missing from office surface")\n            if page.locator('[data-profile-toggle]').count() != 1:\n                fail("profile avatar is not interactive")\n            page.locator('[data-profile-toggle]').click()\n            if not page.locator('[data-profile-menu]').is_visible():\n                fail("profile menu does not open")\n            page.keyboard.press('Escape')\n            office_checks = [\n'''
        if anchor not in text:
            raise RuntimeError("Office smoke login anchor changed")
        text = text.replace(anchor, block, 1)
        field_old = '            for marker in ("Meine Einsätze", "Geplant", "Überfällig", "Dokumentiert", "nx-field-bottom"):\n'
        field_new = '            for marker in ("Meine Einsätze", "Geplant", "Überfällig", "Dokumentiert", "nx-field-bottom", "Vor Ort in einem Ablauf", "data-global-assistant-form"):\n'
        if field_old not in text:
            raise RuntimeError("Field smoke marker anchor changed")
        text = text.replace(field_old, field_new, 1)
    write(path, text)


def guard() -> None:
    base = read("templates/rebuild/base.html")
    appointment = read("templates/rebuild/appointment_detail.html")
    field = read("templates/rebuild/field_home.html")
    urls = read("erp/rebuild_urls.py")
    views = read("erp/rebuild_views.py")
    js = read("static/js/kayi-next.js")
    css = read("static/css/kayi-next.css")
    requirements = read("requirements.txt")
    for needle in ["data-profile-toggle", "data-profile-menu", "data-global-assistant-form", "data-assistant-drawer", "next-logout"]:
        if needle not in base:
            raise RuntimeError(f"Global KI/profile UI missing: {needle}")
    for needle in ["next-assistant-command", "next-appointment-voice", "next-logout"]:
        if needle not in urls:
            raise RuntimeError(f"Global KI route missing: {needle}")
    for needle in ["data-field-voice", "data-customer-reviewed", "Einsatz abschließen & PDF erstellen", "data-handoff-result"]:
        if needle not in appointment:
            raise RuntimeError(f"Field handoff UI missing: {needle}")
    if "Vor Ort in einem Ablauf" not in field:
        raise RuntimeError("Field workflow is not discoverable on Monteur-App home")
    for needle in ["KAYI_FIELD_HANDOFF_VALIDATION", "field_voice_note", "build_field_report_pdf", '"pdf_url"']:
        if needle not in views:
            raise RuntimeError(f"Field handoff backend missing: {needle}")
    if MARKER not in js or MARKER not in css:
        raise RuntimeError("Global KI assets were not installed")
    if "reportlab" not in requirements.lower():
        raise RuntimeError("Signed PDF dependency missing")


install_backend()
patch_dependency()
patch_base()
patch_field_ui()
patch_field_backend()
patch_assets()
install_tests()
patch_browser_smoke()
guard()
print("KAYI global KI assistant, working profile menu, real field voice capture, signed handoff PDF and browser guards installed.")
