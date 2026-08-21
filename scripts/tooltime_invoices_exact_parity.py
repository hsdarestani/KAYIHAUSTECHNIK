from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME INVOICES EXACT PARITY 2026-08-21"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"ToolTime invoices parity target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def install_view_module() -> None:
    write("erp/tooltime_invoices_exact.py", r'''from __future__ import annotations

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

    pay_cfg = dict((profile_for(org).settings or {}).get("pay") or {})
    provider = str(pay_cfg.get("provider") or "").strip().lower()
    pay_active = bool(pay_cfg.get("enabled")) or provider not in {"", "disabled", "none"}

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
''')


def patch_urls() -> None:
    rel = "erp/rebuild_urls.py"
    text = read(rel)
    import_line = "from . import tooltime_invoices_exact as invoices_exact\n"
    if import_line not in text:
        anchor = "from . import tooltime_parity_views as tooltime_parity\n"
        if anchor in text:
            text = text.replace(anchor, anchor + import_line, 1)
        else:
            lines = text.splitlines(True)
            insert_at = 0
            for index, line in enumerate(lines):
                if line.startswith("from . import "):
                    insert_at = index + 1
            lines.insert(insert_at, import_line)
            text = "".join(lines)

    pattern = re.compile(r'path\("invoices/",\s*[^,\n]+\.invoice_list,\s*name="next-invoices"\)')
    replacement = 'path("invoices/", invoices_exact.invoice_list, name="next-invoices")'
    text, count = pattern.subn(replacement, text, count=1)
    if count != 1 and replacement not in text:
        raise RuntimeError("ToolTime invoices parity route anchor missing")
    write(rel, text)


