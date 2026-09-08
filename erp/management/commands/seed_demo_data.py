from __future__ import annotations

import secrets
from datetime import datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from erp.models import CalendarEvent, Customer, Employee, Invoice, InvoiceItem, ObjectLocation, Organization, Payment, Project, Quote, QuoteItem, Supplier, Task, UserProfile


class Command(BaseCommand):
    help = "Erzeugt idempotente Beispieldaten in einem vollständig getrennten Demo-Mandanten."

    def add_arguments(self, parser):
        parser.add_argument("--credentials-file", default="/runtime/demo_credentials.txt")

    @transaction.atomic
    def handle(self, *args, **options):
        org, _ = Organization.objects.get_or_create(name="A+Bau Demo", defaults={"legal_name": "A+Bau Demo GmbH", "settings": {"is_demo": True, "invoice_due_days": 14}})
        if not org.settings.get("is_demo"):
            org.settings = {**org.settings, "is_demo": True}
            org.save(update_fields=["settings", "updated_at"])
        user, created = User.objects.get_or_create(username="demo", defaults={"first_name": "Demo", "last_name": "A+Bau", "email": "demo@kayi.local"})
        credentials = Path(options["credentials_file"])
        if created or not user.has_usable_password():
            password = secrets.token_urlsafe(16)
            user.set_password(password)
            user.save()
            credentials.parent.mkdir(parents=True, exist_ok=True)
            credentials.write_text(f"username=demo\npassword={password}\n", encoding="utf-8")
            credentials.chmod(0o600)
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.organization = org
        profile.role = UserProfile.Role.ADMIN
        profile.is_mobile_worker = True
        profile.save()

        employees = []
        for no, first, last, trade, color in [
            ("D-001", "Mehmet", "Kaya", "Sanitär", "#3b82f6"),
            ("D-002", "Emre", "Yilmaz", "Heizung", "#f59e0b"),
            ("D-003", "Lena", "Schmidt", "Projektleitung", "#10b981"),
        ]:
            employee, _ = Employee.objects.get_or_create(organization=org, employee_number=no, defaults={"first_name": first, "last_name": last, "trade": trade, "color": color, "hourly_rate": Decimal("65")})
            employees.append(employee)
        # A_BAU_IDEMPOTENT_EMPLOYEE_USER_SEED: keep deployments idempotent when this user is already linked.
        existing_employee_for_user = type(employees[0]).objects.filter(user=user).exclude(pk=employees[0].pk).first()
        if existing_employee_for_user is None:
            employees[0].user = user
            employees[0].save(update_fields=["user", "updated_at"])


        customers = []
        for number, company, last, city in [
            ("KD-1001", "", "Müller", "Frankfurt"),
            ("KD-1002", "Klein Immobilien", "Klein", "Offenbach"),
            ("KD-1003", "Öztürk Hausverwaltung", "Öztürk", "Hanau"),
            ("KD-1004", "Schmidt & Partner", "Schmidt", "Aschaffenburg"),
        ]:
            customer, _ = Customer.objects.get_or_create(organization=org, number=number, defaults={"company": company, "first_name": "Anna" if last == "Müller" else "", "last_name": last, "city": city, "email": f"{last.lower()}@example.de"})
            customers.append(customer)
        projects = []
        project_specs = [
            ("P-26031", "Hauswasserstation Müller", customers[0], Project.Status.IN_PROGRESS, 65),
            ("P-26032", "Wartung Heizung Klein", customers[1], Project.Status.CONFIRMED, 35),
            ("P-26033", "Aufmaß Neubau", customers[2], Project.Status.PLANNING, 20),
            ("P-26034", "Badmodernisierung Öztürk", customers[2], Project.Status.REVIEW, 90),
        ]
        for number, title, customer, status, progress in project_specs:
            location, _ = ObjectLocation.objects.get_or_create(organization=org, customer=customer, name="Hauptobjekt", defaults={"street": "Musterstraße 12", "postal_code": "60311", "city": customer.city})
            project, _ = Project.objects.get_or_create(organization=org, number=number, defaults={"title": title, "customer": customer, "object_location": location, "manager": employees[2], "status": status, "progress": progress, "budget": Decimal("12500")})
            project.members.set(employees)
            projects.append(project)

        monday = timezone.localdate() - timedelta(days=timezone.localdate().weekday())
        event_specs = [
            (0, 10, "Hauswasserstation · Müller", projects[0], CalendarEvent.Type.SITE, employees[0]),
            (1, 13, "Rohrbruch Notdienst", projects[0], CalendarEvent.Type.SITE, employees[1]),
            (2, 9, "Wartung Heizung · Klein", projects[1], CalendarEvent.Type.APPOINTMENT, employees[1]),
            (2, 11, "Aufmaß Neubau", projects[2], CalendarEvent.Type.INSPECTION, employees[2]),
            (3, 14, "Kundengespräch · Schmidt", projects[2], CalendarEvent.Type.APPOINTMENT, employees[2]),
            (4, 10, "Materiallieferung", projects[3], CalendarEvent.Type.DELIVERY, employees[0]),
            (4, 15, "Abnahme Bad · Öztürk", projects[3], CalendarEvent.Type.INSPECTION, employees[2]),
        ]
        for day, hour, title, project, event_type, employee in event_specs:
            start = timezone.make_aware(datetime.combine(monday + timedelta(days=day), time(hour, 0)))
            event, _ = CalendarEvent.objects.get_or_create(organization=org, title=title, starts_at=start, defaults={"project": project, "type": event_type, "ends_at": start + timedelta(hours=1), "location": project.object_location.city if project.object_location else "", "created_by": user})
            event.attendees.add(employee)

        for idx, project in enumerate(projects[:3], start=1):
            Task.objects.get_or_create(organization=org, project=project, title=f"Nächster Schritt für {project.title}", defaults={"assigned_to": employees[idx % len(employees)], "due_at": timezone.now() + timedelta(days=idx), "priority": Project.Priority.HIGH if idx == 1 else Project.Priority.NORMAL})

        supplier, _ = Supplier.objects.get_or_create(organization=org, number="L-1001", defaults={"name": "Raab Karcher", "city": "Frankfurt"})
        quote, _ = Quote.objects.get_or_create(organization=org, number="AN-26001", defaults={"project": projects[3], "status": Quote.Status.SENT, "created_by": user})
        QuoteItem.objects.get_or_create(quote=quote, position=1, defaults={"code": "SAN-001", "description": "Demontage und Montage Sanitärobjekte", "quantity": 1, "unit": "psch", "unit_price": Decimal("2400")})
        invoice, _ = Invoice.objects.get_or_create(organization=org, number="RE-26001", defaults={"project": projects[0], "status": Invoice.Status.PARTIAL, "due_date": timezone.localdate() + timedelta(days=10), "created_by": user})
        InvoiceItem.objects.get_or_create(invoice=invoice, position=1, defaults={"description": "Montage Hauswasserstation", "quantity": 1, "unit": "psch", "unit_price": Decimal("1800")})
        Payment.objects.get_or_create(invoice=invoice, reference="DEMO-ANZAHLUNG", defaults={"amount": Decimal("500"), "recorded_by": user})
        self.stdout.write(self.style.SUCCESS("Demo-Mandant mit Kalender-, Projekt- und Finanzdaten ist bereit."))
