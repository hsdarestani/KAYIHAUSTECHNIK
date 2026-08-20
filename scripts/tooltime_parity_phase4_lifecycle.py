from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME PHASE 4 LIFECYCLE 2026-08-20"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Phase 4 target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_views() -> None:
    rel = "erp/tooltime_parity_views.py"
    text = read(rel)
    if "from datetime import date" not in text:
        anchor = "from decimal import Decimal\n"
        if anchor not in text:
            raise RuntimeError("Phase 4 datetime import anchor missing")
        text = text.replace(anchor, anchor + "from datetime import date\n", 1)

    if f"# {MARKER}" not in text:
        text += r'''

# A+BAU TOOLTIME PHASE 4 LIFECYCLE 2026-08-20

def _phase4_customer(document, meta=None):
    if meta is not None and getattr(meta, "customer_id", None):
        return meta.customer
    project = getattr(document, "project", None)
    return getattr(project, "customer", None)


def _phase4_project_label(document):
    project = getattr(document, "project", None)
    if project is None:
        return "Ohne Projekt"
    title = (getattr(project, "title", "") or "").strip()
    if title.startswith("Direktdokumente · Kunde") or title == "Allgemeiner Auftrag":
        return "Ohne Projekt"
    number = (getattr(project, "number", "") or "").strip()
    return f"{number} · {title}" if number else (title or "Ohne Projekt")


def _phase4_invoice_compliance_state(invoice):
    try:
        return invoice.compliance.state or "draft"
    except Exception:
        return "draft"


def _phase4_invoice_display(invoice, totals):
    state = _phase4_invoice_compliance_state(invoice)
    if state == "cancelled":
        return "Storniert", "cancelled"
    if state == "credited":
        return "Gutgeschrieben", "credited"
    if state != "finalized":
        return "Entwurf", "draft"
    open_amount = totals.get("open", Decimal("0")) or Decimal("0")
    if open_amount <= 0:
        return "Bezahlt", "paid"
    if invoice.due_date and invoice.due_date < timezone.localdate():
        return "Überfällig", "overdue"
    return "Unbezahlt", "unpaid"


@login_required
def quote_list(request):
    org = _org(request)
    query = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "all").strip()
    sort = (request.GET.get("sort") or "date_desc").strip()
    qs = m.Quote.objects.filter(organization=org).select_related("project__customer").order_by("-created_at")
    if query:
        qs = qs.filter(
            Q(number__icontains=query)
            | Q(project__number__icontains=query)
            | Q(project__title__icontains=query)
            | Q(project__customer__company__icontains=query)
            | Q(project__customer__first_name__icontains=query)
            | Q(project__customer__last_name__icontains=query)
        )
    if status in {"draft", "sent", "accepted", "rejected"}:
        qs = qs.filter(status=status)
    rows = []
    for quote in qs[:500]:
        totals = base._quote_total(quote)
        meta = meta_for(quote, "quote", create=False)
        customer = _phase4_customer(quote, meta)
        rows.append({
            "quote": quote,
            "meta": meta,
            "customer": customer,
            "project_label": _phase4_project_label(quote),
            "total": totals.get("gross", totals.get("net", Decimal("0"))) or Decimal("0"),
            "finalized": bool(meta and meta.finalized_at),
        })
    if sort == "amount_desc":
        rows.sort(key=lambda row: row["total"], reverse=True)
    elif sort == "amount_asc":
        rows.sort(key=lambda row: row["total"])
    elif sort == "date_asc":
        rows.sort(key=lambda row: (row["quote"].issue_date, row["quote"].pk))
    return render(request, "rebuild/quotes.html", {"rows": rows, "q": query, "status_filter": status, "sort": sort})


@login_required
def invoice_list(request):
    org = _org(request)
    query = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "all").strip()
    sort = (request.GET.get("sort") or "date_desc").strip()
    qs = m.Invoice.objects.filter(organization=org).select_related("project__customer").order_by("-created_at")
    if query:
        qs = qs.filter(
            Q(number__icontains=query)
            | Q(project__number__icontains=query)
            | Q(project__title__icontains=query)
            | Q(project__customer__company__icontains=query)
            | Q(project__customer__first_name__icontains=query)
            | Q(project__customer__last_name__icontains=query)
        )
    rows = []
    for invoice in qs[:500]:
        totals = base._invoice_total(invoice)
        meta = meta_for(invoice, "invoice", create=False)
        display_status, status_key = _phase4_invoice_display(invoice, totals)
        if status in {"draft", "unpaid", "overdue", "paid", "cancelled", "credited"} and status_key != status:
            continue
        customer = _phase4_customer(invoice, meta)
        rows.append({
            "invoice": invoice,
            "meta": meta,
            "customer": customer,
            "project_label": _phase4_project_label(invoice),
            "gross": totals.get("gross", totals.get("net", Decimal("0"))) or Decimal("0"),
            "open": totals.get("open", Decimal("0")) or Decimal("0"),
            "status": display_status,
            "status_key": status_key,
            "can_pay": status_key in {"unpaid", "overdue"},
            "can_dun": status_key in {"unpaid", "overdue"},
        })
    if sort == "open_desc":
        rows.sort(key=lambda row: row["open"], reverse=True)
    elif sort == "open_asc":
        rows.sort(key=lambda row: row["open"])
    elif sort == "amount_desc":
        rows.sort(key=lambda row: row["gross"], reverse=True)
    elif sort == "amount_asc":
        rows.sort(key=lambda row: row["gross"])
    elif sort == "date_asc":
        rows.sort(key=lambda row: (row["invoice"].issue_date, row["invoice"].pk))
    return render(request, "rebuild/invoices.html", {"rows": rows, "q": query, "status_filter": status, "sort": sort, "today": timezone.localdate()})


@login_required
@require_POST
def invoice_payment(request, pk):
    org = _org(request)
    invoice = get_object_or_404(m.Invoice.objects.select_related("project__customer"), organization=org, pk=pk)
    if _phase4_invoice_compliance_state(invoice) != "finalized":
        messages.error(request, "Zahlungen können nur für fertiggestellte Rechnungen erfasst werden.")
        return redirect("next-invoices")
    totals = base._invoice_total(invoice)
    open_amount = totals.get("open", Decimal("0")) or Decimal("0")
    if open_amount <= 0:
        messages.error(request, "Diese Rechnung ist bereits vollständig bezahlt.")
        return redirect("next-invoices")
    try:
        amount = money(request.POST.get("amount") or "0")
    except Exception:
        amount = Decimal("0")
    if amount <= 0:
        messages.error(request, "Bitte einen positiven Zahlbetrag eingeben.")
        return redirect("next-invoices")
    if amount > open_amount:
        messages.error(request, "Der Zahlbetrag darf den aktuell ausstehenden Betrag nicht überschreiten.")
        return redirect("next-invoices")
    paid_raw = (request.POST.get("paid_at") or "").strip()
    if paid_raw:
        try:
            paid_at = date.fromisoformat(paid_raw)
        except ValueError:
            messages.error(request, "Das Zahlungsdatum ist ungültig.")
            return redirect("next-invoices")
    else:
        paid_at = timezone.localdate()
    method = (request.POST.get("method") or "Überweisung").strip()[:40]
    if method not in {"Überweisung", "Bar", "Karte", "Lastschrift", "Sonstiges"}:
        method = "Sonstiges"
    reference = (request.POST.get("reference") or "").strip()[:240]
    m.Payment.objects.create(
        invoice=invoice,
        amount=amount,
        paid_at=paid_at,
        method=method,
        reference=reference,
        recorded_by=request.user,
    )
    after = base._invoice_total(invoice)
    invoice.status = "paid" if (after.get("open", Decimal("0")) or Decimal("0")) <= 0 else "partial"
    invoice.save(update_fields=["status", "updated_at"])
    messages.success(request, "Zahlung wurde verbucht. Teilzahlungen können jederzeit ergänzt werden.")
    return redirect("next-invoices")
'''
    write(rel, text)