def install_template() -> None:
    write("templates/rebuild/invoices.html", r'''{% extends 'rebuild/base.html' %}{% load static %}
{% block title %}Rechnungen · A+Bau{% endblock %}
{% block content %}
<link rel="stylesheet" href="{% static 'css/tooltime-invoices-exact.css' %}?v=20260821-invoices-exact">
<script src="{% static 'js/tooltime-invoices-exact.js' %}?v=20260821-invoices-exact" defer></script>
<div class="tti-page" data-tooltime-invoices-exact>
  <div class="tti-topbar">
    <div class="tti-heading"><h1>Rechnungen</h1><span class="tti-help" title="Rechnungen verwalten">?</span></div>
    <div class="tti-top-actions">
      <form class="tti-search" method="get" role="search">
        <input type="hidden" name="status" value="{{ status_filter }}"><input type="hidden" name="type" value="{{ type_filter }}">
        <input type="hidden" name="date_from" value="{{ date_from }}"><input type="hidden" name="date_to" value="{{ date_to }}">
        <input type="hidden" name="sort" value="{{ sort }}"><input type="hidden" name="amount" value="{{ amount }}">
        <span aria-hidden="true">⌕</span><input type="search" name="q" value="{{ q }}" placeholder="Suchen" aria-label="Rechnungen suchen"><button type="submit" class="sr-only">Suchen</button>
      </form>
      <a class="tti-new" href="{% url 'next-invoice-create' %}"><span aria-hidden="true">＋</span> Neue Rechnung</a>
    </div>
  </div>
  <div class="tti-kpis" aria-label="Rechnungsübersicht">
    <div class="tti-kpi" data-invoice-kpi="draft"><span>Entwurf</span><strong>{{ draft_amount|floatformat:2 }} €</strong></div>
    <div class="tti-kpi" data-invoice-kpi="unpaid"><span>Unbezahlt</span><strong>{{ unpaid_amount|floatformat:2 }} €</strong></div>
    <div class="tti-kpi" data-invoice-kpi="overdue"><span>Überfällig</span><strong>{{ overdue_amount|floatformat:2 }} €</strong></div>
    <div class="tti-kpi" data-invoice-kpi="dunning"><span>Im Mahnverfahren</span><strong>{{ dunning_amount|floatformat:2 }} €</strong></div>
  </div>
  <form class="tti-filters" method="get" data-invoice-filters>
    <input type="hidden" name="q" value="{{ q }}"><input type="hidden" name="sort" value="{{ sort }}"><input type="hidden" name="amount" value="{{ amount }}">
    <label class="tti-select"><span class="sr-only">Status</span><select name="status" aria-label="Rechnungsstatus">
      <option value="all" {% if status_filter == 'all' %}selected{% endif %}>Alle Rechnungen</option><option value="draft" {% if status_filter == 'draft' %}selected{% endif %}>Entwurf</option><option value="unpaid" {% if status_filter == 'unpaid' %}selected{% endif %}>Unbezahlt</option><option value="overdue" {% if status_filter == 'overdue' %}selected{% endif %}>Überfällig</option><option value="dunning" {% if status_filter == 'dunning' %}selected{% endif %}>Im Mahnverfahren</option><option value="paid" {% if status_filter == 'paid' %}selected{% endif %}>Bezahlt</option><option value="refunded" {% if status_filter == 'refunded' %}selected{% endif %}>Erstattet</option><option value="cancelled" {% if status_filter == 'cancelled' %}selected{% endif %}>Storniert</option>
    </select></label>
    <label class="tti-select"><span class="sr-only">Rechnungstyp</span><select name="type" aria-label="Rechnungstyp">
      <option value="all" {% if type_filter == 'all' %}selected{% endif %}>Alle Rechnungstypen</option><option value="standard" {% if type_filter == 'standard' %}selected{% endif %}>Rechnung</option><option value="advance" {% if type_filter == 'advance' %}selected{% endif %}>Abschlagsrechnung</option><option value="partial" {% if type_filter == 'partial' %}selected{% endif %}>Teilrechnung</option><option value="final" {% if type_filter == 'final' %}selected{% endif %}>Schlussrechnung</option>
    </select></label>
    <details class="tti-date-filter" {% if date_from or date_to %}open{% endif %}><summary><span aria-hidden="true">▣</span>{% if date_from or date_to %}Zeitraum aktiv{% else %}Zeitraum wählen{% endif %}</summary><div class="tti-date-popover"><label>Von<input type="date" name="date_from" value="{{ date_from }}"></label><label>Bis<input type="date" name="date_to" value="{{ date_to }}"></label><div><button type="submit">Anwenden</button>{% if date_from or date_to %}<button type="button" data-clear-invoice-dates>Zurücksetzen</button>{% endif %}</div></div></details>
    <label class="tti-mobile-sort"><span>Sortieren</span><select name="sort" aria-label="Sortieren"><option value="last_change_desc" {% if sort == 'last_change_desc' %}selected{% endif %}>Letzte Änderung ↓</option><option value="last_change_asc" {% if sort == 'last_change_asc' %}selected{% endif %}>Letzte Änderung ↑</option><option value="date_desc" {% if sort == 'date_desc' %}selected{% endif %}>Rechnungsdatum ↓</option><option value="date_asc" {% if sort == 'date_asc' %}selected{% endif %}>Rechnungsdatum ↑</option><option value="amount_desc" {% if sort == 'amount_desc' %}selected{% endif %}>Betrag ↓</option><option value="amount_asc" {% if sort == 'amount_asc' %}selected{% endif %}>Betrag ↑</option><option value="outstanding_desc" {% if sort == 'outstanding_desc' %}selected{% endif %}>Ausstehend ↓</option><option value="outstanding_asc" {% if sort == 'outstanding_asc' %}selected{% endif %}>Ausstehend ↑</option></select></label>
    <button type="submit" class="sr-only">Filter anwenden</button>
  </form>
  {% if not pay_active %}<div class="tti-pay-banner"><div><span class="tti-pay-mark">◐</span><strong>Pay</strong><span>Schluss mit Warten auf Ihr Geld? Digitale Zahlungen helfen, Rechnungen schneller abzuschließen.</span></div><div><a href="{% url 'next-settings' %}">Jetzt aktivieren</a><button type="button" data-dismiss-pay-banner aria-label="Hinweis schließen">×</button></div></div>{% endif %}
  <div class="tti-table-wrap"><table class="tti-table" data-invoice-table><thead><tr><th>Rechnungsdatum</th><th>Nr.</th><th>Status</th><th>Rechnungstitel</th><th>Kunde</th><th class="tti-money">Betrag</th><th class="tti-money">Ausstehend</th><th><a class="tti-sort-link" href="?{{ last_change_query }}{% if last_change_query %}&{% endif %}offset=0">Letzte Änderung <span aria-hidden="true">{% if sort == 'last_change_asc' %}↑{% else %}↓{% endif %}</span></a></th><th aria-label="Aktionen"></th></tr></thead>
    <tbody>{% for row in rows %}<tr data-invoice-row><td data-label="Rechnungsdatum"><strong>{{ row.invoice.issue_date|date:'d.m.Y' }}</strong></td><td data-label="Nr."><strong>{% if row.invoice.number %}{{ row.invoice.number }}{% else %}–{% endif %}</strong></td><td data-label="Status"><span class="tti-status tti-status-{{ row.status_key }}">{{ row.status }}</span></td><td data-label="Rechnungstitel"><a class="tti-title" href="{% url 'next-invoice-edit' row.invoice.pk %}">{{ row.invoice_title }}</a><small>{{ row.invoice_type_label }}</small></td><td data-label="Kunde"><span class="tti-customer-icon" aria-hidden="true">⌂</span>{% if row.customer_label %}{{ row.customer_label }}{% else %}—{% endif %}</td><td data-label="Betrag" class="tti-money"><strong>{{ row.gross|floatformat:2 }} €</strong></td><td data-label="Ausstehend" class="tti-money">{{ row.open|floatformat:2 }} €</td><td data-label="Letzte Änderung"><span class="tti-last-change">{{ row.last_change_label }}</span></td><td class="tti-actions"><details class="tti-row-menu"><summary aria-label="Rechnungsaktionen">•••</summary><div><a href="{% url 'next-invoice-edit' row.invoice.pk %}">Rechnung öffnen</a>{% if row.finalized and row.open > 0 %}<a href="{% url 'next-invoice-edit' row.invoice.pk %}#zahlungen">Zahlung erfassen</a>{% endif %}</div></details></td></tr>{% empty %}<tr><td colspan="9"><div class="tti-empty"><strong>Keine Rechnungen gefunden.</strong><span>Passe die Filter an oder erstelle eine neue Rechnung.</span></div></td></tr>{% endfor %}</tbody></table></div>
  <div class="tti-pagination" aria-label="Seitennavigation"><div><span>{% if total_count %}{{ first_item }}–{{ last_item }} von {{ total_count }}{% else %}0 Rechnungen{% endif %}</span><label>Zeilen <select data-invoice-page-size aria-label="Zeilen pro Seite"><option value="20" {% if amount == 20 %}selected{% endif %}>20</option><option value="50" {% if amount == 50 %}selected{% endif %}>50</option><option value="100" {% if amount == 100 %}selected{% endif %}>100</option></select></label></div><div class="tti-page-buttons">{% if offset > 0 %}<a href="?{{ query_tail }}{% if query_tail %}&{% endif %}offset={{ prev_offset }}" aria-label="Vorherige Seite">‹</a>{% else %}<span aria-disabled="true">‹</span>{% endif %}{% if next_offset != None %}<a href="?{{ query_tail }}{% if query_tail %}&{% endif %}offset={{ next_offset }}" aria-label="Nächste Seite">›</a>{% else %}<span aria-disabled="true">›</span>{% endif %}</div></div>
</div>
{% endblock %}''')


