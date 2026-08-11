from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "KAYI ANDROID VOICE CAPTURE HOTFIX 2026-08-11"
VERSION = "20260811-7"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Missing Android voice hotfix target: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_backend() -> None:
    rel = "erp/assistant_views.py"
    text = read(rel)
    if "def field_voice_transcribe(request):" not in text:
        anchor = "\n\ndef _draw_wrapped(pdf, text: str, x: float, y: float, width_chars: int = 92, leading: float = 13) -> float:\n"
        if anchor not in text:
            raise RuntimeError("Generic voice endpoint anchor changed")
        endpoint = r'''

@login_required
@require_POST
def field_voice_transcribe(request):
    """Transcribe a field recording without requiring an existing appointment.

    This endpoint is intentionally usable by Schnellauftrag before the job/event
    exists. The text is returned to the current form; nothing is saved here.
    """
    if not has_ai_consent(request.user):
        return _consent_error()
    upload = request.FILES.get("voice")
    if upload is None:
        return JsonResponse({"ok": False, "error": "Keine Sprachaufnahme empfangen."}, status=400)
    if getattr(upload, "size", 0) > 20 * 1024 * 1024:
        return JsonResponse({"ok": False, "error": "Die Sprachaufnahme ist zu groß. Bitte kürzer aufnehmen."}, status=400)
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return JsonResponse({"ok": False, "error": "Die KI-Sprachauswertung ist noch nicht konfiguriert."}, status=503)
    try:
        from openai import OpenAI

        raw = upload.read()
        if len(raw) < 32:
            return JsonResponse({"ok": False, "error": "Die Sprachaufnahme ist leer oder zu kurz."}, status=400)
        audio = io.BytesIO(raw)
        audio.name = getattr(upload, "name", "kayi-aufnahme.webm") or "kayi-aufnahme.webm"
        client = OpenAI(api_key=api_key)
        transcription = client.audio.transcriptions.create(
            model=os.environ.get("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe"),
            file=audio,
            language="de",
        )
        transcript = str(getattr(transcription, "text", "") or "").strip()
    except Exception:
        return JsonResponse({"ok": False, "error": "Die Sprachaufnahme konnte nicht transkribiert werden."}, status=502)
    if not transcript:
        return JsonResponse({"ok": False, "error": "In der Aufnahme wurde kein verständlicher Text erkannt."}, status=422)
    return JsonResponse({"ok": True, "transcript": transcript})
'''
        text = text.replace(anchor, endpoint + anchor, 1)
        write(rel, text)

    urls_rel = "erp/rebuild_urls.py"
    urls = read(urls_rel)
    route = '    path("field/voice/transcribe/", assistant.field_voice_transcribe, name="next-field-voice-transcribe"),\n'
    if route not in urls:
        anchor = '    path("assistant/command/", assistant.assistant_command, name="next-assistant-command"),\n'
        if anchor not in urls:
            raise RuntimeError("Assistant route anchor changed")
        urls = urls.replace(anchor, anchor + route, 1)
        write(urls_rel, urls)


