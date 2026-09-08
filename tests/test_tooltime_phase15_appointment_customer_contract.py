from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase15AppointmentCustomerContractTests(SimpleTestCase):
    def test_native_customer_relation_and_migration_are_assembled(self):
        models = (ROOT / "erp/models.py").read_text(encoding="utf-8")
        migration = (ROOT / "erp/migrations/0020_calendar_event_customer.py").read_text(encoding="utf-8")
        views = (ROOT / "erp/rebuild_views.py").read_text(encoding="utf-8")
        detail = (ROOT / "templates/rebuild/appointment_detail.html").read_text(encoding="utf-8")

        self.assertIn('related_name="calendar_events"', models)
        self.assertIn('("erp", "0019_tooltime_online_acceptance")', migration)
        self.assertIn('name="customer"', migration)
        self.assertIn("event.customer = selected_customer", views)
        self.assertIn("updated.customer = selected_customer", views)
        self.assertIn("Q(customer_id=int(customer_filter))", views)
        self.assertIn("Q(customer__company__icontains=query_filter)", views)
        self.assertIn("_appointment_customer_address", views)
        self.assertIn("event.customer.display_name", detail)