def install_assets() -> None:
    write("static/css/tooltime-invoices-exact.css", r'''.tti-page{max-width:100%;margin:0 auto;color:#1f2c3a}.tti-topbar{display:flex;align-items:center;justify-content:space-between;gap:24px;margin-bottom:16px}.tti-heading{display:flex;align-items:center;gap:10px}.tti-heading h1{margin:0;font-size:27px;letter-spacing:-.035em;font-weight:760}.tti-help{display:inline-flex;width:19px;height:19px;border:2px solid #1682e8;border-radius:50%;align-items:center;justify-content:center;color:#1682e8;font-size:11px;font-weight:900}.tti-top-actions{display:flex;align-items:center;gap:14px}.tti-search{height:42px;min-width:270px;border:1px solid #d4dce5;border-radius:9px;background:#fff;display:flex;align-items:center;gap:9px;padding:0 12px}.tti-search span{font-size:21px;color:#758497;transform:rotate(-18deg)}.tti-search input[type=search]{width:100%;border:0;outline:0;background:transparent;font:inherit;color:#243449}.tti-new{height:42px;display:inline-flex;align-items:center;justify-content:center;gap:7px;padding:0 15px;border-radius:9px;background:#147de0;color:#fff;text-decoration:none;font-weight:750}.tti-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));max-width:680px;border-radius:10px;background:#f6f7f9;margin-bottom:13px;overflow:hidden}.tti-kpi{position:relative;padding:14px 20px 13px}.tti-kpi:not(:last-child):after{content:"";position:absolute;right:0;top:13px;bottom:13px;width:1px;background:#d7dde5}.tti-kpi span{display:block;font-size:12px;color:#8a97a6;margin-bottom:4px}.tti-kpi strong{font-size:16px;color:#253447;white-space:nowrap}.tti-filters{display:flex;align-items:center;gap:10px;margin:8px 0 13px}.tti-select select,.tti-mobile-sort select{appearance:none;border:1px solid #d3dbe4;border-radius:8px;background:#fff;padding:9px 34px 9px 12px;min-height:39px;color:#2d3c4e;font:inherit;font-size:13px;font-weight:600}.tti-mobile-sort{display:none}.tti-date-filter{position:relative}.tti-date-filter>summary{list-style:none;cursor:pointer;min-height:39px;display:flex;align-items:center;gap:7px;border:1px solid #d3dbe4;border-radius:8px;background:#fff;padding:0 12px;font-size:13px;font-weight:600}.tti-date-filter>summary::-webkit-details-marker{display:none}.tti-date-popover{position:absolute;z-index:50;top:46px;left:0;width:300px;padding:14px;border:1px solid #dce2e9;border-radius:10px;background:#fff;box-shadow:0 14px 32px rgba(25,42,62,.14);display:grid;grid-template-columns:1fr 1fr;gap:10px}.tti-date-popover label{display:grid;gap:5px;font-size:11px;font-weight:700;color:#6e7a89}.tti-date-popover input{width:100%;box-sizing:border-box;border:1px solid #d7dfe8;border-radius:7px;padding:8px}.tti-date-popover>div{grid-column:1/-1;display:flex;gap:8px;justify-content:flex-end}.tti-date-popover button{border:0;border-radius:7px;padding:8px 11px;cursor:pointer;font-weight:700}.tti-date-popover button[type=submit]{background:#147de0;color:#fff}.tti-pay-banner{min-height:47px;border-radius:9px;background:#eef8f3;display:flex;align-items:center;justify-content:space-between;gap:18px;padding:0 15px;margin-bottom:11px;font-size:13px;color:#617165}.tti-pay-banner>div{display:flex;align-items:center;gap:8px}.tti-pay-mark{font-size:20px;color:#162f4b}.tti-pay-banner strong{font-size:17px;color:#20364b}.tti-pay-banner a{color:#147de0;text-decoration:none;font-weight:750}.tti-pay-banner button{border:0;background:transparent;color:#93a2ad;font-size:22px;cursor:pointer}.tti-table-wrap{background:#fff;border-top:1px solid #e5e9ee;overflow-x:auto}.tti-table{width:100%;border-collapse:collapse;font-size:13px}.tti-table th{padding:13px;text-align:left;color:#7f8b99;font-size:11px;font-weight:650;white-space:nowrap;border-bottom:1px solid #dfe5eb}.tti-table td{padding:17px 13px;border-bottom:1px solid #e4e8ed;color:#57677a;vertical-align:middle}.tti-table tbody tr:hover{background:#fbfcfd}.tti-title{display:block;color:#34465a;text-decoration:none;white-space:nowrap;max-width:250px;overflow:hidden;text-overflow:ellipsis}.tti-title+small{display:block;margin-top:3px;color:#9aa5b1;font-size:10px}.tti-customer-icon{margin-right:7px;color:#7b8c9e}.tti-money{text-align:right!important;font-variant-numeric:tabular-nums;white-space:nowrap}.tti-status{display:inline-flex;align-items:center;min-height:23px;padding:0 9px;border-radius:999px;font-size:10px;font-weight:800;white-space:nowrap}.tti-status-draft{background:#eef1f4;color:#697787}.tti-status-unpaid{background:#fff4d8;color:#8a6517}.tti-status-overdue{background:#fde4e4;color:#c74749}.tti-status-dunning{background:#ffecce;color:#a66214}.tti-status-paid{background:#dcefe3;color:#3a8560}.tti-status-refunded{background:#dce4eb;color:#527083}.tti-status-cancelled{background:#eaedf1;color:#7c8490}.tti-last-change{white-space:nowrap;color:#637387}.tti-sort-link{color:inherit;text-decoration:none}.tti-actions{width:44px}.tti-row-menu{position:relative}.tti-row-menu>summary{list-style:none;cursor:pointer;font-weight:900;letter-spacing:1px;color:#334b64;padding:7px 9px;border-radius:7px}.tti-row-menu>summary::-webkit-details-marker{display:none}.tti-row-menu>div{position:absolute;z-index:40;right:0;top:34px;min-width:190px;padding:6px;border:1px solid #dfe5ec;border-radius:9px;background:#fff;box-shadow:0 12px 30px rgba(23,39,57,.15)}.tti-row-menu a{display:block;padding:9px 10px;border-radius:6px;text-decoration:none;color:#34475b;white-space:nowrap}.tti-row-menu a:hover{background:#f2f5f8}.tti-empty{min-height:150px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:5px;color:#8a96a4}.tti-pagination{display:flex;align-items:center;justify-content:space-between;padding:14px 4px;color:#7b8794;font-size:12px}.tti-pagination>div{display:flex;align-items:center;gap:14px}.tti-page-buttons{gap:6px!important}.tti-page-buttons a,.tti-page-buttons span{width:30px;height:30px;border:1px solid #d9e0e7;border-radius:7px;display:flex;align-items:center;justify-content:center;text-decoration:none;color:#34495e;background:#fff;font-size:19px}.sr-only{position:absolute!important;width:1px!important;height:1px!important;padding:0!important;margin:-1px!important;overflow:hidden!important;clip:rect(0,0,0,0)!important;white-space:nowrap!important;border:0!important}@media(max-width:900px){.tti-kpis{max-width:none}.tti-mobile-sort{display:block}.tti-filters{flex-wrap:wrap}.tti-table th:nth-child(8),.tti-table td:nth-child(8){display:none}}@media(max-width:720px){.tti-topbar{display:grid}.tti-top-actions{width:100%}.tti-search{flex:1;min-width:0}.tti-kpis{grid-template-columns:1fr 1fr}.tti-pay-banner{padding:12px;flex-direction:column;align-items:flex-start}.tti-table-wrap{border:0;overflow:visible}.tti-table,.tti-table tbody{display:block}.tti-table thead{display:none}.tti-table tr[data-invoice-row]{display:block;padding:14px;margin-bottom:10px;border:1px solid #e0e5ea;border-radius:12px}.tti-table tr[data-invoice-row] td{display:flex!important;align-items:center;justify-content:space-between;gap:12px;padding:5px 0;border:0;text-align:right!important}.tti-table tr[data-invoice-row] td:before{content:attr(data-label);font-size:10px;text-transform:uppercase;color:#98a3af;font-weight:750}.tti-date-popover{position:fixed;left:16px;right:16px;width:auto}}@media(max-width:480px){.tti-top-actions{display:grid}.tti-new{width:100%;box-sizing:border-box}.tti-kpis{grid-template-columns:1fr}.tti-filters{display:grid;grid-template-columns:1fr 1fr}.tti-select select{width:100%}.tti-date-filter,.tti-mobile-sort{grid-column:1/-1}.tti-mobile-sort select{width:100%}}''')
    write("static/js/tooltime-invoices-exact.js", r'''(()=>{const root=document.querySelector('[data-tooltime-invoices-exact]');if(!root)return;const filters=root.querySelector('[data-invoice-filters]');filters?.querySelectorAll('select[name="status"],select[name="type"],select[name="sort"]').forEach(s=>s.addEventListener('change',()=>filters.requestSubmit()));root.querySelector('[data-clear-invoice-dates]')?.addEventListener('click',()=>{const a=filters?.querySelector('input[name="date_from"]'),b=filters?.querySelector('input[name="date_to"]');if(a)a.value='';if(b)b.value='';filters?.requestSubmit()});root.querySelector('[data-invoice-page-size]')?.addEventListener('change',e=>{const u=new URL(location.href);u.searchParams.set('amount',e.target.value);u.searchParams.set('offset','0');location.assign(u.toString())});root.querySelector('[data-dismiss-pay-banner]')?.addEventListener('click',e=>e.currentTarget.closest('.tti-pay-banner')?.remove());document.addEventListener('click',e=>root.querySelectorAll('.tti-row-menu[open]').forEach(m=>{if(!m.contains(e.target))m.removeAttribute('open')}));document.addEventListener('keydown',e=>{if(e.key==='Escape')root.querySelectorAll('details[open]').forEach(n=>n.removeAttribute('open'))})})();''')


