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
    anchor = '    path("settings/next/", views.settings_page, name="next-settings"),\n'
    if anchor not in urls:
        raise RuntimeError("KAYI Next settings route anchor changed")
    routes = [
        '    path("assistant/command/", assistant.assistant_command, name="next-assistant-command"),',
        '    path("appointments/<int:pk>/voice/", assistant.appointment_voice, name="next-appointment-voice"),',
        '    path("konto/abmelden/", assistant.account_logout, name="next-logout"),',
    ]
    for route in routes:
        if route not in urls:
            urls = urls.replace(anchor, anchor + route + "\n", 1)
    write(urls_path, urls)


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
  <div class="nx-assistant-head"><div><div class="nx-kicker">KAYI KI</div><h3>Assistent für diese Seite</h3><p>Suchen, Felder ausfüllen, Auswahlen treffen und Katalogpositionen vorbereiten.</p></div><button type="button" class="nx-assistant-close" data-assistant-close>×</button></div>
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


def patch_field_home() -> None:
    path = "templates/rebuild/field_home.html"
    text = read(path)
    text = text.replace(
        "Kunden auswählen oder neu anlegen → Spracheingabe → Preis → Unterschrift → Arbeit starten.",
        "Kunde → Auftrag & Preis → Unterschrift → Arbeit → Sprachnotiz → Kundenunterschrift → PDF.",
    ).replace(
        "Kunden auswählen oder neu anlegen → Voice → Preis → Unterschrift → Arbeit starten.",
        "Kunde → Auftrag & Preis → Unterschrift → Arbeit → Sprachnotiz → Kundenunterschrift → PDF.",
    )
    if "Vor Ort in einem Ablauf" not in text:
        anchor = '<div data-tabs>'
        index = text.find(anchor)
        if index < 0:
            raise RuntimeError("Field home tabs anchor changed")
        card = '''<section class="nx-field-flow-card"><b>Vor Ort in einem Ablauf</b><p>Auftrag und Preis mit dem Kunden freigeben, arbeiten, danach eine echte Sprachnotiz aufnehmen, von KAYI KI in Bericht/Leistungen/Material umwandeln lassen, gemeinsam prüfen, unterschreiben und das Abschluss-PDF direkt übergeben.</p><div class="nx-field-flow-steps"><span>1 · Freigabe</span><span>2 · Arbeit</span><span>3 · Aufnahme</span><span>4 · KI-Bericht</span><span>5 · Unterschrift</span><span>6 · PDF</span></div></section>\n\n  '''
        text = text[:index] + card + text[index:]
    write(path, text)


