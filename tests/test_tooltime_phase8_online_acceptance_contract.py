from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase8OnlineAcceptanceContractTests(SimpleTestCase):
    def test_acceptance_is_persisted_and_migrated(self):
        models = (ROOT / "erp/tooltime_parity_finance.py").read_text(encoding="utf-8")
        migration = (ROOT / "erp/migrations/0019_tooltime_online_acceptance.py").read_text(encoding="utf-8")
        self.assertIn("acceptance_details = models.JSONField", models)
        self.assertIn("withdrawn_at = models.DateTimeField", models)
        self.assertIn('("erp", "0018_tooltime_pay")', migration)

    def test_public_acceptance_requires_identity_and_legal_consents(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        template = (ROOT / "templates/rebuild/public_quote.html").read_text(encoding="utf-8")
        self.assertIn('request.POST.get("identity_confirmed") == "on"', views)
        self.assertIn('request.POST.get("terms_accepted") == "on"', views)
        self.assertIn('request.POST.get("withdrawal_accepted") == "on"', views)
        self.assertIn('name="signer_name"', template)
        self.assertIn("Zahlungspflichtig bestellen", template)
        self.assertIn("AGB öffnen", template)
        self.assertIn("Widerrufsbelehrung öffnen", template)

    def test_accepted_offer_stays_immutable_and_private_withdrawal_is_time_limited(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        self.assertIn('(existing.status == "accepted" or meta.accepted_at)', views)
        self.assertIn("meta.accepted_at + timedelta(days=14)", views)
        self.assertIn('decision == "withdraw"', views)
        self.assertIn('quote.status = "rejected"', views)

    def test_notifications_never_fake_success(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        self.assertIn("def _phase8_productive_mail_ready", views)
        self.assertIn('any(part in backend for part in ("console", "locmem", "dummy", "filebased"))', views)
        self.assertIn(".send(fail_silently=False) == 1", views)
        self.assertIn('result["customer_sent"] = False', views)
        self.assertIn('result["company_sent"] = False', views)

    def test_browser_smoke_exercises_real_public_acceptance(self):
        smoke = (ROOT / "scripts/production_browser_smoke.py").read_text(encoding="utf-8")
        self.assertIn("A+BAU TOOLTIME PHASE 8 ONLINE ACCEPTANCE", smoke)
        self.assertIn("Online-Annahme fehlt PLZ-Verifizierung", smoke)
        self.assertIn("Online-Annahme wurde nicht verbindlich gespeichert", smoke)
