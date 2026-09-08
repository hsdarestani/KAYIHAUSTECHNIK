from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
from io import TextIOWrapper
from pathlib import Path
from openpyxl import load_workbook
from django.db import transaction
from erp.models import CatalogItem, Customer, Project, TimeEntry
from erp.services.numbering import next_number


def _decimal(value, default="0") -> Decimal:
    if value in (None, ""):
        return Decimal(default)
    text = str(value).strip().replace("€", "").replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation:
        return Decimal(default)


def import_catalog(path: str, organization) -> dict:
    suffix = Path(path).suffix.lower()
    rows = []
    if suffix == ".xlsx":
        workbook = load_workbook(path, read_only=True, data_only=True)
        sheet = workbook.active
        values = list(sheet.iter_rows(values_only=True))
        if not values:
            return {"created": 0, "updated": 0, "errors": []}
        headers = [str(v or "").strip().lower() for v in values[0]]
        rows = [dict(zip(headers, values_row)) for values_row in values[1:]]
    elif suffix == ".csv":
        with open(path, newline="", encoding="utf-8-sig", errors="replace") as handle:
            sample = handle.read(4096)
            handle.seek(0)
            dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
            rows = list(csv.DictReader(handle, dialect=dialect))
    else:
        raise ValueError("Unterstützt werden CSV und XLSX.")

    aliases = {
        "code": ["code", "nummer", "nr", "artikelnr", "leistungsnummer", "pos"],
        "name": ["name", "bezeichnung", "leistung", "artikel", "kurztext"],
        "description": ["description", "beschreibung", "langtext", "text"],
        "unit": ["unit", "einheit", "me"],
        "sales_price": ["sales_price", "verkaufspreis", "preis", "ep", "netto"],
        "purchase_price": ["purchase_price", "einkaufspreis", "ek"],
        "tax_rate": ["tax_rate", "mwst", "steuer"],
    }

    def value(row, key, default=""):
        normalized = {str(k).strip().lower(): v for k, v in row.items()}
        for alias in aliases[key]:
            if alias in normalized and normalized[alias] not in (None, ""):
                return normalized[alias]
        return default

    created = updated = 0
    errors = []
    with transaction.atomic():
        for index, row in enumerate(rows, start=2):
            code = str(value(row, "code", "")).strip()
            name = str(value(row, "name", "")).strip()
            if not code or not name:
                continue
            try:
                _, was_created = CatalogItem.objects.update_or_create(
                    organization=organization,
                    code=code,
                    defaults={
                        "name": name,
                        "description": str(value(row, "description", "") or "").strip(),
                        "unit": str(value(row, "unit", "Stk.") or "Stk.").strip(),
                        "sales_price": _decimal(value(row, "sales_price", 0)),
                        "purchase_price": _decimal(value(row, "purchase_price", 0)),
                        "tax_rate": _decimal(value(row, "tax_rate", 19), "19"),
                    },
                )
                created += int(was_created)
                updated += int(not was_created)
            except Exception as exc:
                errors.append(f"Zeile {index}: {exc}")
    return {"created": created, "updated": updated, "errors": errors[:50]}


def import_tooltime(path: str, organization, user=None) -> dict:
    """Importiert flexible ToolTime CSV/XLSX Exporte: Kunden, Projekte und Zeiteinträge."""
    suffix = Path(path).suffix.lower()
    if suffix == ".xlsx":
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        rows_raw = list(ws.iter_rows(values_only=True))
        headers = [str(v or "").strip().lower() for v in rows_raw[0]]
        rows = [dict(zip(headers, r)) for r in rows_raw[1:]]
    else:
        with open(path, newline="", encoding="utf-8-sig", errors="replace") as handle:
            sample = handle.read(4096)
            handle.seek(0)
            dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
            rows = list(csv.DictReader(handle, dialect=dialect))

    stats = {"customers": 0, "projects": 0, "time_entries": 0, "errors": []}
    for idx, raw in enumerate(rows, start=2):
        row = {str(k).strip().lower(): v for k, v in raw.items()}
        try:
            customer_name = str(row.get("kunde") or row.get("customer") or row.get("kundenname") or "").strip()
            project_title = str(row.get("projekt") or row.get("project") or row.get("auftrag") or "").strip()
            if not customer_name and not project_title:
                continue
            customer = Customer.objects.filter(organization=organization, company=customer_name).first()
            if not customer:
                customer = Customer.objects.create(organization=organization, number=next_number(organization, "customer"), company=customer_name or "Importierter Kunde")
                stats["customers"] += 1
            external_ref = str(row.get("projektnummer") or row.get("project_id") or row.get("auftragsnummer") or "").strip()
            project = Project.objects.filter(organization=organization, external_reference=external_ref).first() if external_ref else None
            if not project:
                project = Project.objects.create(
                    organization=organization,
                    number=next_number(organization, "project"),
                    title=project_title or external_ref or "Importiertes Projekt",
                    customer=customer,
                    external_reference=external_ref,
                )
                stats["projects"] += 1
        except Exception as exc:
            stats["errors"].append(f"Zeile {idx}: {exc}")
    return stats


