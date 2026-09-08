from datetime import timedelta
from decimal import Decimal
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone
from erp.models import CalendarEvent, CatalogItem, Customer, Employee, Invoice, InvoiceItem, Organization, Project, Quote, QuoteItem, Task
from erp.services.numbering import next_number


class Command(BaseCommand):
    help = "Erstellt optionale Demo-Daten."

    def handle(self, *args, **options):
        org = Organization.objects.first()
        if not org:
            org = Organization.objects.create(name="A+Bau")
        if Customer.objects.filter(organization=org).exists():
            self.stdout.write("Daten vorhanden; Demo übersprungen.")
            return
        user = User.objects.first()
        customer = Customer.objects.create(organization=org, number=next_number(org, "customer"), company="Muster Hausverwaltung GmbH", email="kontakt@example.de", phone="+49 69 000000", street="Musterstraße 12", postal_code="60311", city="Frankfurt am Main", type=Customer.Type.PROPERTY_MANAGER)
        employee = Employee.objects.create(organization=org, employee_number=next_number(org, "employee"), first_name="Ahmet", last_name="A+Bau", trade="Sanitär & Heizung", hourly_rate=Decimal("68.00"), hourly_cost=Decimal("32.00"))
        project = Project.objects.create(organization=org, number=next_number(org, "project"), title="Badsanierung Musterstraße", customer=customer, manager=employee, status=Project.Status.IN_PROGRESS, priority=Project.Priority.HIGH, description="Komplette Modernisierung des Badezimmers inklusive Sanitär, Fliesen und Elektrokoordination.", planned_start=timezone.localdate(), planned_end=timezone.localdate() + timedelta(days=21), budget=Decimal("18500"), progress=35)
        project.members.add(employee)
        Task.objects.create(organization=org, project=project, title="Materiallieferung prüfen", assigned_to=employee, due_at=timezone.now() + timedelta(days=1), priority=Project.Priority.HIGH)
        CalendarEvent.objects.create(organization=org, project=project, title="Baustellentermin", starts_at=timezone.now() + timedelta(hours=2), ends_at=timezone.now() + timedelta(hours=4), location="Musterstraße 12, Frankfurt", created_by=user)
        item = CatalogItem.objects.create(organization=org, code="SAN-001", name="Montage Sanitärgegenstand", description="Montage einschließlich Anschluss und Funktionsprüfung", unit="Stk.", sales_price=Decimal("185.00"))
        quote = Quote.objects.create(organization=org, project=project, number=next_number(org, "quote"), status=Quote.Status.ACCEPTED, created_by=user)
        QuoteItem.objects.create(quote=quote, position=1, catalog_item=item, code=item.code, description=item.description, quantity=2, unit=item.unit, unit_price=item.sales_price)
        invoice = Invoice.objects.create(organization=org, project=project, quote=quote, number=next_number(org, "invoice"), status=Invoice.Status.SENT, issue_date=timezone.localdate(), due_date=timezone.localdate() + timedelta(days=14), created_by=user)
        InvoiceItem.objects.create(invoice=invoice, position=1, catalog_item=item, code=item.code, description=item.description, quantity=2, unit=item.unit, unit_price=item.sales_price)
        self.stdout.write(self.style.SUCCESS("Demo-Daten erstellt."))