def patch_field_template() -> None:
    path = "templates/rebuild/appointment_detail.html"
    text = read(path)
    text = text.replace("AI strukturieren", "KI strukturieren").replace("mit AI strukturieren", "mit KI strukturieren").replace("mit AI", "mit KI")

    completion_form_marker = 'data-completion-form'
    form_marker_at = text.find(completion_form_marker)
    if form_marker_at >= 0:
        form_start = text.rfind('<form', 0, form_marker_at)
        form_end = text.find('</form>', form_marker_at)
        if form_start < 0 or form_end < 0:
            raise RuntimeError("Completion form boundaries changed")

        if "data-field-voice" not in text[form_start:form_end]:
            voice_anchor = text.find('<div class="fa-voice-field">', form_marker_at, form_end)
            if voice_anchor < 0:
                raise RuntimeError("Completion report block changed")
            recording = '''<div class="nx-voice-capture" data-field-voice data-mode="completion" data-transcribe-url="{% url 'next-appointment-voice' event.pk %}">
        <label class="nx-voice-consent"><input type="checkbox" data-field-voice-consent><span>Der Ansprechpartner stimmt der Vor-Ort-Sprachaufnahme und der KI-Auswertung zu.</span></label>
        <div class="nx-voice-controls"><button class="nx-btn nx-btn-primary" type="button" data-field-record>🎙 Vor-Ort-Sprachnotiz aufnehmen</button><button class="nx-btn" type="button" data-field-transcribe hidden>✦ Aufnahme mit KI auswerten</button><span class="nx-record-status" data-field-record-status>Noch keine Aufnahme.</span></div>
        <audio class="nx-voice-preview" data-field-voice-preview controls hidden></audio>
        <input type="file" name="voice_note" accept="audio/*" data-field-voice-file hidden><input type="hidden" name="voice_transcript">
      </div>
      '''
            text = text[:voice_anchor] + recording + text[voice_anchor:]
            form_end += len(recording)

        final_sign_pattern = re.compile(r'<details class="fa-final-sign">.*?</details>', re.S)
        segment = text[form_start:form_end]
        if "data-customer-reviewed" not in segment:
            final_sign = '''<div class="fa-final-sign fa-final-sign-required">
        <div class="fa-block-head"><div><b>Kundenunterschrift zum Abschluss</b><small>Bericht, Leistungen und Material gemeinsam prüfen. Die Unterschrift wird Bestandteil des Abschluss-PDF.</small></div></div>
        <label class="fa-consent"><input type="checkbox" name="customer_reviewed" value="1" data-customer-reviewed required><span>Arbeitsbericht, ausgeführte Leistungen, Material und Ergebnis wurden gemeinsam geprüft.</span></label>
        <canvas class="fa-signature" data-completion-signature-canvas></canvas><input type="hidden" name="completion_signature_data" data-completion-signature-data><button type="button" class="nx-btn nx-btn-ghost" data-completion-signature-clear>Unterschrift löschen</button>
      </div>'''
            new_segment, count = final_sign_pattern.subn(final_sign, segment, count=1)
            if count != 1:
                raise RuntimeError("Completion customer signature block changed")
            text = text[:form_start] + new_segment + text[form_end:]
            form_end = form_start + len(new_segment)

        text = text.replace("✓ Einsatz abschließen & PDF erzeugen", "✓ Einsatz abschließen & PDF erstellen")
        if "data-handoff-result" not in text[form_start:form_end]:
            form_end_close = text.find('</form>', form_start)
            result = '''<div class="nx-handoff-result" data-handoff-result hidden><b>✓ Einsatz abgeschlossen</b><p>Der unterschriebene Abschluss wurde archiviert. Das PDF kann jetzt direkt beim Kunden geöffnet oder geteilt werden.</p><div class="nx-actions"><a class="nx-btn nx-btn-primary" data-handoff-pdf target="_blank" download>PDF öffnen / herunterladen</a><button class="nx-btn" type="button" data-handoff-share>PDF teilen</button></div></div>\n      '''
            text = text[:form_end_close] + result + text[form_end_close:]

    text = re.sub(r"(field-authorization\.(?:css|js)' %\}\?v=)[^\"']+", rf"\g<1>{VERSION}", text)
    write(path, text)