def import_customers(path: str, organization) -> dict:
    """Import a A+Bau customer register without deleting existing customer data.

    Supported headers include the legacy register fields used by A+Bau:
    K-Nr, Typ, Firma, Name, PLZ, Ort and E-Mail. Existing customers are matched
    by their stable K-Nr and updated only with non-empty values from the file.
    """
    suffix = Path(path).suffix.lower()
    if suffix == ".xlsx":
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        rows_raw = list(ws.iter_rows(values_only=True))
        if not rows_raw:
            return {"created": 0, "updated": 0, "skipped": 0, "errors": []}
        headers = [str(v or "").strip() for v in rows_raw[0]]
        rows = [dict(zip(headers, row)) for row in rows_raw[1:]]
    elif suffix == ".csv":
        with open(path, newline="", encoding="utf-8-sig", errors="replace") as handle:
            sample = handle.read(4096)
            handle.seek(0)
            dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
            rows = list(csv.DictReader(handle, dialect=dialect))
    else:
        raise ValueError("Unterstützt werden CSV und XLSX.")

    def normalized(row):
        return {str(key or "").strip().casefold(): value for key, value in row.items()}

    def pick(row, *keys):
        for key in keys:
            value = row.get(key.casefold())
            if value not in (None, ""):
                return str(value).strip()
        return ""

    stats = {"created": 0, "updated": 0, "skipped": 0, "errors": []}
    with transaction.atomic():
        for idx, raw in enumerate(rows, start=2):
            row = normalized(raw)
            number = pick(row, "K-Nr", "Kundennummer", "Nummer", "Customer No")
            company = pick(row, "Firma", "Unternehmen", "Company")
            full_name = pick(row, "Name", "Kunde", "Customer")
            if not number or not (company or full_name):
                stats["skipped"] += 1
                continue
            try:
                type_raw = pick(row, "Typ", "Kundentyp", "Type").casefold()
                customer_type = Customer.Type.BUSINESS if (
                    "unternehmen" in type_raw or "geschäft" in type_raw or "business" in type_raw or company
                ) else Customer.Type.PRIVATE
                first_name = ""
                last_name = ""
                if full_name:
                    parts = full_name.split(None, 1)
                    first_name = parts[0]
                    last_name = parts[1] if len(parts) > 1 else ""

                customer, created = Customer.objects.get_or_create(
                    organization=organization,
                    number=number,
                    defaults={"type": customer_type},
                )
                customer.type = customer_type
                if company:
                    customer.company = company
                if first_name:
                    customer.first_name = first_name
                if last_name:
                    customer.last_name = last_name
                email = pick(row, "E-Mail", "Email", "E-Mail-Adresse")
                postal_code = pick(row, "PLZ", "Postleitzahl", "ZIP")
                city = pick(row, "Ort", "Stadt", "City")
                if email:
                    customer.email = email
                if postal_code:
                    customer.postal_code = postal_code
                if city:
                    customer.city = city

                legacy_details = []
                offers = pick(row, "Anzahl_Angebote")
                invoices = pick(row, "Anzahl_Rechnungen")
                revenue = pick(row, "Umsatz_Netto_Bezahlt")
                folder = pick(row, "Ordner")
                if offers:
                    legacy_details.append(f"Angebote: {offers}")
                if invoices:
                    legacy_details.append(f"Rechnungen: {invoices}")
                if revenue:
                    legacy_details.append(f"Umsatz netto bezahlt: {revenue}")
                if folder:
                    legacy_details.append(f"Altordner: {folder}")
                if legacy_details:
                    marker = "Kundenregister-Import: " + " · ".join(legacy_details)
                    if marker not in customer.notes:
                        customer.notes = (customer.notes.rstrip() + "\n" + marker).strip()
                tags = list(customer.tags or [])
                if "Kundenregister" not in tags:
                    tags.append("Kundenregister")
                customer.tags = tags
                customer.active = True
                customer.save()
                stats["created" if created else "updated"] += 1
            except Exception as exc:
                stats["errors"].append(f"Zeile {idx}: {exc}")
    stats["errors"] = stats["errors"][:50]
    return stats