def patch_browser_smoke() -> None:
    rel = "scripts/production_browser_smoke.py"
    text = read(rel)
    marker = "            # A+BAU TOOLTIME INVOICES EXACT PARITY BROWSER SMOKE\n"
    if marker in text:
        return
    office_start = text.find("def run_office_surface(")
    field_start = text.find("\ndef run_field_surface(", office_start)
    close = "            context.close()\n"
    if office_start < 0 or field_start < 0:
        raise RuntimeError("Invoices parity browser smoke could not find office/field surfaces")
    office_close = text.rfind(close, office_start, field_start)
    if office_close < 0:
        raise RuntimeError("Invoices parity browser smoke could not find office context close")
    block = r'''            # A+BAU TOOLTIME INVOICES EXACT PARITY BROWSER SMOKE
            response = page.goto(base_url.rstrip("/") + "/invoices/", wait_until="domcontentloaded", timeout=30_000)
            if response is None or response.status != 200:
                fail(f"ToolTime invoices exact parity expected 200, got {response.status if response else 'no response'}")
            if page.locator('[data-tooltime-invoices-exact]').count() != 1:
                fail("ToolTime invoices exact parity shell is missing")
            if page.locator('[data-invoice-kpi]').count() != 4:
                fail("ToolTime invoices KPI strip must expose exactly four metrics")
            if page.locator('[data-invoice-filters] select[name="status"]').count() != 1:
                fail("ToolTime invoices status filter is missing")
            if page.locator('[data-invoice-filters] select[name="type"]').count() != 1:
                fail("ToolTime invoices type filter is missing")
            if page.locator('input[aria-label="Rechnungen suchen"]').count() != 1:
                fail("ToolTime invoices search is missing")
            invoice_headers = " ".join(page.locator('[data-invoice-table] thead th').all_inner_texts())
            for expected_header in ("Rechnungsdatum", "Nr.", "Status", "Rechnungstitel", "Kunde", "Betrag", "Ausstehend", "Letzte Änderung"):
                if expected_header not in invoice_headers:
                    fail(f"ToolTime invoices table header missing: {expected_header}")
'''
    text = text[:office_close] + block + text[office_close:]
    write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def install_contract_test() -> None:
    write("tests/test_tooltime_invoices_exact_parity.py", r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]