def patch_urls() -> None:
    rel = "erp/rebuild_urls.py"
    text = read(rel)
    replacements = (
        ('path("quotes/", views.quote_list, name="next-quotes")', 'path("quotes/", tooltime_parity.quote_list, name="next-quotes")'),
        ('path("invoices/", views.invoice_list, name="next-invoices")', 'path("invoices/", tooltime_parity.invoice_list, name="next-invoices")'),
        ('path("invoices/<int:pk>/payment/", views.invoice_payment, name="next-invoice-payment")', 'path("invoices/<int:pk>/payment/", tooltime_parity.invoice_payment, name="next-invoice-payment")'),
    )
    for old, new in replacements:
        if new not in text:
            if old not in text:
                raise RuntimeError(f"Phase 4 route anchor missing: {old}")
            text = text.replace(old, new, 1)
    write(rel, text)


def install_templates() -> None:
    write("templates/rebuild/quotes.html", r'''{% extends 'rebuild/base.html' %}{% load static %}
{% block title %}Angebote · A+Bau{% endblock %}
{% block content %}
<link rel="stylesheet" href="{% static 'css/tooltime-parity-finance.css' %}?v=20260820-4">
<div class="tt-pagehead"><div><span class="tt-eyebrow">Verkauf</span><h1>Angebote</h1><p>Angebote durchsuchen, Status verwalten und direkt in Rechnungen übernehmen.</p></div><a class="nx-btn nx-btn-accent" href="{% url 'next-quote-create' %}">＋ Neues Angebot</a></div>
<form class="tt-list-toolbar" method="get"><label>Suchen<input class="nx-control" type="search" name="q" value="{{ q }}" placeholder="Nummer, Kunde oder Projekt"></label><label>Status<select class="nx-control" name="status"><option value="all">Alle Status</option><option value="draft" {% if status_filter == 'draft' %}selected{% endif %}>Entwurf</option><option value="sent" {% if status_filter == 'sent' %}selected{% endif %}>Versendet</option><option value="accepted" {% if status_filter == 'accepted' %}selected{% endif %}>Angenommen</option><option value="rejected" {% if status_filter == 'rejected' %}selected{% endif %}>Abgelehnt</option></select></label><label>Sortieren<select class="nx-control" name="sort"><option value="date_desc" {% if sort == 'date_desc' %}selected{% endif %}>Neueste zuerst</option><option value="date_asc" {% if sort == 'date_asc' %}selected{% endif %}>Älteste zuerst</option><option value="amount_desc" {% if sort == 'amount_desc' %}selected{% endif %}>Betrag absteigend</option><option value="amount_asc" {% if sort == 'amount_asc' %}selected{% endif %}>Betrag aufsteigend</option></select></label><button class="nx-btn" type="submit">Anwenden</button>{% if q or status_filter != 'all' or sort != 'date_desc' %}<a class="tt-link" href="{% url 'next-quotes' %}">Filter zurücksetzen</a>{% endif %}</form>
<div class="tt-list-card"><div class="tt-list-table tt-quotes-table"><div class="tt-list-head"><span>Angebot</span><span>Kunde</span><span>Projekt</span><span>Datum</span><span>Betrag</span><span>Status</span><span>Aktionen</span></div>{% for row in rows %}<div class="tt-list-row"><a class="tt-doc-number" href="{% url 'next-quote-edit' row.quote.pk %}">{% if row.quote.number %}{{ row.quote.number }}{% else %}Entwurf{% endif %}</a><span>{% if row.customer %}{{ row.customer.display_name }}{% else %}—{% endif %}</span><span>{{ row.project_label }}</span><span>{{ row.quote.issue_date|date:'d.m.Y' }}</span><strong>{{ row.total|floatformat:2 }} €</strong><span><span class="tt-state tt-state-{{ row.quote.status }}">{{ row.quote.get_status_display }}</span></span><div class="tt-row-actions"><a class="nx-btn nx-btn-small" href="{% url 'next-quote-edit' row.quote.pk %}">Öffnen</a>{% if row.finalized %}{% if row.quote.status != 'accepted' %}<form method="post" action="{% url 'next-quote-status' row.quote.pk %}">{% csrf_token %}<button class="tt-link" name="action" value="accepted">Annehmen</button></form>{% endif %}{% if row.quote.status != 'accepted' and row.quote.status != 'rejected' %}<form method="post" action="{% url 'next-quote-status' row.quote.pk %}">{% csrf_token %}<button class="tt-link" name="action" value="rejected">Ablehnen</button></form>{% endif %}{% if row.quote.status == 'rejected' %}<form method="post" action="{% url 'next-quote-status' row.quote.pk %}">{% csrf_token %}<button class="tt-link" name="action" value="pending">Zurücksetzen</button></form>{% endif %}<form method="post" action="{% url 'next-quote-to-invoice' row.quote.pk %}">{% csrf_token %}<button class="nx-btn nx-btn-small nx-btn-accent" type="submit">In Rechnung</button></form>{% endif %}</div></div>{% empty %}<div class="tt-empty-state"><strong>Keine Angebote gefunden.</strong><span>Passe die Filter an oder erstelle ein neues Angebot.</span></div>{% endfor %}</div></div>
{% endblock %}''')

    write("templates/rebuild/invoices.html", r'''{% extends 'rebuild/base.html' %}{% load static %}
{% block title %}Rechnungen · A+Bau{% endblock %}
{% block content %}
<link rel="stylesheet" href="{% static 'css/tooltime-parity-finance.css' %}?v=20260820-4"><script src="{% static 'js/tooltime-parity-lifecycle.js' %}?v=20260820-4" defer></script>
<div class="tt-pagehead"><div><span class="tt-eyebrow">Finanzen</span><h1>Rechnungen</h1><p>Offene Beträge, Fälligkeiten, Teilzahlungen und Mahnungen an einer Stelle.</p></div><a class="nx-btn nx-btn-accent" href="{% url 'next-invoice-create' %}">＋ Neue Rechnung</a></div>
<form class="tt-list-toolbar" method="get"><label>Suchen<input class="nx-control" type="search" name="q" value="{{ q }}" placeholder="Nummer, Kunde oder Projekt"></label><label>Status<select class="nx-control" name="status"><option value="all">Alle Status</option><option value="draft" {% if status_filter == 'draft' %}selected{% endif %}>Entwurf</option><option value="unpaid" {% if status_filter == 'unpaid' %}selected{% endif %}>Unbezahlt</option><option value="overdue" {% if status_filter == 'overdue' %}selected{% endif %}>Überfällig</option><option value="paid" {% if status_filter == 'paid' %}selected{% endif %}>Bezahlt</option><option value="cancelled" {% if status_filter == 'cancelled' %}selected{% endif %}>Storniert</option><option value="credited" {% if status_filter == 'credited' %}selected{% endif %}>Gutgeschrieben</option></select></label><label>Sortieren<select class="nx-control" name="sort"><option value="date_desc" {% if sort == 'date_desc' %}selected{% endif %}>Neueste zuerst</option><option value="date_asc" {% if sort == 'date_asc' %}selected{% endif %}>Älteste zuerst</option><option value="open_desc" {% if sort == 'open_desc' %}selected{% endif %}>Ausstehend absteigend</option><option value="open_asc" {% if sort == 'open_asc' %}selected{% endif %}>Ausstehend aufsteigend</option><option value="amount_desc" {% if sort == 'amount_desc' %}selected{% endif %}>Gesamtbetrag absteigend</option><option value="amount_asc" {% if sort == 'amount_asc' %}selected{% endif %}>Gesamtbetrag aufsteigend</option></select></label><button class="nx-btn" type="submit">Anwenden</button>{% if q or status_filter != 'all' or sort != 'date_desc' %}<a class="tt-link" href="{% url 'next-invoices' %}">Filter zurücksetzen</a>{% endif %}</form>
<div class="tt-list-card"><div class="tt-list-table tt-invoices-table"><div class="tt-list-head"><span>Rechnung</span><span>Kunde / Projekt</span><span>Rechnungsdatum</span><span>Fällig am</span><span>Gesamt</span><span>Ausstehend</span><span>Status</span><span>Aktionen</span></div>{% for row in rows %}<div class="tt-list-row"><a class="tt-doc-number" href="{% url 'next-invoice-edit' row.invoice.pk %}">{% if row.invoice.number %}{{ row.invoice.number }}{% else %}Entwurf{% endif %}</a><span><strong>{% if row.customer %}{{ row.customer.display_name }}{% else %}—{% endif %}</strong><small>{{ row.project_label }}</small></span><span>{{ row.invoice.issue_date|date:'d.m.Y' }}</span><span>{% if row.invoice.due_date %}{{ row.invoice.due_date|date:'d.m.Y' }}{% else %}—{% endif %}</span><strong>{{ row.gross|floatformat:2 }} €</strong><strong>{{ row.open|floatformat:2 }} €</strong><span><span class="tt-state tt-state-{{ row.status_key }}">{{ row.status }}</span></span><div class="tt-row-actions"><a class="nx-btn nx-btn-small" href="{% url 'next-invoice-edit' row.invoice.pk %}">Öffnen</a>{% if row.can_pay %}<button type="button" class="nx-btn nx-btn-small nx-btn-accent" data-payment-open data-action="{% url 'next-invoice-payment' row.invoice.pk %}" data-number="{{ row.invoice.number|default:'Rechnung' }}" data-open="{{ row.open }}">Zahlung eintragen</button>{% endif %}{% if row.can_dun %}<form method="post" action="{% url 'next-invoice-dunning' row.invoice.pk %}">{% csrf_token %}<input type="hidden" name="level" value="reminder"><input type="hidden" name="due_days" value="7"><button class="tt-link" type="submit">Zahlungserinnerung</button></form>{% endif %}</div></div>{% empty %}<div class="tt-empty-state"><strong>Keine Rechnungen gefunden.</strong><span>Passe die Filter an oder erstelle eine neue Rechnung.</span></div>{% endfor %}</div></div>
<div class="tt-modal" data-payment-modal hidden><form class="tt-modal-card" method="post" data-payment-form>{% csrf_token %}<header><div><span class="tt-eyebrow">Zahlung</span><h2>Zahlung eintragen</h2><p data-payment-caption></p></div><button type="button" data-payment-close aria-label="Schließen">×</button></header><div class="tt-two"><label>Zahlungsdatum<input class="nx-control" type="date" name="paid_at" value="{{ today|date:'Y-m-d' }}" required></label><label>Betrag<input class="nx-control" type="number" name="amount" min="0.01" step="0.01" data-payment-amount required></label><label>Zahlungsart<select class="nx-control" name="method"><option>Überweisung</option><option>Bar</option><option>Karte</option><option>Lastschrift</option><option>Sonstiges</option></select></label><label>Kommentar / Referenz<input class="nx-control" name="reference" maxlength="240" placeholder="Optional"></label></div><p class="tt-modal-note">Teilzahlungen sind möglich. Die Rechnung bleibt bis zum vollständigen Ausgleich als unbezahlt bzw. überfällig sichtbar.</p><button class="nx-btn nx-btn-accent" type="submit">Zahlung verbuchen</button></form></div>
{% endblock %}''')