def patch_javascript() -> None:
    rel = "static/js/field-authorization.js"
    text = read(rel)
    if MARKER not in text:
        text += r'''

// KAYI ANDROID VOICE CAPTURE HOTFIX 2026-08-11
(() => {
  'use strict';
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const endpoint = '/field/voice/transcribe/';
  const states = new WeakMap();

  const csrf = (root = document) => $('input[name="csrfmiddlewaretoken"]', root)?.value || document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';
  const toast = (message, type = 'info') => {
    let el = $('.fa-toast');
    if (!el) { el = document.createElement('div'); el.className = 'fa-toast'; document.body.appendChild(el); }
    el.textContent = message; el.dataset.type = type; el.classList.add('show');
    clearTimeout(el._voiceTimer); el._voiceTimer = setTimeout(() => el.classList.remove('show'), 4300);
  };
  const targetFor = (button) => {
    const box = button.closest('.fa-voice-field,.fa-block,form') || document;
    return $('[data-voice-target]', box) || $('[data-voice-target]');
  };
  const appendTranscript = (target, transcript) => {
    const before = String(target.value || '').trim();
    target.value = [before, String(transcript || '').trim()].filter(Boolean).join(before ? ' ' : '');
    target.dispatchEvent(new Event('input', {bubbles:true}));
    target.dispatchEvent(new Event('change', {bubbles:true}));
    target.focus({preventScroll:true});
  };
  const sendVoice = async (button, target, file) => {
    const old = button.textContent;
    button.disabled = true; button.textContent = '✦';
    try {
      const data = new FormData(); data.append('voice', file); data.append('csrfmiddlewaretoken', csrf(button.closest('form') || document));
      const response = await fetch(endpoint, {
        method:'POST', credentials:'same-origin', body:data,
        headers:{'Accept':'application/json','X-Requested-With':'XMLHttpRequest','X-CSRFToken':csrf(button.closest('form') || document)},
      });
      const result = await response.json().catch(()=>({}));
      if (response.status === 428) throw new Error(result.error || 'Bitte KI-Verarbeitung zuerst in den Einstellungen freigeben.');
      if (!response.ok || !result.ok) throw new Error(result.error || 'Sprachaufnahme konnte nicht verarbeitet werden.');
      appendTranscript(target, result.transcript);
      toast('Sprachaufnahme übernommen.', 'success');
    } catch (error) {
      toast(error.message || 'Sprachaufnahme konnte nicht verarbeitet werden.', 'error');
    } finally {
      button.disabled = false; button.textContent = old === '■' ? '🎙' : old;
    }
  };
  const nativeAudioCapture = (button, target) => {
    const input = document.createElement('input');
    input.type = 'file'; input.accept = 'audio/*'; input.setAttribute('capture','microphone'); input.hidden = true;
    input.addEventListener('change', async () => {
      const file = input.files?.[0];
      if (file) await sendVoice(button, target, file);
      input.remove();
    }, {once:true});
    document.body.appendChild(input);
    try { input.click(); } catch (_) { toast('Bitte Mikrofon in den Website-Einstellungen erlauben oder eine Audiodatei auswählen.', 'error'); }
  };

  const handleVoiceButton = async (button) => {
    const target = targetFor(button);
    if (!target) { toast('Zielfeld für die Spracheingabe wurde nicht gefunden.', 'error'); return; }
    const current = states.get(button);
    if (current?.recorder?.state === 'recording') { current.recorder.stop(); return; }
    if (!window.MediaRecorder || !navigator.mediaDevices?.getUserMedia) {
      nativeAudioCapture(button, target); return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({audio:true});
      const chunks = [];
      const preferred = MediaRecorder.isTypeSupported?.('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : '';
      const recorder = new MediaRecorder(stream, preferred ? {mimeType:preferred} : undefined);
      states.set(button, {recorder, stream});
      recorder.ondataavailable = (event) => { if (event.data?.size) chunks.push(event.data); };
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        states.delete(button); button.classList.remove('is-listening'); button.textContent = '🎙';
        const mime = recorder.mimeType || 'audio/webm';
        const ext = mime.includes('ogg') ? 'ogg' : (mime.includes('mp4') ? 'm4a' : 'webm');
        const blob = new Blob(chunks, {type:mime});
        if (!blob.size) { toast('Keine Audiodaten aufgenommen.', 'error'); return; }
        await sendVoice(button, target, new File([blob], `kayi-diktat-${Date.now()}.${ext}`, {type:mime}));
      };
      recorder.start(400); button.classList.add('is-listening'); button.textContent = '■';
      toast('Aufnahme läuft – zum Stoppen erneut tippen.', 'info');
    } catch (error) {
      states.delete(button); button.classList.remove('is-listening'); button.textContent = '🎙';
      toast('Browser-Mikrofon blockiert – KAYI öffnet jetzt die Audioaufnahme des Geräts.', 'info');
      nativeAudioCapture(button, target);
    }
  };

  const preparePanelFile = (box, file) => {
    const input = $('[data-field-voice-file]', box), preview = $('[data-field-voice-preview]', box), transcribe = $('[data-field-transcribe]', box), status = $('[data-field-record-status]', box);
    if (input && file && input.files?.[0] !== file) {
      try { const transfer = new DataTransfer(); transfer.items.add(file); input.files = transfer.files; } catch (_) {}
    }
    if (preview && file) { preview.src = URL.createObjectURL(file); preview.hidden = false; }
    if (transcribe) transcribe.hidden = false;
    if (status) { status.textContent = 'Aufnahme bereit. Jetzt mit KI auswerten.'; status.classList.remove('is-live'); }
  };
  const bindPanelInput = (box) => {
    const input = $('[data-field-voice-file]', box); if (!input || input.dataset.androidVoiceBound === '1') return input;
    input.dataset.androidVoiceBound = '1'; input.accept = 'audio/*'; input.setAttribute('capture','microphone');
    input.addEventListener('change', () => { const file = input.files?.[0]; if (file) preparePanelFile(box, file); });
    return input;
  };
  const handlePanelRecord = async (button) => {
    const box = button.closest('[data-field-voice]'); if (!box) return;
    const consent = $('[data-field-voice-consent]', box), status = $('[data-field-record-status]', box), input = bindPanelInput(box);
    if (!consent?.checked) { toast('Bitte zuerst der Sprachaufnahme zustimmen.', 'error'); consent?.focus(); return; }
    const current = states.get(button);
    if (current?.recorder?.state === 'recording') { current.recorder.stop(); return; }
    if (!window.MediaRecorder || !navigator.mediaDevices?.getUserMedia) { input?.click(); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({audio:true}); const chunks = [];
      const preferred = MediaRecorder.isTypeSupported?.('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : '';
      const recorder = new MediaRecorder(stream, preferred ? {mimeType:preferred} : undefined);
      states.set(button, {recorder,stream});
      recorder.ondataavailable = (event) => { if (event.data?.size) chunks.push(event.data); };
      recorder.onstop = () => {
        stream.getTracks().forEach((track)=>track.stop()); states.delete(button); button.textContent = '🎙 Neue Aufnahme';
        const mime = recorder.mimeType || 'audio/webm', ext = mime.includes('ogg') ? 'ogg' : (mime.includes('mp4') ? 'm4a' : 'webm');
        const file = new File([new Blob(chunks,{type:mime})], `einsatz-${Date.now()}.${ext}`, {type:mime}); preparePanelFile(box,file);
      };
      recorder.start(400); button.textContent = '■ Aufnahme stoppen'; if (status) { status.textContent='Aufnahme läuft …'; status.classList.add('is-live'); }
    } catch (_) {
      if (status) status.textContent = 'Browser-Mikrofon blockiert. Audioaufnahme des Geräts wird geöffnet …';
      toast('Browser-Mikrofon blockiert – Audioaufnahme des Geräts wird geöffnet.', 'info'); input?.click();
    }
  };

  // Capture phase intentionally wins over every legacy SpeechRecognition/getUserMedia listener.
  document.addEventListener('click', (event) => {
    const voiceButton = event.target.closest?.('[data-voice-button]');
    const panelRecord = event.target.closest?.('[data-field-record]');
    if (!voiceButton && !panelRecord) return;
    event.preventDefault(); event.stopPropagation(); event.stopImmediatePropagation();
    if (voiceButton) handleVoiceButton(voiceButton);
    else handlePanelRecord(panelRecord);
  }, true);

  const enable = () => {
    $$('[data-voice-button]').forEach((button) => { button.hidden = false; button.disabled = false; button.title = 'Spracheingabe'; });
    $$('[data-field-voice]').forEach(bindPanelInput);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', enable); else enable();
})();
'''
        write(rel, text)