class ToolTimeInvoicesExactParityContractTests(SimpleTestCase):
    def test_exact_invoice_surface_is_installed(self):
        template = (ROOT / "templates/rebuild/invoices.html").read_text(encoding="utf-8")
        for required in ("data-tooltime-invoices-exact", "data-invoice-kpi", "Rechnungsdatum", "Rechnungstitel", "Ausstehend", "Letzte Änderung", 'name="date_from"', 'name="date_to"', "data-invoice-page-size", "tti-row-menu"):
            self.assertIn(required, template)

    def test_invoice_route_uses_exact_parity_module(self):
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        module = (ROOT / "erp/tooltime_invoices_exact.py").read_text(encoding="utf-8")
        self.assertIn("invoices_exact.invoice_list", urls)
        self.assertIn("tooltime_dunning_records", module)
        self.assertIn("tooltime_payment_transactions", module)
        self.assertIn("unpaid_amount += open_amount", module)
        self.assertIn("overdue_amount += open_amount", module)
        self.assertIn("dunning_amount += open_amount", module)
        self.assertIn('"last_change_desc"', module)

    def test_browser_smoke_covers_exact_invoice_surface(self):
        smoke = (ROOT / "scripts/production_browser_smoke.py").read_text(encoding="utf-8")
        self.assertIn("A+BAU TOOLTIME INVOICES EXACT PARITY BROWSER SMOKE", smoke)
        self.assertIn("[data-tooltime-invoices-exact]", smoke)