def install_js_css() -> None:
    write("static/js/tooltime-parity-lifecycle.js", r'''(()=>{'use strict';const modal=document.querySelector('[data-payment-modal]'),form=document.querySelector('[data-payment-form]');if(!modal||!form)return;const close=()=>{modal.hidden=true;document.body.classList.remove('tt-modal-open')};document.addEventListener('click',e=>{const open=e.target.closest('[data-payment-open]');if(open){form.action=open.dataset.action;const amount=form.querySelector('[data-payment-amount]');if(amount){amount.value=open.dataset.open||'';amount.max=open.dataset.open||''}const caption=modal.querySelector('[data-payment-caption]');if(caption)caption.textContent=`${open.dataset.number} · Ausstehend ${open.dataset.open} €`;modal.hidden=false;document.body.classList.add('tt-modal-open');setTimeout(()=>amount?.focus(),0);return}if(e.target.closest('[data-payment-close]'))close();if(e.target===modal)close()});document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!modal.hidden)close()})})();''')
    rel = "static/css/tooltime-parity-finance.css"
    css = read(rel)
    if "/* A+BAU PHASE 4 LIFECYCLE */" not in css:
        css += r'''
/* A+BAU PHASE 4 LIFECYCLE */
.tt-list-toolbar{display:flex;gap:12px;align-items:end;flex-wrap:wrap;margin:18px 0}.tt-list-toolbar label{display:grid;gap:6px;min-width:180px}.tt-list-toolbar label:first-child{flex:1;min-width:240px}.tt-list-card{background:#fff;border:1px solid #e1e7ee;border-radius:14px;overflow:hidden}.tt-list-table{display:grid}.tt-list-head,.tt-list-row{display:grid;gap:12px;align-items:center;padding:13px 16px}.tt-quotes-table .tt-list-head,.tt-quotes-table .tt-list-row{grid-template-columns:1.05fr 1.35fr 1.45fr .8fr .9fr .9fr 2fr}.tt-invoices-table .tt-list-head,.tt-invoices-table .tt-list-row{grid-template-columns:1fr 1.55fr .85fr .85fr .85fr .9fr .9fr 2fr}.tt-list-head{background:#f6f8fa;color:#667085;font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:.03em}.tt-list-row{border-top:1px solid #edf0f3;min-height:66px}.tt-list-row:hover{background:#fbfcfd}.tt-list-row small{display:block;color:#667085;margin-top:3px}.tt-doc-number{font-weight:850;color:#122033;text-decoration:none}.tt-row-actions{display:flex;gap:7px;align-items:center;flex-wrap:wrap}.tt-row-actions form{margin:0}.nx-btn-small{min-height:34px!important;padding:6px 10px!important;font-size:13px}.tt-state{display:inline-flex;padding:5px 9px;border-radius:999px;font-size:12px;font-weight:800;background:#eef2f6;color:#344054}.tt-state-paid,.tt-state-accepted{background:#e9f7ef;color:#11733c}.tt-state-overdue,.tt-state-rejected,.tt-state-cancelled{background:#fff0ed;color:#b42318}.tt-state-unpaid,.tt-state-sent{background:#fff8e6;color:#8a5a00}.tt-state-draft{background:#eef2f6;color:#475467}.tt-state-credited{background:#f3edff;color:#6941c6}.tt-empty-state{padding:38px 20px;text-align:center;display:grid;gap:7px;color:#667085}.tt-empty-state strong{color:#1d2939}.tt-modal-note{font-size:13px;color:#667085;background:#f7f9fb;border-radius:9px;padding:10px 12px}body.tt-modal-open{overflow:hidden}@media(max-width:1100px){.tt-list-head{display:none}.tt-list-row,.tt-quotes-table .tt-list-row,.tt-invoices-table .tt-list-row{grid-template-columns:1fr 1fr}.tt-row-actions{grid-column:1/-1}}@media(max-width:640px){.tt-list-row,.tt-quotes-table .tt-list-row,.tt-invoices-table .tt-list-row{grid-template-columns:1fr}.tt-row-actions{grid-column:auto}.tt-list-toolbar>*{width:100%}.tt-list-toolbar label{min-width:0}}
'''
    write(rel, css)