def patch_field_backend() -> None:
    path = "erp/field_authorization_views.py"
    text = read(path)

    auth_ai_anchor = '''def authorization_ai(request, pk):\n    org, event = _event_for(request, pk)\n'''
    auth_ai_new = '''def authorization_ai(request, pk):\n    org, event = _event_for(request, pk)\n    from .store_views import has_ai_consent\n    if not has_ai_consent(request.user):\n        return JsonResponse({"ok": False, "error": "Vor der KI-Verarbeitung ist deine ausdrückliche Einwilligung in den Einstellungen erforderlich.", "consent_required": True, "settings_url": "/settings/next/"}, status=428)\n'''
    if "authorization_ai(request, pk)" in text and "authorization_ai(request, pk):\n    org, event = _event_for(request, pk)\n    from .store_views import has_ai_consent" not in text:
        if auth_ai_anchor not in text:
            raise RuntimeError("Authorization KI consent anchor changed")
        text = text.replace(auth_ai_anchor, auth_ai_new, 1)

    if "KAYI_FINAL_CUSTOMER_HANDOFF" not in text:
        material_anchor = '''    material = (request.POST.get("material") or "").strip()\n'''
        material_new = material_anchor + '''    # KAYI_FINAL_CUSTOMER_HANDOFF\n    voice_transcript = (request.POST.get("voice_transcript") or "").strip()\n    customer_reviewed = request.POST.get("customer_reviewed") == "1"\n    if not customer_reviewed:\n        return JsonResponse({"ok": False, "error": "Bitte Bericht, Leistungen und Material gemeinsam mit dem Kunden prüfen."}, status=400)\n'''
        complete_at = text.find("def complete_job(request, pk):")
        material_at = text.find(material_anchor, complete_at)
        if complete_at < 0 or material_at < 0:
            raise RuntimeError("Completion material anchor changed")
        text = text[:material_at] + text[material_at:].replace(material_anchor, material_new, 1)

        signature_anchor = '''    completion_signature = decode_signature(request.POST.get("completion_signature_data") or "")\n'''
        signature_new = signature_anchor + '''    if not completion_signature:\n        return JsonResponse({"ok": False, "error": "Bitte den Kunden den Einsatzabschluss unterschreiben lassen."}, status=400)\n    voice_upload = request.FILES.get("voice_note")\n    voice_raw = b""\n    voice_mime = ""\n    voice_name = ""\n    if voice_upload is not None:\n        if getattr(voice_upload, "size", 0) > 20 * 1024 * 1024:\n            return JsonResponse({"ok": False, "error": "Die Sprachaufnahme ist größer als 20 MB."}, status=400)\n        voice_mime = (getattr(voice_upload, "content_type", "") or "audio/webm")[:120]\n        if not voice_mime.startswith("audio/"):\n            return JsonResponse({"ok": False, "error": "Die Sprachaufnahme hat ein ungültiges Dateiformat."}, status=400)\n        voice_name = Path(getattr(voice_upload, "name", "einsatz.webm") or "einsatz.webm").name\n        voice_raw = voice_upload.read()\n'''
        complete_at = text.find("def complete_job(request, pk):")
        sig_at = text.find(signature_anchor, complete_at)
        if sig_at < 0:
            raise RuntimeError("Completion signature anchor changed")
        text = text[:sig_at] + text[sig_at:].replace(signature_anchor, signature_new, 1)

        snapshot_anchor = '''        "material": material,\n'''
        snapshot_new = snapshot_anchor + '''        "voice_transcript": voice_transcript,\n        "customer_reviewed": customer_reviewed,\n'''
        complete_at = text.find("def complete_job(request, pk):")
        snap_at = text.find(snapshot_anchor, complete_at)
        if snap_at < 0:
            raise RuntimeError("Completion snapshot anchor changed")
        text = text[:snap_at] + text[snap_at:].replace(snapshot_anchor, snapshot_new, 1)

        transaction_anchor = '''    with transaction.atomic():\n        for photo in after_photos:\n'''
        transaction_new = '''    with transaction.atomic():\n        if voice_raw:\n            save_binary_document(\n                org=org, project=event.project, customer=event.project.customer, user=request.user,\n                title=f"Vor-Ort-Sprachnotiz · {event.title}", category="other",\n                filename=f"voice-{event.pk}-{timezone.now():%Y%m%d%H%M%S}-{voice_name}", mime=voice_mime, raw=voice_raw,\n                metadata={"event_id": event.pk, "kind": "field_voice_note", "phase": "after", "transcript": voice_transcript, "completion_snapshot_sha256": completion_hash},\n            )\n        for photo in after_photos:\n'''
        complete_at = text.find("def complete_job(request, pk):")
        transaction_at = text.find(transaction_anchor, complete_at)
        if transaction_at < 0:
            raise RuntimeError("Completion transaction anchor changed")
        text = text[:transaction_at] + text[transaction_at:].replace(transaction_anchor, transaction_new, 1)

        old_signature_save = '''        signature_doc = None\n        if completion_signature:\n            signature_doc = save_binary_document(\n                org=org, project=event.project, customer=event.project.customer, user=request.user,\n                title="Kundenunterschrift Einsatzabschluss", category="other", filename=f"completion-signature-{event.pk}-{timezone.now():%Y%m%d%H%M%S}.png", mime="image/png", raw=completion_signature,\n                metadata={"event_id": event.pk, "kind": "field_completion_signature", "phase": "after", "completion_snapshot_sha256": completion_hash},\n            )\n'''
        new_signature_save = '''        signature_doc = save_binary_document(\n            org=org, project=event.project, customer=event.project.customer, user=request.user,\n            title="Kundenunterschrift Einsatzabschluss", category="other", filename=f"completion-signature-{event.pk}-{timezone.now():%Y%m%d%H%M%S}.png", mime="image/png", raw=completion_signature,\n            metadata={"event_id": event.pk, "kind": "field_completion_signature", "phase": "after", "completion_snapshot_sha256": completion_hash},\n        )\n'''
        if old_signature_save not in text:
            raise RuntimeError("Completion signature persistence contract changed")
        text = text.replace(old_signature_save, new_signature_save, 1)
        text = text.replace('"signature_document_id": signature_doc.pk if signature_doc else None', '"signature_document_id": signature_doc.pk', 1)
    write(path, text)


