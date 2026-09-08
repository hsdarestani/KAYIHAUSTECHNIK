from __future__ import annotations

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone

from . import models as m
from .rebuild_views import _import_tooltime_rows, _money, _norm, _org, _pick, _read_table, _unique_number


STATUS_MAP = {
    "anfrage": "inquiry",
    "planung": "planning",
    "angebot": "quoted",
    "beauftragt": "confirmed",
    "bestätigt": "confirmed",
    "bestaetigt": "confirmed",
    "in ausführung": "in_progress",
    "in ausfuehrung": "in_progress",
    "ausführung": "in_progress",
    "ausfuehrung": "in_progress",
    "wartet": "waiting",
    "abnahme": "review",
    "abgerechnet": "invoiced",
    "abgeschlossen": "completed",
    "storniert": "cancelled",
}


def _customer_for_row(org, row):
    number = _pick(row, "Kundennummer", "Customer Number", "Customer No")
    name = _pick(row, "Kunde", "Kundenname", "Customer", "Customer Name")
    customer = m.Customer.objects.filter(organization=org, number=number).first() if number else None
    if customer is None and name:
        customer = m.Customer.objects.filter(organization=org).filter(
            Q(company__iexact=name) | Q(last_name__iexact=name)
        ).first()
    if customer is None:
        customer = m.Customer.objects.create(
            organization=org,
            number=number or _unique_number(m.Customer, org, "K"),
            company=name or "ToolTime Import",
        )
    return customer


def _parse_date(value):
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return timezone.datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    try:
        return timezone.datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _parse_datetime(date_value, time_value=""):
    date_value = (date_value or "").strip()
    time_value = (time_value or "").strip()
    if "T" in date_value or (" " in date_value and ":" in date_value):
        try:
            parsed = timezone.datetime.fromisoformat(date_value.replace("Z", "+00:00"))
            return parsed if timezone.is_aware(parsed) else timezone.make_aware(parsed)
        except ValueError:
            pass
    date = _parse_date(date_value)
    if date is None:
        return None
    time = timezone.datetime.min.time()
    if time_value:
        for fmt in ("%H:%M", "%H:%M:%S"):
            try:
                time = timezone.datetime.strptime(time_value, fmt).time()
                break
            except ValueError:
                pass
    return timezone.make_aware(timezone.datetime.combine(date, time))


def _import_projects(org, rows):
    created = updated = skipped = 0
    for source in rows:
        row = _norm(source)
        number = _pick(row, "Projektnummer", "Projekt-Nr", "Project Number", "Auftragsnummer")
        title = _pick(row, "Projekt", "Projekttitel", "Titel", "Project", "Auftrag") or "ToolTime Projekt"
        customer = _customer_for_row(org, row)
        project = m.Project.objects.filter(organization=org, number=number).first() if number else None
        values = {
            "title": title,
            "customer": customer,
            "description": _pick(row, "Beschreibung", "Description", "Notiz", "Notes"),
            "external_reference": _pick(row, "Referenz", "External Reference", "Auftragsreferenz"),
        }
        raw_status = _pick(row, "Status", "Project Status").lower()
        status = STATUS_MAP.get(raw_status)
        if project:
            for key, value in values.items():
                if value:
                    setattr(project, key, value)
            if status:
                project.status = status
            project.save()
            updated += 1
        else:
            project = m.Project.objects.create(
                organization=org,
                number=number or _unique_number(m.Project, org, "P"),
                status=status or "inquiry",
                **values,
            )
            created += 1

        site_street = _pick(row, "Einsatzort Straße", "Einsatzort Strasse", "Site Street", "Objekt Straße")
        site_city = _pick(row, "Einsatzort Ort", "Site City", "Objekt Ort")
        site_postal = _pick(row, "Einsatzort PLZ", "Site ZIP", "Objekt PLZ")
        if site_street and not project.object_location_id:
            location = m.ObjectLocation.objects.filter(
                organization=org, customer=customer, street=site_street, postal_code=site_postal, city=site_city
            ).first()
            if location is None:
                location = m.ObjectLocation.objects.create(
                    organization=org, customer=customer, name="ToolTime Einsatzort",
                    street=site_street, postal_code=site_postal, city=site_city,
                )
            project.object_location = location
            project.save(update_fields=["object_location", "updated_at"])
    return {"created": created, "updated": updated, "skipped": skipped, "rows": len(rows)}


