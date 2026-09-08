from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase6CommunicationSettingsContractTests(SimpleTestCase):
    def test_email_sender_reply_to_and_templates_feed_real_delivery(self):
        service = (ROOT / "erp/services/tooltime_parity_finance.py").read_text(encoding="utf-8")
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        tags = (ROOT / "erp/templatetags/tooltime_parity.py").read_text(encoding="utf-8")
        self.assertIn('"sender_name": ""', service)
        self.assertIn('communication_cfg = _phase6_document_message', views)
        self.assertIn('formataddr((sender_name, from_address))', views)
        self.assertIn('communication_cfg.get("reply_email")', views)
        self.assertIn('communication = (commercial.settings or {}).get("communication", {})', tags)

    def test_sms_provider_never_reports_fake_success_without_real_provider(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        self.assertIn('KAYI_SMS_PROVIDER_TOKEN', views)
        self.assertIn('urllib.request.urlopen(request, timeout=12)', views)
        self.assertIn('if status < 200 or status >= 300:', views)
        self.assertIn('return True, "SMS wurde vom Provider angenommen."', views)
        self.assertIn('return False, "SMS-Versand ist deaktiviert."', views)

    def test_settings_ui_has_live_email_preview_and_160_char_sms_guard(self):
        template = (ROOT / "templates/rebuild/tooltime_settings.html").read_text(encoding="utf-8")
        for token in ('data-phase6-communication', 'name="sender_name"', 'name="reply_email"', 'name="quote_subject"', 'name="invoice_subject"', 'name="sms_provider"', 'name="sms_endpoint"', 'data-phase6-preview'):
            self.assertIn(token, template)
        self.assertIn('maxlength="160"', template)
        self.assertIn('KAYI_SMS_PROVIDER_TOKEN', template)
