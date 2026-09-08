from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ABauV3HistoryLifecycleCloseoutSourceTests(SimpleTestCase):
    def read(self, rel):
        return (ROOT / rel).read_text(encoding="utf-8")

    def test_closeout_is_wired_before_phase2_source_copy(self):
        customer_compat = self.read("scripts/tooltime_customer_detail_regression_compat.py")
        self.assertIn("ab_bau_v3_history_lifecycle_closeout.py", customer_compat)
        self.assertIn("tooltime_receipt_interaction_fix.py", customer_compat)
        self.assertLess(
            customer_compat.index("tooltime_receipt_interaction_fix.py"),
            customer_compat.index("ab_bau_v3_history_lifecycle_closeout.py"),
        )

    def test_closeout_augments_current_v3_instead_of_restoring_stale_templates(self):
        closeout = self.read("scripts/ab_bau_v3_history_lifecycle_closeout.py")
        for marker in (
            "AB_V3_HISTORY_CUSTOMER_CONTEXT",
            "AB_V3_HISTORY_PROJECT_CONTEXT",
            "next-customer-quote-create",
            "next-customer-invoice-create",
            "next-project-lifecycle",
            "data-ab-v3-customer-history",
            "data-ab-v3-project-history",
            "next-room-planner",
            "field-user finance guard",
        ):
            self.assertIn(marker, closeout)
        self.assertNotIn("CUSTOMER_TEMPLATE = r'''", closeout)
        self.assertNotIn("PROJECT_TEMPLATE = r'''", closeout)

    def test_stale_history_regressions_are_explicitly_forbidden(self):
        closeout = self.read("scripts/ab_bau_v3_history_lifecycle_closeout.py")
        self.assertIn("next-appointment-create", closeout)
        self.assertIn("legacy configurator", closeout)
        self.assertIn("Direktdokumente · Kunde", closeout)
        self.assertIn("exclude(title=direct_title)", closeout)
        self.assertIn("20260908-v3-closeout1", closeout)
