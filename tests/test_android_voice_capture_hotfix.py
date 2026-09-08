from pathlib import Path
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
        self.assertIn("A+Bau ANDROID VOICE CAPTURE HOTFIX 2026-08-11", js)
        self.assertIn("navigator.mediaDevices?.getUserMedia", js)
        self.assertIn("capture','microphone", js)
        self.assertIn("/field/voice/transcribe/", js)
        self.assertIn("stopImmediatePropagation", js)

    def test_quick_job_and_appointment_cache_bust_field_voice_asset(self):
        root = Path(__file__).resolve().parents[1]
        for rel in ("templates/rebuild/field_quick_job.html", "templates/rebuild/appointment_detail.html"):
            text = (root / rel).read_text(encoding="utf-8")
            self.assertRegex(text, r"field-authorization\.css.*\?v=[0-9A-Za-z._-]+")
            self.assertTrue(("field-authorization.js" in text and "?v=" in text) or ("MediaRecorder" in text and "data-intake-record" in text))
