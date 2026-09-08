from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from erp import models as m
from erp.assistant_orchestrator import AgentPlanError, execute_steps, looks_like_workflow

ROOT = Path(__file__).resolve().parents[1]


class ABBauAgentContractTests(SimpleTestCase):
    def test_complex_creation_commands_are_detected(self):
        self.assertTrue(looks_like_workflow("Erstelle einen Kunden, ein Projekt, ein Angebot und eine Rechnung"))
        self.assertTrue(looks_like_workflow("create customer and project and quote"))
        self.assertTrue(looks_like_workflow("یه مشتری بساز و براش پروژه و invoice بساز"))
        self.assertFalse(looks_like_workflow("Öffne die Kundenliste"))

    def test_png_logo_is_installed_and_referenced(self):
        self.assertTrue((ROOT / "static/brand/ab-bau-logo.png").exists())
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        self.assertIn("brand/ab-bau-logo.png", base)
        self.assertNotIn("brand/ab-bau-logo.webp", base)

    def test_single_confirm_ui_and_execute_route_exist(self):
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        js = (ROOT / "static/js/kayi-next.js").read_text(encoding="utf-8")
        self.assertIn("data-assistant-execute-url", base)
        self.assertIn('path("assistant/execute/"', urls)
        self.assertIn("Alles bestätigen & ausführen", js)
        self.assertIn("plan_token", js)


class ABBauAgentExecutionTests(TestCase):
    def setUp(self):
        self.org = m.Organization.objects.create(name="A+Bau Agent Test")
        self.user = get_user_model().objects.create_user(username="agent-test", password="x")

    def workflow(self):
        empty = []
        common = {"priority":"normal","status":"draft","valid_days":30,"due_days":14,"tax_code":"19","discount_type":"percent","discount_value":0,"items":empty}
        return {"title":"Kompletter Vorgang","confirmation_text":"Alles anlegen?","steps":[
            {"id":"customer_1","type":"create_customer","parent_ref":"","parent_id":0,"source_ref":"","source_id":0,"customer_type":"private","company":"","salutation":"Herr","first_name":"Max","last_name":"Mustermann","email":"max@example.test","phone":"","mobile":"","street":"","postal_code":"","city":"Frankfurt","country":"DE","title":"","description":"","intro_text":"","notes":"",**common},
            {"id":"project_1","type":"create_project","parent_ref":"customer_1","parent_id":0,"source_ref":"","source_id":0,"customer_type":"private","company":"","salutation":"","first_name":"","last_name":"","email":"","phone":"","mobile":"","street":"","postal_code":"","city":"","country":"DE","title":"Badmodernisierung","description":"Komplettbad","intro_text":"","notes":"",**common},
            {"id":"quote_1","type":"create_quote","parent_ref":"project_1","parent_id":0,"source_ref":"","source_id":0,"customer_type":"private","company":"","salutation":"","first_name":"","last_name":"","email":"","phone":"","mobile":"","street":"","postal_code":"","city":"","country":"DE","title":"","description":"","intro_text":"","notes":"",**common},
            {"id":"invoice_1","type":"create_invoice","parent_ref":"project_1","parent_id":0,"source_ref":"quote_1","source_id":0,"customer_type":"private","company":"","salutation":"","first_name":"","last_name":"","email":"","phone":"","mobile":"","street":"","postal_code":"","city":"","country":"DE","title":"","description":"","intro_text":"","notes":"",**common},
        ]}

    def test_customer_project_quote_invoice_chain_executes_atomically(self):
        results = execute_steps(self.org, self.user, self.workflow())
        self.assertEqual(len(results), 4)
        customer = m.Customer.objects.get(organization=self.org)
        project = m.Project.objects.get(organization=self.org)
        quote = m.Quote.objects.get(organization=self.org)
        invoice = m.Invoice.objects.get(organization=self.org)
        self.assertEqual(project.customer_id, customer.pk)
        self.assertEqual(quote.project_id, project.pk)
        self.assertEqual(invoice.project_id, project.pk)
        self.assertEqual(invoice.quote_id, quote.pk)
        self.assertEqual(project.status, "invoiced")
        self.assertTrue(m.CommercialDocumentSettings.objects.filter(quote=quote).exists())
        self.assertTrue(m.CommercialDocumentSettings.objects.filter(invoice=invoice).exists())

    def test_failure_rolls_back_whole_chain(self):
        workflow = self.workflow()
        workflow["steps"][1]["parent_ref"] = "missing"
        with self.assertRaises(AgentPlanError):
            execute_steps(self.org, self.user, workflow)
        self.assertEqual(m.Customer.objects.filter(organization=self.org).count(), 0)
        self.assertEqual(m.Project.objects.filter(organization=self.org).count(), 0)