def patch_field_js() -> None:
    path = "static/js/field-authorization.js"
    text = read(path)
    text = text.replace("AI analysiert", "KI analysiert").replace("AI nicht erreichbar", "KI nicht erreichbar")
    old_fetch = "const res = await fetch(form.action, { method: 'POST', headers: { 'X-CSRFToken': csrf(form) }, body: new FormData(form) }); const data = await res.json();"
    new_fetch = "const res = await fetch(form.action, { method: 'POST', credentials: 'same-origin', headers: { 'Accept':'application/json','X-Requested-With':'XMLHttpRequest','X-CSRFToken': csrf(form) }, body: new FormData(form) }); const data = await res.json();"
    if new_fetch not in text:
        if old_fetch not in text:
            raise RuntimeError("Field form fetch contract changed")
        text = text.replace(old_fetch, new_fetch, 1)
    old_redirect = "if (data.redirect) window.location.href = data.redirect; else if (data.reload) window.location.reload();\n      return data;"
    new_redirect = "if (form.matches('[data-completion-form]') && data.pdf_url && window.KAYIFieldHandoff?.showResult(data)) { if (button) button.hidden = true; return data; }\n      if (data.redirect) window.location.href = data.redirect; else if (data.reload) window.location.reload();\n      return data;"
    if new_redirect not in text:
        if old_redirect not in text:
            raise RuntimeError("Field completion response contract changed")
        text = text.replace(old_redirect, new_redirect, 1)
    old_submit = "form.addEventListener('submit', (e) => { e.preventDefault(); postForm(form, $('[data-completion-status]', form)); });"
    new_submit = "form.addEventListener('submit', (e) => { e.preventDefault(); const reviewed = $('[data-customer-reviewed]', form); const signature = $('[data-completion-signature-data]', form); if (!reviewed?.checked) { toast('Bitte den Abschluss gemeinsam mit dem Kunden prüfen.', 'error'); return; } if (!signature?.value) { toast('Bitte Kundenunterschrift zum Abschluss erfassen.', 'error'); return; } postForm(form, $('[data-completion-status]', form)); });"
    if new_submit not in text:
        if old_submit not in text:
            raise RuntimeError("Field completion submit contract changed")
        text = text.replace(old_submit, new_submit, 1)
    write(path, text)


def patch_assets() -> None:
    append_once("static/css/kayi-next.css", "static/css/global-assistant.css")
    js_path = "static/js/kayi-next.js"
    js = read(js_path)
    addition = (OVERLAY / "static" / "js" / "global-assistant.js").read_text(encoding="utf-8")
    if MARKER not in js:
        js = js.rstrip() + "\n\n" + addition.strip() + "\n"
    write(js_path, js)


def install_tests() -> None:
    copy("tests/test_global_ai_field_handoff.py")


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
    field_views = read("erp/field_authorization_views.py")
    next_js = read("static/js/kayi-next.js")
    field_js = read("static/js/field-authorization.js")
    css = read("static/css/kayi-next.css")
    for needle in ["data-profile-toggle", "data-profile-menu", "data-global-assistant-form", "data-assistant-drawer", "next-logout"]:
        if needle not in base:
            raise RuntimeError(f"Global KI/profile UI missing: {needle}")
    for needle in ["next-assistant-command", "next-appointment-voice", "next-logout"]:
        if needle not in urls:
            raise RuntimeError(f"Global KI route missing: {needle}")
    for needle in ["data-field-voice", "data-customer-reviewed", "Kundenunterschrift zum Abschluss", "Einsatz abschließen & PDF erstellen", "data-handoff-result"]:
        if needle not in appointment:
            raise RuntimeError(f"Field handoff UI missing: {needle}")
    if "Vor Ort in einem Ablauf" not in field:
        raise RuntimeError("Field workflow is not discoverable on Monteur-App home")
    for needle in ["KAYI_FINAL_CUSTOMER_HANDOFF", "field_voice_note", "customer_reviewed", "signature_doc.pk"]:
        if needle not in field_views:
            raise RuntimeError(f"Real field handoff backend missing: {needle}")
    for needle in ["KAYIFieldHandoff", "data-field-voice", "MediaRecorder"]:
        if needle not in next_js:
            raise RuntimeError(f"Global/voice runtime missing: {needle}")
    if "KAYIFieldHandoff?.showResult" not in field_js or "Kundenunterschrift zum Abschluss erfassen" not in field_js:
        raise RuntimeError("Field completion JS does not enforce/show signed PDF handoff")
    if MARKER not in css:
        raise RuntimeError("Global KI styles were not installed")


install_backend()
patch_base()
patch_field_home()
patch_field_template()
patch_field_backend()
patch_field_js()
patch_assets()
install_tests()
patch_browser_smoke()
guard()
print("KAYI global KI, working profile menu and the real signed field voice-to-PDF handoff are installed and verified.")