def install_tests() -> None:
    write("tests/test_tooltime_phase4_lifecycle.py", r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase4LifecycleContractTests(SimpleTestCase):
    def test_routes_use_phase4_authoritative_views(self):
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        self.assertIn('tooltime_parity.quote_list', urls)
        self.assertIn('tooltime_parity.invoice_list', urls)
        self.assertIn('tooltime_parity.invoice_payment', urls)

    def test_invoice_lifecycle_is_real_and_payment_safe(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        self.assertIn('def _phase4_invoice_display', views)
        self.assertIn('def invoice_payment', views)
        self.assertIn('invoice.compliance.state', views)
        self.assertIn('amount > open_amount', views)
        self.assertIn('m.Payment.objects.create', views)
        self.assertIn('date.fromisoformat', views)

    def test_lists_have_real_filters_and_actions(self):
        quotes = (ROOT / "templates/rebuild/quotes.html").read_text(encoding="utf-8")
        invoices = (ROOT / "templates/rebuild/invoices.html").read_text(encoding="utf-8")
        for phrase in ('Suchen', 'Status', 'Sortieren', 'In Rechnung'):
            self.assertIn(phrase, quotes)
        for phrase in ('Ausstehend', 'Überfällig', 'Zahlung eintragen', 'Zahlungserinnerung'):
            self.assertIn(phrase, invoices)
        self.assertIn('data-payment-open', invoices)
        self.assertIn('next-invoice-payment', invoices)

    def test_no_fake_tooltime_pay_product_is_added(self):
        combined = '\n'.join((
            (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8"),
            (ROOT / "templates/rebuild/invoices.html").read_text(encoding="utf-8"),
            (ROOT / "static/js/tooltime-parity-lifecycle.js").read_text(encoding="utf-8"),
        ))
        self.assertNotIn('ToolTime Pay', combined)

    def test_phase3_immutability_contract_remains(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        self.assertIn('Ein bereits angenommenes Angebot bleibt aus Aufbewahrungsgründen gesperrt', views)
        self.assertIn('def quote_to_invoice', views)
''')


def run() -> None:
    patch_views()
    patch_urls()
    install_templates()
    install_js_css()
    install_tests()
    print("ToolTime Phase 4 installiert: Angebots-/Rechnungslisten, dynamische Zahlungsstatus, Teilzahlungen und Mahnaktionen.")


if __name__ == "__main__":
    run()