def patch_cache_versions() -> None:
    templates = [
        ROOT / "templates" / "rebuild" / "appointment_detail.html",
        ROOT / "templates" / "rebuild" / "field_quick_job.html",
    ]
    for path in templates:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        text = re.sub(r"(field-authorization\.(?:css|js)' %\}\?v=)[^\"']+", rf"\g<1>{VERSION}", text)
        path.write_text(text, encoding="utf-8")


def install_tests() -> None:
    write("tests/test_android_voice_capture_hotfix.py", r'''from pathlib import Path
from django.test import SimpleTestCase


class AndroidVoiceCaptureHotfixTests(SimpleTestCase):
    def test_generic_voice_endpoint_exists_before_appointment_creation(self):
        root = Path(__file__).resolve().parents[1]
        views = (root / "erp/assistant_views.py").read_text(encoding="utf-8")
        urls = (root / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        self.assertIn("def field_voice_transcribe(request):", views)
        self.assertIn('path("field/voice/transcribe/"', urls)

    def test_field_voice_uses_media_recorder_and_native_audio_fallback(self):
        root = Path(__file__).resolve().parents[1]
        js = (root / "static/js/field-authorization.js").read_text(encoding="utf-8")
        self.assertIn("KAYI ANDROID VOICE CAPTURE HOTFIX 2026-08-11", js)
        self.assertIn("navigator.mediaDevices?.getUserMedia", js)
        self.assertIn("capture','microphone", js)
        self.assertIn("/field/voice/transcribe/", js)
        self.assertIn("stopImmediatePropagation", js)

    def test_quick_job_and_appointment_cache_bust_field_voice_asset(self):
        root = Path(__file__).resolve().parents[1]
        for rel in ("templates/rebuild/field_quick_job.html", "templates/rebuild/appointment_detail.html"):
            text = (root / rel).read_text(encoding="utf-8")
            self.assertIn("20260811-7", text)
''')


def guard() -> None:
    views = read("erp/assistant_views.py")
    urls = read("erp/rebuild_urls.py")
    js = read("static/js/field-authorization.js")
    quick = read("templates/rebuild/field_quick_job.html")
    appointment = read("templates/rebuild/appointment_detail.html")
    for needle in ("def field_voice_transcribe(request):", "OPENAI_TRANSCRIBE_MODEL"):
        if needle not in views:
            raise RuntimeError(f"Android voice backend missing: {needle}")
    if 'path("field/voice/transcribe/"' not in urls:
        raise RuntimeError("Generic field voice route missing")
    for needle in (MARKER, "MediaRecorder", "capture','microphone", "/field/voice/transcribe/", "stopImmediatePropagation"):
        if needle not in js:
            raise RuntimeError(f"Android voice frontend missing: {needle}")
    if VERSION not in quick or VERSION not in appointment:
        raise RuntimeError("Field authorization voice asset cache version was not bumped")


patch_backend()
patch_javascript()
patch_cache_versions()
install_tests()
guard()
print("KAYI Android voice hotfix installed: every field mic uses recorded audio, system-recorder fallback and generic server transcription.")