def _import_appointments(org, user, rows):
    created = updated = skipped = 0
    for source in rows:
        row = _norm(source)
        project_number = _pick(row, "Projektnummer", "Project Number", "Auftragsnummer")
        project = m.Project.objects.filter(organization=org, number=project_number).first() if project_number else None
        if project is None:
            skipped += 1
            continue
        title = _pick(row, "Termin", "Titel", "Title", "Betreff") or project.title
        date_value = _pick(row, "Datum", "Date", "Startdatum", "Start Date")
        start_value = _pick(row, "Start", "Von", "Startzeit", "Start Time")
        end_date_value = _pick(row, "Enddatum", "End Date") or date_value
        end_value = _pick(row, "Ende", "Bis", "Endzeit", "End Time")
        starts = _parse_datetime(date_value, start_value)
        ends = _parse_datetime(end_date_value, end_value)
        if starts is None:
            skipped += 1
            continue
        if ends is None or ends <= starts:
            ends = starts + timedelta(hours=1)
        existing = m.CalendarEvent.objects.filter(
            organization=org, project=project, title=title, starts_at=starts
        ).first()
        values = {
            "ends_at": ends,
            "location": _pick(row, "Ort", "Location", "Einsatzort"),
            "notes": _pick(row, "Notiz", "Notizen", "Notes", "Beschreibung"),
        }
        if existing:
            for key, value in values.items():
                if value:
                    setattr(existing, key, value)
            existing.save()
            updated += 1
        else:
            m.CalendarEvent.objects.create(
                organization=org, project=project, title=title, starts_at=starts,
                created_by=user, **values,
            )
            created += 1
    return {"created": created, "updated": updated, "skipped": skipped, "rows": len(rows)}


def _import_expenses(org, rows):
    created = updated = skipped = 0
    for source in rows:
        row = _norm(source)
        supplier = _pick(row, "Lieferant", "Supplier", "Vendor") or "ToolTime Import"
        description = _pick(row, "Beschreibung", "Description", "Beleg", "Receipt") or "Importierte Ausgabe"
        date = _parse_date(_pick(row, "Datum", "Date", "Belegdatum")) or timezone.localdate()
        amount = _money(_pick(row, "Netto", "Net Amount", "Betrag Netto", "Amount"))
        project_number = _pick(row, "Projektnummer", "Project Number")
        project = m.Project.objects.filter(organization=org, number=project_number).first() if project_number else None
        existing = m.Expense.objects.filter(
            organization=org, supplier=supplier, description=description, expense_date=date, amount_net=amount
        ).first()
        if existing:
            updated += 1
            continue
        m.Expense.objects.create(
            organization=org, supplier=supplier, description=description, expense_date=date,
            amount_net=amount, tax_rate=_money(_pick(row, "MwSt", "Tax", "Steuer") or 19),
            category=_pick(row, "Kategorie", "Category"), project=project,
            paid=_pick(row, "Bezahlt", "Paid").lower() in {"1", "true", "ja", "yes", "bezahlt"},
        )
        created += 1
    return {"created": created, "updated": updated, "skipped": skipped, "rows": len(rows)}


@login_required
def migration_import(request):
    org = _org(request)
    summary = None
    errors = []
    if request.method == "POST" and request.FILES.get("file"):
        upload = request.FILES["file"]
        kind = request.POST.get("kind") or "customers"
        try:
            rows = _read_table(upload)
            with transaction.atomic():
                if kind == "projects":
                    summary = _import_projects(org, rows)
                elif kind == "appointments":
                    summary = _import_appointments(org, request.user, rows)
                elif kind == "expenses":
                    summary = _import_expenses(org, rows)
                else:
                    summary = _import_tooltime_rows(org, request.user, kind, rows)
            messages.success(request, f"ToolTime-Import abgeschlossen: {summary['created']} neu, {summary['updated']} aktualisiert, {summary['skipped']} übersprungen.")
        except Exception as exc:
            errors.append(str(exc))
    return render(request, "rebuild/migration.html", {"summary": summary, "errors": errors})
