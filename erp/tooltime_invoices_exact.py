from __future__ import annotations

from datetime import date
from decimal import Decimal
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from . import models as m
from . import rebuild_views as base
from . import tooltime_parity_views as parity
from .services.tooltime_parity_finance import meta_for, profile_for
from .services.tooltime_pay import provider_ready as pay_provider_ready


def customer_label(customer):
    if customer is None:
        return ""
    display = getattr(customer, "display_name", None)
    if callable(display):
        try:
            display = display()
        except TypeError:
            pass
    if isinstance(display, str) and display.strip():
        return display.strip()
    company = (getattr(customer, "company", "") or "").strip()
    person = " ".join(
        value.strip()
        for value in (
            getattr(customer, "first_name", "") or "",
            getattr(customer, "last_name", "") or "",
        )
        if value.strip()
    )
    return company or person or ""


def compliance_state(invoice):
    helper = getattr(parity, "_phase4_invoice_compliance_state", None)
    if helper:
        return helper(invoice)
    try:
        return invoice.compliance.state or "draft"
    except Exception:
        return "draft"


def document_customer(invoice, meta):
    helper = getattr(parity, "_phase4_customer", None)
    if helper:
        return helper(invoice, meta)
    project = getattr(invoice, "project", None)
    return getattr(project, "customer", None)


def has_dunning(invoice):
    try:
        return any(True for _row in invoice.tooltime_dunning_records.all())
    except Exception:
        return False


def has_refund(invoice):
    try:
        return any(
            (getattr(row, "status", "") or "").lower() == "refunded"
            for row in invoice.tooltime_payment_transactions.all()
        )
    except Exception:
        return False


def display_status(invoice, totals):
    state = compliance_state(invoice)
    if state == "cancelled":
        return "Storniert", "cancelled"
    if state == "credited" or has_refund(invoice):
        return "Erstattet", "refunded"
    if state != "finalized":
        return "Entwurf", "draft"
    open_amount = totals.get("open", Decimal("0")) or Decimal("0")
    if open_amount <= 0:
        return "Bezahlt", "paid"
    if has_dunning(invoice):
        return "Im Mahnverfahren", "dunning"
    if invoice.due_date and invoice.due_date < timezone.localdate():
        return "Überfällig", "overdue"
    return "Unbezahlt", "unpaid"


def invoice_type(meta):
    return (getattr(meta, "invoice_type", "") or "standard") if meta is not None else "standard"


def type_label(meta):
    return {
        "standard": "Rechnung",
        "advance": "Abschlagsrechnung",
        "partial": "Teilrechnung",
        "final": "Schlussrechnung",
    }.get(invoice_type(meta), "Rechnung")


def invoice_title(invoice, meta, status_key):
    for source in (meta, invoice):
        if source is None:
            continue
        for attr in ("document_title", "title", "subject", "heading", "name"):
            value = getattr(source, attr, None)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return "Stornorechnung" if status_key == "refunded" else type_label(meta)


def last_change(invoice, meta=None):
    values = [
        getattr(invoice, "updated_at", None),
        getattr(invoice, "created_at", None),
        getattr(meta, "updated_at", None) if meta is not None else None,
    ]
    try:
        values.extend(row.created_at for row in invoice.tooltime_dunning_records.all())
    except Exception:
        pass
    try:
        values.extend(row.updated_at for row in invoice.tooltime_payment_transactions.all())
    except Exception:
        pass
    values = [value for value in values if value is not None]
    return max(values) if values else None


def relative_change(value):
    if value is None:
        return "—"
    try:
        current = timezone.now()
        if timezone.is_naive(value):
            value = timezone.make_aware(value, timezone.get_current_timezone())
        seconds = max(0, int((current - value).total_seconds()))
    except Exception:
        return "—"
    if seconds < 60:
        return "gerade eben"
    minutes = seconds // 60
    if minutes < 60:
        return f"vor {minutes} Min."
    hours = minutes // 60
    if hours < 24:
        return f"vor {hours} Std."
    days = hours // 24
    if days == 1:
        return "vor einem Tag"
    if days < 14:
        return f"vor {days} Tagen"
    return value.strftime("%d.%m.%Y")


def sort_key(row, sort):
    if sort.startswith("amount"):
        return row["gross"]
    if sort.startswith("outstanding"):
        return row["open"]
    if sort.startswith("date"):
        return row["invoice"].issue_date
    return row["last_change"] or row["invoice"].issue_date