''')


def final_guard() -> None:
    module = read("erp/tooltime_invoices_exact.py")
    urls = read("erp/rebuild_urls.py")
    template = read("templates/rebuild/invoices.html")
    smoke = read("scripts/production_browser_smoke.py")
    if "invoices_exact.invoice_list" not in urls:
        raise RuntimeError("Exact invoice list route is not active")
    for required in ("data-tooltime-invoices-exact", "data-invoice-kpi", "data-invoice-table", "Rechnungstitel", "Ausstehend", "Letzte Änderung"):
        if required not in template:
            raise RuntimeError(f"Invoice exact-parity template contract missing: {required}")
    if "A+BAU TOOLTIME INVOICES EXACT PARITY BROWSER SMOKE" not in smoke:
        raise RuntimeError("Invoice exact-parity browser smoke missing")
    compile(module, str(ROOT / "erp/tooltime_invoices_exact.py"), "exec")
    compile(smoke, str(ROOT / "scripts/production_browser_smoke.py"), "exec")


def run() -> None:
    install_view_module()
    patch_urls()
    install_template()
    install_assets()
    patch_browser_smoke()
    install_contract_test()
    final_guard()
    print(f"{MARKER}: KPI, Suche, Filter, Pay-Hinweis, ToolTime-Spalten, Mahn-/Zahlungsstatus, Sortierung, Pagination und Drei-Punkt-Aktionen aktiv.")


if __name__ == "__main__":
    run()
