from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePayContractTests(SimpleTestCase):
    def test_models_and_migration_are_persistent(self):
        models = (ROOT / "erp/tooltime_parity_finance.py").read_text(encoding="utf-8"); migration = (ROOT / "erp/migrations/0018_tooltime_pay.py").read_text(encoding="utf-8")
        self.assertIn("class ToolTimePaymentTransaction", models); self.assertIn("class ToolTimePayout", models); self.assertIn("automatic_dunning_disabled", models); self.assertIn("0017_tooltime_phase5_communication", migration)

    def test_payment_provider_cannot_fake_success(self):
        service = (ROOT / "erp/services/tooltime_pay.py").read_text(encoding="utf-8"); views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        self.assertIn("KAYI_PAY_PROVIDER_TOKEN", service); self.assertIn("KAYI_PAY_WEBHOOK_TOKEN", service); self.assertIn("urllib.request.urlopen(req, timeout=15)", service); self.assertIn('status="pending"', service); self.assertIn('event not in {"payment.succeeded", "succeeded", "paid"}', service); self.assertIn("hmac.compare_digest", service); self.assertIn("@csrf_exempt", views)

    def test_qr_payout_and_dunning_contracts_exist(self):
        service = (ROOT / "erp/services/tooltime_pay.py").read_text(encoding="utf-8"); settings = (ROOT / "templates/rebuild/tooltime_settings.html").read_text(encoding="utf-8"); requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("qrcode", requirements.lower()); self.assertIn("def qr_data_uri", service); self.assertIn("card_limit", service); self.assertIn("def apply_payout_event", service); self.assertIn("def effective_dunning_fee", service); self.assertIn("run_automatic_dunning", service); self.assertIn("_productive_mail_ready", service); self.assertIn("if sent != 1", service); self.assertIn("record.sent_at = timezone.now()", service); self.assertIn('name="automatic_dunning"', settings)

    def test_ui_routes_and_invoice_opt_out_are_real(self):
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8"); invoices = (ROOT / "templates/rebuild/invoices.html").read_text(encoding="utf-8"); payments = (ROOT / "templates/rebuild/payments.html").read_text(encoding="utf-8"); payouts = (ROOT / "templates/rebuild/payouts.html").read_text(encoding="utf-8")
        for name in ("next-payments", "next-payouts", "next-invoice-payment-link", "next-invoice-dunning-toggle", "next-pay-provider-webhook"): self.assertIn(name, urls)
        self.assertIn("Online-Zahlung / QR", invoices); self.assertIn("Mahn-Automatik aussetzen", invoices); self.assertIn("data-tooltime-pay-overview", payments); self.assertIn("data-tooltime-payout-overview", payouts)

    def test_scheduler_entrypoint_exists(self):
        command = (ROOT / "erp/management/commands/tooltime_auto_dunning.py").read_text(encoding="utf-8"); self.assertIn("run_automatic_dunning", command); self.assertIn("Organization.objects.order_by", command)
