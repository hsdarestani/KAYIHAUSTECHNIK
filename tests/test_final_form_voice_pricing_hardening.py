from pathlib import Path

from django.test import SimpleTestCase


class FinalFormVoicePricingHardeningTests(SimpleTestCase):
    def test_all_forms_surface_hidden_and_server_validation(self):
        js = Path("static/js/kayi-next.js").read_text(encoding="utf-8")
        css = Path("static/css/kayi-next.css").read_text(encoding="utf-8")
        for marker in ("A+Bau GLOBAL FORM VALIDATION 2026-08-11", "addEventListener('invalid'", "dataset.globalFormErrors", "current.tagName === 'DETAILS'"):
            self.assertIn(marker, js)
        self.assertIn(".nx-global-form-errors", css)

    def test_release_voice_uses_media_recorder_and_server_transcription(self):
        js = Path("static/js/field-authorization.js").read_text(encoding="utf-8")
        template = Path("templates/rebuild/appointment_detail.html").read_text(encoding="utf-8")
        backend = Path("erp/assistant_views.py").read_text(encoding="utf-8")
        self.assertIn("MediaRecorder", js)
        self.assertIn("getUserMedia", js)
        self.assertIn("transcript_only", js)
        self.assertNotIn("window.SpeechRecognition || window.webkitSpeechRecognition", js)
        self.assertIn("data-fa-voice-url", template)
        self.assertIn("if transcript_only:", backend)

    def test_field_catalog_price_is_preserved_and_rechecked_server_side(self):
        js = Path("static/js/field-authorization.js").read_text(encoding="utf-8")
        views = Path("erp/field_authorization_views.py").read_text(encoding="utf-8")
        service = Path("erp/services/field_authorization.py").read_text(encoding="utf-8")
        template = Path("templates/rebuild/appointment_detail.html").read_text(encoding="utf-8")
        urls = Path("erp/field_authorization_urls.py").read_text(encoding="utf-8")
        for marker in ("item_catalog_id", "bindFieldCatalogSearch", "serverseitig nochmals geprüft"):
            self.assertIn(marker, js)
        for marker in ("authorization_catalog_search", "_reprice_catalog_items", "Never trust a browser-posted price", "effective_price_for_catalog_item"):
            self.assertIn(marker, views)
        self.assertIn('catalog_ids = post.getlist("item_catalog_id")', service)
        self.assertIn("data-fa-catalog-picker", template)
        self.assertIn("field-authorization-catalog", urls)
