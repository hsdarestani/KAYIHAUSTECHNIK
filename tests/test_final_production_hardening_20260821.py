from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class FinalProductionHardeningTests(SimpleTestCase):
    def test_german_runtime_is_global_and_preserves_iso_submission(self):
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        js = (ROOT / "static/js/ab-bau-production-hardening.js").read_text(encoding="utf-8")
        self.assertIn('lang="de"', base)
        self.assertIn("ab-bau-production-hardening.css", base)
        self.assertIn("ab-bau-production-hardening.js", base)
        for marker in ("TT.MM.JJJJ", "HH:MM", "germanToIso", "isoToGerman", "Datei auswählen", "Keine Datei ausgewählt", 'input[type="date"]', 'input[type="time"]'):
            self.assertIn(marker, js)
        for marker in ("Monday","Montag","Friday","Freitag","Tue","Di"):
            self.assertIn(marker, js)

    def test_primary_actions_use_ab_bau_gold(self):
        css = (ROOT / "static/css/ab-bau-production-hardening.css").read_text(encoding="utf-8")
        js = (ROOT / "static/js/ab-bau-production-hardening.js").read_text(encoding="utf-8")
        self.assertIn("#c9a13b", css)
        self.assertIn("ab-primary-action", css)
        for marker in ("Neues Projekt", "Neues Angebot", "Neue Rechnung", "Artikel hinzufügen", "Speichern"):
            self.assertIn(marker, js)

    def test_invoice_pay_ui_uses_real_provider_readiness_and_has_no_dead_activation_banner(self):
        views = (ROOT / "erp/tooltime_invoices_exact.py").read_text(encoding="utf-8")
        template = (ROOT / "templates/rebuild/invoices.html").read_text(encoding="utf-8")
        self.assertIn("provider_ready as pay_provider_ready", views)
        self.assertIn("pay_active, _pay_reason = pay_provider_ready(org)", views)
        self.assertNotIn("Jetzt aktivieren", template)
        if "next-invoice-payment-link" in template:
            self.assertIn("{% if pay_active %}", template)

    def test_review_queue_cannot_show_old_and_new_snapshots_in_two_status_buckets(self):
        source = (ROOT / "erp/manager_review_views.py").read_text(encoding="utf-8")
        self.assertIn("latest_by_visit", source)
        self.assertIn('("event", str(event_id))', source)
        self.assertIn("current = list(latest_by_visit.values())", source)
        self.assertNotIn("pending = list(qs.filter(metadata__status=PENDING)", source)

    def test_finance_cost_and_margin_come_from_purchase_prices_not_revenue(self):
        source = (ROOT / "erp/rebuild_views.py").read_text(encoding="utf-8")
        self.assertIn('purchase = _money(getattr(meta, "purchase_price", 0))', source)
        self.assertIn('cost += _money(item.quantity) * purchase', source)
        self.assertIn('margin = net - cost', source)
        self.assertIn('costs = sum((row["cost"] for row in invoice_totals)', source)
        self.assertNotIn("costs = revenue\n", source)

    def test_room_planner_and_technician_voice_ai_guards_still_exist(self):
        planner = (ROOT / "templates/rebuild/room_planner.html").read_text(encoding="utf-8")
        appointment = (ROOT / "templates/rebuild/appointment_detail.html").read_text(encoding="utf-8")
        field_home = (ROOT / "templates/rebuild/field_home.html").read_text(encoding="utf-8")
        for marker in ("data-rp-canvas", "data-rp-open-vision", "data-rp-add-object"):
            self.assertIn(marker, planner)
        for marker in ("data-field-voice", "data-field-record", "data-field-transcribe", "Kundenunterschrift zum Abschluss", "Einsatz abschließen & PDF erstellen"):
            self.assertIn(marker, appointment)
        self.assertIn("Vor Ort in einem Ablauf", field_home)

    def test_sms_send_controls_are_suppressed_outside_settings_until_provider_is_ready(self):
        js = (ROOT / "static/js/ab-bau-production-hardening.js").read_text(encoding="utf-8")
        self.assertIn('!location.pathname.startsWith("/settings")', js)
        self.assertIn("data.abSmsDisabled", js.replace("dataset.abSmsDisabled", "data.abSmsDisabled"))