@login_required
def invoice_list(request):
    org = base._org(request)
    query = (request.GET.get("q") or "").strip()
    status_filter = (request.GET.get("status") or "all").strip().lower()
    type_filter = (request.GET.get("type") or "all").strip().lower()
    sort = (request.GET.get("sort") or "last_change_desc").strip().lower()
    date_from_raw = (request.GET.get("date_from") or "").strip()
    date_to_raw = (request.GET.get("date_to") or "").strip()

    try:
        date_from = date.fromisoformat(date_from_raw) if date_from_raw else None
    except ValueError:
        date_from = None
        date_from_raw = ""
    try:
        date_to = date.fromisoformat(date_to_raw) if date_to_raw else None
    except ValueError:
        date_to = None
        date_to_raw = ""
    if date_from and date_to and date_from > date_to:
        date_from, date_to = date_to, date_from
        date_from_raw, date_to_raw = date_from.isoformat(), date_to.isoformat()

    try:
        amount = int(request.GET.get("amount") or 20)
    except (TypeError, ValueError):
        amount = 20
    if amount not in {20, 50, 100}:
        amount = 20
    try:
        offset = max(0, int(request.GET.get("offset") or 0))
    except (TypeError, ValueError):
        offset = 0

    qs = (
        m.Invoice.objects.filter(organization=org)
        .select_related("project__customer")
        .prefetch_related("items", "payments", "tooltime_dunning_records", "tooltime_payment_transactions")
        .order_by("-created_at", "-pk")
    )

    all_rows = []
    draft_amount = Decimal("0")
    unpaid_amount = Decimal("0")
    overdue_amount = Decimal("0")
    dunning_amount = Decimal("0")
    today = timezone.localdate()

    for invoice in qs[:2000]:
        totals = base._invoice_total(invoice)
        meta = meta_for(invoice, "invoice", create=False)
        customer = document_customer(invoice, meta)
        status_text, status_key = display_status(invoice, totals)
        gross = totals.get("gross", totals.get("net", Decimal("0"))) or Decimal("0")
        open_amount = totals.get("open", Decimal("0")) or Decimal("0")
        state = compliance_state(invoice)
        dunning = has_dunning(invoice)
        changed = last_change(invoice, meta)
        row = {
            "invoice": invoice,
            "meta": meta,
            "customer_label": customer_label(customer),
            "invoice_title": invoice_title(invoice, meta, status_key),
            "invoice_type": invoice_type(meta),
            "invoice_type_label": type_label(meta),
            "gross": gross,
            "open": open_amount,
            "status": status_text,
            "status_key": status_key,
            "last_change": changed,
            "last_change_label": relative_change(changed),
            "finalized": state == "finalized",
        }
        all_rows.append(row)

        if status_key == "draft":
            draft_amount += gross
        if state == "finalized" and open_amount > 0:
            unpaid_amount += open_amount
            if invoice.due_date and invoice.due_date < today:
                overdue_amount += open_amount
            if dunning:
                dunning_amount += open_amount

    valid_statuses = {"draft", "unpaid", "overdue", "dunning", "paid", "refunded", "cancelled"}
    valid_types = {"standard", "advance", "partial", "final"}
    rows = []
    for row in all_rows:
        invoice = row["invoice"]
        if status_filter in valid_statuses and row["status_key"] != status_filter:
            continue
        if type_filter in valid_types and row["invoice_type"] != type_filter:
            continue
        if date_from and invoice.issue_date < date_from:
            continue
        if date_to and invoice.issue_date > date_to:
            continue
        if query:
            project = getattr(invoice, "project", None)
            searchable = " ".join(
                str(value or "")
                for value in (
                    getattr(invoice, "number", ""),
                    row["invoice_title"],
                    row["invoice_type_label"],
                    row["customer_label"],
                    getattr(project, "number", "") if project else "",
                    getattr(project, "title", "") if project else "",
                )
            ).casefold()
            if query.casefold() not in searchable:
                continue
        rows.append(row)

    allowed_sorts = {
        "last_change_desc", "last_change_asc",
        "date_desc", "date_asc",
        "amount_desc", "amount_asc",
        "outstanding_desc", "outstanding_asc",
    }
    if sort not in allowed_sorts:
        sort = "last_change_desc"
    rows.sort(key=lambda row: (sort_key(row, sort), row["invoice"].pk), reverse=sort.endswith("_desc"))

    total_count = len(rows)
    if offset >= total_count and total_count:
        offset = max(0, ((total_count - 1) // amount) * amount)
    page_rows = rows[offset:offset + amount]
    first_item = offset + 1 if total_count else 0
    last_item = min(offset + amount, total_count)
    prev_offset = max(0, offset - amount)
    next_offset = offset + amount if offset + amount < total_count else None

    params = {
        "q": query,
        "status": status_filter,
        "type": type_filter,
        "date_from": date_from_raw,
        "date_to": date_to_raw,
        "sort": sort,
        "amount": amount,
    }
    query_tail = urlencode({key: value for key, value in params.items() if value not in ("", "all")})
    last_change_params = dict(params)
    last_change_params["sort"] = "last_change_asc" if sort == "last_change_desc" else "last_change_desc"
    last_change_query = urlencode({key: value for key, value in last_change_params.items() if value not in ("", "all")})

    pay_active, _pay_reason = pay_provider_ready(org)

    return render(request, "rebuild/invoices.html", {
        "rows": page_rows,
        "q": query,
        "status_filter": status_filter,
        "type_filter": type_filter,
        "sort": sort,
        "date_from": date_from_raw,
        "date_to": date_to_raw,
        "amount": amount,
        "offset": offset,
        "total_count": total_count,
        "first_item": first_item,
        "last_item": last_item,
        "prev_offset": prev_offset,
        "next_offset": next_offset,
        "query_tail": query_tail,
        "last_change_query": last_change_query,
        "draft_amount": draft_amount,
        "unpaid_amount": unpaid_amount,
        "overdue_amount": overdue_amount,
        "dunning_amount": dunning_amount,
        "pay_active": pay_active,
    })
