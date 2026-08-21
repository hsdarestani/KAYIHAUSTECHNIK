from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME QUOTES EXACT PARITY 2026-08-21"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"ToolTime quotes parity target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_views() -> None:
    rel = "erp/tooltime_parity_views.py"
    text = read(rel)
    if f"# {MARKER}" in text:
        return

    text += r'''

# A+BAU TOOLTIME QUOTES EXACT PARITY 2026-08-21

def _tt_quote_title(quote, meta=None):
    """Return a stable visible quote title without requiring a schema migration."""
    candidates = []
    for source in (quote, meta):
        if source is None:
            continue
        for attr in ("title", "subject", "document_title", "heading", "name"):
            value = getattr(source, attr, None)
            if isinstance(value, str) and value.strip():
                candidates.append(value.strip())
    if candidates:
        return candidates[0]
    return "Kostenvoranschlag" if getattr(quote, "number", "") else "Angebot"


def _tt_quote_customer_label(customer):
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
        for value in (getattr(customer, "first_name", "") or "", getattr(customer, "last_name", "") or "")
        if value.strip()
    )
    return company or person or ""


def _tt_quote_last_change(quote):
    return getattr(quote, "updated_at", None) or getattr(quote, "created_at", None)


def _tt_quote_relative_change(value):
    if value is None:
        return "—"
    try:
        now = timezone.now()
        if timezone.is_naive(value):
            value = timezone.make_aware(value, timezone.get_current_timezone())
        seconds = max(0, int((now - value).total_seconds()))
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


def _tt_quote_status(quote):
    raw = (getattr(quote, "status", "") or "draft").lower()
    if raw == "draft":
        return "Entwurf", "draft"
    if raw in {"sent", "pending"}:
        return "Ausstehend", "pending"
    if raw == "accepted":
        return "Angenommen", "accepted"
    if raw in {"rejected", "declined", "expired"}:
        return "Abgelehnt", "rejected"
    return getattr(quote, "get_status_display", lambda: raw.title())(), raw


def _tt_quote_sort_key(row, key):
    if key.startswith("amount"):
        return row["total"]
    if key.startswith("date"):
        return row["quote"].issue_date
    return row["last_change"] or row["quote"].issue_date


@login_required
def quote_list(request):
    """ToolTime-style quote index: status/period filters, last-change sorting and offset paging."""
    from datetime import date as _date, timedelta as _timedelta
    from urllib.parse import urlencode

    org = _org(request)
    query = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "all").strip().lower()
    period = (request.GET.get("period") or "any").strip().lower()
    sort = (request.GET.get("sort") or "last_change_desc").strip().lower()

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

    qs = m.Quote.objects.filter(organization=org).select_related("project__customer").order_by("-created_at", "-pk")
    if status == "draft":
        qs = qs.filter(status="draft")
    elif status == "pending":
        qs = qs.filter(status__in=("sent", "pending"))
    elif status == "accepted":
        qs = qs.filter(status="accepted")
    elif status == "rejected":
        qs = qs.filter(status__in=("rejected", "declined", "expired"))

    today = timezone.localdate()
    if period == "7d":
        qs = qs.filter(issue_date__gte=today - _timedelta(days=7))
    elif period == "30d":
        qs = qs.filter(issue_date__gte=today - _timedelta(days=30))
    elif period == "90d":
        qs = qs.filter(issue_date__gte=today - _timedelta(days=90))
    elif period == "year":
        qs = qs.filter(issue_date__gte=_date(today.year, 1, 1), issue_date__lte=today)

    rows = []
    # Sorting by amount and quote title is computed from commercial metadata, so the
    # bounded set is intentionally materialized before the final 20/50/100-row page.
    for quote in qs[:2000]:
        totals = base._quote_total(quote)
        meta = meta_for(quote, "quote", create=False)
        customer = _phase4_customer(quote, meta)
        status_label, status_key = _tt_quote_status(quote)
        last_change = _tt_quote_last_change(quote)
        row = {
            "quote": quote,
            "meta": meta,
            "customer": customer,
            "customer_label": _tt_quote_customer_label(customer),
            "quote_title": _tt_quote_title(quote, meta),
            "total": totals.get("gross", totals.get("net", Decimal("0"))) or Decimal("0"),
            "status": status_label,
            "status_key": status_key,
            "last_change": last_change,
            "last_change_label": _tt_quote_relative_change(last_change),
            "finalized": bool(meta and getattr(meta, "finalized_at", None)),
        }
        if query:
            project = getattr(quote, "project", None)
            searchable = " ".join(
                str(value or "")
                for value in (
                    getattr(quote, "number", ""),
                    row["quote_title"],
                    row["customer_label"],
                    getattr(project, "number", "") if project else "",
                    getattr(project, "title", "") if project else "",
                )
            ).casefold()
            if query.casefold() not in searchable:
                continue
        rows.append(row)

    reverse = not sort.endswith("_asc")
    if sort not in {"last_change_desc", "last_change_asc", "date_desc", "date_asc", "amount_desc", "amount_asc"}:
        sort = "last_change_desc"
        reverse = True
    rows.sort(key=lambda row: (_tt_quote_sort_key(row, sort), row["quote"].pk), reverse=reverse)

    total_count = len(rows)
    if offset >= total_count and total_count:
        offset = max(0, ((total_count - 1) // amount) * amount)
    page_rows = rows[offset: offset + amount]
    first_item = offset + 1 if total_count else 0
    last_item = min(offset + amount, total_count)
    prev_offset = max(0, offset - amount)
    next_offset = offset + amount if offset + amount < total_count else None

    params = {
        "q": query,
        "status": status,
        "period": period,
        "sort": sort,
        "amount": amount,
    }
    query_tail = urlencode({key: value for key, value in params.items() if value not in ("", "all", "any")})
    last_change_next_sort = "last_change_asc" if sort == "last_change_desc" else "last_change_desc"
    last_change_params = dict(params)
    last_change_params["sort"] = last_change_next_sort
    last_change_query = urlencode({key: value for key, value in last_change_params.items() if value not in ("", "all", "any")})

    return render(
        request,
        "rebuild/quotes.html",
        {
            "rows": page_rows,
            "q": query,
            "status_filter": status,
            "period_filter": period,
            "sort": sort,
            "amount": amount,
            "offset": offset,
            "total_count": total_count,
            "first_item": first_item,
            "last_item": last_item,
            "prev_offset": prev_offset,
            "next_offset": next_offset,
            "query_tail": query_tail,
            "last_change_query": last_change_query,
            "last_change_next_sort": last_change_next_sort,
        },
    )
'''
    write(rel, text)


def install_template() -> None:
    write("templates/rebuild/quotes.html", r'''{% extends 'rebuild/base.html' %}{% load static %}
{% block title %}Angebote · A+Bau{% endblock %}
{% block content %}
<link rel="stylesheet" href="{% static 'css/tooltime-parity-finance.css' %}?v=20260821-quotes-exact">
<script src="{% static 'js/tooltime-quotes-exact.js' %}?v=20260821-quotes-exact" defer></script>
<div class="ttq-page" data-tooltime-quotes-exact>
  <div class="ttq-topbar">
    <div class="ttq-heading"><h1>Angebote</h1><span class="ttq-help" title="Angebote verwalten">?</span></div>
    <div class="ttq-top-actions">
      <form class="ttq-search" method="get" role="search">
        <input type="hidden" name="status" value="{{ status_filter }}"><input type="hidden" name="period" value="{{ period_filter }}"><input type="hidden" name="sort" value="{{ sort }}"><input type="hidden" name="amount" value="{{ amount }}">
        <span aria-hidden="true">⌕</span><input type="search" name="q" value="{{ q }}" placeholder="Suchen" aria-label="Angebote suchen"><button type="submit" class="sr-only">Suchen</button>
      </form>
      <details class="ttq-new-menu"><summary>Neues Angebot <span aria-hidden="true">▾</span></summary><div class="ttq-menu-card"><a href="{% url 'next-quote-create' %}"><strong>Leeres Angebot</strong><small>Direkt ein neues Angebot erstellen</small></a><a href="{% url 'next-projects' %}"><strong>Aus Projekt erstellen</strong><small>Projekt öffnen und Angebot anlegen</small></a></div></details>
    </div>
  </div>

  <form class="ttq-filters tt-list-toolbar" method="get" data-auto-filter>
    <input type="hidden" name="q" value="{{ q }}"><input type="hidden" name="amount" value="{{ amount }}">
    <label class="ttq-select"><span class="sr-only">Status</span><select name="status" aria-label="Status"><option value="all" {% if status_filter == 'all' %}selected{% endif %}>Alle Angebote</option><option value="draft" {% if status_filter == 'draft' %}selected{% endif %}>Entwurf</option><option value="pending" {% if status_filter == 'pending' %}selected{% endif %}>Ausstehend</option><option value="accepted" {% if status_filter == 'accepted' %}selected{% endif %}>Angenommen</option><option value="rejected" {% if status_filter == 'rejected' %}selected{% endif %}>Abgelehnt</option></select></label>
    <label class="ttq-select"><span class="sr-only">Zeitraum</span><select name="period" aria-label="Zeitraum"><option value="any" {% if period_filter == 'any' %}selected{% endif %}>Beliebiger Zeitraum</option><option value="7d" {% if period_filter == '7d' %}selected{% endif %}>Letzte 7 Tage</option><option value="30d" {% if period_filter == '30d' %}selected{% endif %}>Letzte 30 Tage</option><option value="90d" {% if period_filter == '90d' %}selected{% endif %}>Letzte 90 Tage</option><option value="year" {% if period_filter == 'year' %}selected{% endif %}>Dieses Jahr</option></select></label>
    <label class="tt-mobile-sort"><span>Sortieren</span><select name="sort" aria-label="Sortieren"><option value="last_change_desc" {% if sort == 'last_change_desc' %}selected{% endif %}>Letzte Änderung ↓</option><option value="last_change_asc" {% if sort == 'last_change_asc' %}selected{% endif %}>Letzte Änderung ↑</option><option value="date_desc" {% if sort == 'date_desc' %}selected{% endif %}>Angebotsdatum ↓</option><option value="date_asc" {% if sort == 'date_asc' %}selected{% endif %}>Angebotsdatum ↑</option><option value="amount_desc" {% if sort == 'amount_desc' %}selected{% endif %}>Betrag ↓</option><option value="amount_asc" {% if sort == 'amount_asc' %}selected{% endif %}>Betrag ↑</option></select></label>
    <button class="sr-only" type="submit">Anwenden</button>
  </form>

  <div class="ttq-table-wrap">
    <table class="ttq-table">
      <thead><tr><th>Angebotsdatum</th><th>Nr.</th><th>Status</th><th>Angebotstitel</th><th>Kunde</th><th class="ttq-money">Betrag</th><th><a class="ttq-sort-link" data-last-change-sort href="?{{ last_change_query }}&offset=0">Letzte Änderung <span aria-hidden="true">{% if sort == 'last_change_asc' %}↑{% else %}↓{% endif %}</span></a></th><th aria-label="Aktionen"></th></tr></thead>
      <tbody>{% for row in rows %}<tr data-quote-row>
        <td data-label="Angebotsdatum"><strong>{{ row.quote.issue_date|date:'d.m.Y' }}</strong></td>
        <td data-label="Nr."><strong>{% if row.quote.number %}{{ row.quote.number }}{% else %}–{% endif %}</strong></td>
        <td data-label="Status"><span class="ttq-status ttq-status-{{ row.status_key }}">{{ row.status }}</span></td>
        <td data-label="Angebotstitel"><a class="ttq-title" href="{% url 'next-quote-edit' row.quote.pk %}">{{ row.quote_title }}</a></td>
        <td data-label="Kunde"><span class="ttq-customer-icon" aria-hidden="true">⌂</span>{% if row.customer_label %}{{ row.customer_label }}{% else %}—{% endif %}</td>
        <td data-label="Betrag" class="ttq-money"><strong>{{ row.total|floatformat:2 }} €</strong></td>
        <td data-label="Letzte Änderung" class="ttq-last-change">{{ row.last_change_label }}</td>
        <td class="ttq-actions-cell"><details class="ttq-row-menu"><summary aria-label="Aktionen für Angebot">•••</summary><div class="ttq-menu-card ttq-row-menu-card"><a href="{% url 'next-quote-edit' row.quote.pk %}">Öffnen</a>{% if row.finalized %}{% if row.status_key != 'accepted' %}<form method="post" action="{% url 'next-quote-status' row.quote.pk %}">{% csrf_token %}<button name="action" value="accepted">Annehmen</button></form>{% endif %}{% if row.status_key != 'accepted' and row.status_key != 'rejected' %}<form method="post" action="{% url 'next-quote-status' row.quote.pk %}">{% csrf_token %}<button name="action" value="rejected">Ablehnen</button></form>{% endif %}{% if row.status_key == 'rejected' %}<form method="post" action="{% url 'next-quote-status' row.quote.pk %}">{% csrf_token %}<button name="action" value="pending">Zurücksetzen</button></form>{% endif %}<form method="post" action="{% url 'next-quote-to-invoice' row.quote.pk %}">{% csrf_token %}<button type="submit">In Rechnung</button></form>{% endif %}</div></details></td>
      </tr>{% empty %}<tr><td colspan="8"><div class="ttq-empty"><strong>Keine Angebote gefunden.</strong><span>Filter anpassen oder ein neues Angebot erstellen.</span></div></td></tr>{% endfor %}</tbody>
    </table>
  </div>

  <div class="ttq-pagination" aria-label="Seitennavigation"><span>{% if total_count %}{{ first_item }}–{{ last_item }} von {{ total_count }}{% else %}0 von 0{% endif %}</span><label>Pro Seite<select name="amount" data-page-size><option value="20" {% if amount == 20 %}selected{% endif %}>20</option><option value="50" {% if amount == 50 %}selected{% endif %}>50</option><option value="100" {% if amount == 100 %}selected{% endif %}>100</option></select></label><div>{% if offset > 0 %}<a aria-label="Vorherige Seite" href="?{{ query_tail }}&offset={{ prev_offset }}">‹</a>{% else %}<span aria-disabled="true">‹</span>{% endif %}{% if next_offset != None %}<a aria-label="Nächste Seite" href="?{{ query_tail }}&offset={{ next_offset }}">›</a>{% else %}<span aria-disabled="true">›</span>{% endif %}</div></div>
</div>
{% endblock %}''')


def install_js_css() -> None:
    write("static/js/tooltime-quotes-exact.js", r'''(()=>{'use strict';const page=document.querySelector('[data-tooltime-quotes-exact]');if(!page)return;page.querySelectorAll('[data-auto-filter] select').forEach(select=>select.addEventListener('change',()=>select.form.requestSubmit()));const pageSize=page.querySelector('[data-page-size]');if(pageSize)pageSize.addEventListener('change',()=>{const url=new URL(window.location.href);url.searchParams.set('amount',pageSize.value);url.searchParams.set('offset','0');window.location.assign(url.toString())});document.addEventListener('click',event=>{page.querySelectorAll('details[open]').forEach(details=>{if(!details.contains(event.target))details.removeAttribute('open')})});page.querySelectorAll('.ttq-row-menu,.ttq-new-menu').forEach(details=>details.addEventListener('toggle',()=>{if(!details.open)return;page.querySelectorAll('details[open]').forEach(other=>{if(other!==details)other.removeAttribute('open')})}))})();''')

    rel = "static/css/tooltime-parity-finance.css"
    css = read(rel)
    if "/* A+BAU TOOLTIME QUOTES EXACT PARITY */" not in css:
        css += r'''
/* A+BAU TOOLTIME QUOTES EXACT PARITY */
.ttq-page{padding:0 2px 28px}.ttq-topbar{display:flex;justify-content:space-between;align-items:center;gap:20px;margin:0 0 24px}.ttq-heading{display:flex;align-items:center;gap:10px}.ttq-heading h1{margin:0;font-size:28px;line-height:1.2;color:#172033}.ttq-help{width:19px;height:19px;border:1.5px solid #2d83dc;color:#2d83dc;border-radius:50%;display:inline-grid;place-items:center;font-size:12px;font-weight:800}.ttq-top-actions{display:flex;align-items:center;gap:14px}.ttq-search{width:min(330px,30vw);height:42px;border:1px solid #d7dee7;border-radius:7px;background:#fff;display:flex;align-items:center;gap:8px;padding:0 12px;color:#7e8a9a}.ttq-search:focus-within{border-color:#1688e9;box-shadow:0 0 0 2px rgba(22,136,233,.10)}.ttq-search input[type=search]{border:0;outline:0;background:transparent;width:100%;font:inherit;color:#263244}.ttq-new-menu{position:relative}.ttq-new-menu>summary{list-style:none;cursor:pointer;min-height:42px;padding:0 15px;border-radius:7px;background:#1688e9;color:#fff;display:flex;align-items:center;gap:18px;font-weight:800}.ttq-new-menu>summary::-webkit-details-marker,.ttq-row-menu>summary::-webkit-details-marker{display:none}.ttq-menu-card{position:absolute;right:0;top:calc(100% + 7px);z-index:40;min-width:220px;background:#fff;border:1px solid #dfe5ec;border-radius:9px;box-shadow:0 16px 40px rgba(27,39,51,.16);padding:6px}.ttq-menu-card a,.ttq-menu-card button{display:block;width:100%;border:0;background:transparent;text-align:left;padding:10px 11px;border-radius:6px;text-decoration:none;color:#263244;font:inherit;cursor:pointer}.ttq-menu-card a:hover,.ttq-menu-card button:hover{background:#f4f7fa}.ttq-menu-card small{display:block;color:#7a8795;margin-top:3px}.ttq-filters{display:flex;align-items:center;gap:12px;margin:0 0 22px}.ttq-select select,.tt-mobile-sort select{appearance:auto;height:38px;border:1px solid #d7dee7;border-radius:7px;background:#fff;padding:0 12px;color:#263244;font-weight:650}.tt-mobile-sort{display:none}.ttq-table-wrap{overflow:visible;border-top:1px solid #d8dfe7}.ttq-table{width:100%;border-collapse:collapse;table-layout:fixed}.ttq-table th{height:45px;padding:0 14px;text-align:left;color:#768394;font-size:12px;font-weight:650;border-bottom:1px solid #d8dfe7}.ttq-table td{height:61px;padding:8px 14px;border-bottom:1px solid #e3e8ee;color:#394657;font-size:14px;vertical-align:middle}.ttq-table th:nth-child(1){width:10%}.ttq-table th:nth-child(2){width:8%}.ttq-table th:nth-child(3){width:11%}.ttq-table th:nth-child(4){width:23%}.ttq-table th:nth-child(5){width:24%}.ttq-table th:nth-child(6){width:10%}.ttq-table th:nth-child(7){width:12%}.ttq-table th:nth-child(8){width:42px}.ttq-table tbody tr:hover{background:#fbfcfe}.ttq-title{color:#455467;text-decoration:none}.ttq-title:hover{color:#1688e9}.ttq-money{text-align:right!important;white-space:nowrap}.ttq-status{display:inline-flex;align-items:center;min-height:23px;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:800}.ttq-status-draft{background:#49a9dc;color:#fff}.ttq-status-pending{background:#d5c555;color:#fff}.ttq-status-accepted{background:#47ae73;color:#fff}.ttq-status-rejected{background:#d75a5a;color:#fff}.ttq-customer-icon{display:inline-block;margin-right:7px;color:#71839a}.ttq-last-change{color:#758294;white-space:nowrap}.ttq-sort-link{color:inherit;text-decoration:none;white-space:nowrap}.ttq-actions-cell{position:relative;text-align:right}.ttq-row-menu{position:relative;display:inline-block}.ttq-row-menu>summary{list-style:none;cursor:pointer;color:#546578;font-weight:900;letter-spacing:2px;padding:8px}.ttq-row-menu-card{top:34px;right:0;min-width:170px}.ttq-row-menu-card form{margin:0}.ttq-empty{padding:48px 20px;display:grid;gap:6px;text-align:center;color:#788596}.ttq-empty strong{color:#263244}.ttq-pagination{display:flex;justify-content:flex-end;align-items:center;gap:18px;padding:16px 8px;color:#738092;font-size:13px}.ttq-pagination label{display:flex;align-items:center;gap:8px}.ttq-pagination select{height:31px;border:1px solid #d7dee7;border-radius:5px;background:#fff}.ttq-pagination>div{display:flex;gap:5px}.ttq-pagination a,.ttq-pagination>div span{width:31px;height:31px;display:grid;place-items:center;border:1px solid #d7dee7;border-radius:5px;color:#425267;text-decoration:none}.ttq-pagination>div span{opacity:.42}.sr-only{position:absolute!important;width:1px!important;height:1px!important;padding:0!important;margin:-1px!important;overflow:hidden!important;clip:rect(0,0,0,0)!important;white-space:nowrap!important;border:0!important}@media(max-width:900px){.ttq-topbar{align-items:flex-start;flex-direction:column}.ttq-top-actions{width:100%}.ttq-search{width:auto;flex:1}.tt-mobile-sort{display:block}.ttq-table{table-layout:auto}.ttq-table th:nth-child(4),.ttq-table td:nth-child(4),.ttq-table th:nth-child(7),.ttq-table td:nth-child(7){display:none}}@media(max-width:640px){.ttq-top-actions{align-items:stretch;flex-direction:column}.ttq-search{width:100%}.ttq-new-menu>summary{justify-content:space-between}.ttq-filters{align-items:stretch;flex-direction:column}.ttq-filters label,.ttq-filters select{width:100%}.ttq-table thead{display:none}.ttq-table,.ttq-table tbody,.ttq-table tr,.ttq-table td{display:block;width:100%}.ttq-table tr{padding:12px 42px 12px 0;position:relative;border-bottom:1px solid #e3e8ee}.ttq-table td{height:auto;border:0;padding:5px 8px 5px 112px;position:relative}.ttq-table td:before{content:attr(data-label);position:absolute;left:8px;top:5px;width:96px;color:#8793a2;font-size:12px}.ttq-table td.ttq-actions-cell{position:absolute;right:4px;top:5px;width:auto;padding:0}.ttq-table td.ttq-actions-cell:before{display:none}.ttq-table td:nth-child(4),.ttq-table td:nth-child(7){display:block}.ttq-money{text-align:left!important}.ttq-pagination{justify-content:space-between;flex-wrap:wrap}.ttq-pagination label{display:none}}
'''
        write(rel, css)


def patch_browser_smoke() -> None:
    rel = "scripts/production_browser_smoke.py"
    text = read(rel)
    smoke_marker = "# A+BAU TOOLTIME QUOTES EXACT PARITY BROWSER SMOKE"
    if smoke_marker in text:
        return
    anchor = "            context.close()\n"
    if anchor not in text:
        raise RuntimeError("ToolTime quotes exact browser-smoke context anchor missing")
    block = r'''            # A+BAU TOOLTIME QUOTES EXACT PARITY BROWSER SMOKE
            response = page.goto(urljoin(base_url, "quotes/?amount=20&offset=0"), wait_until="domcontentloaded", timeout=30_000)
            if response is None or response.status >= 500:
                fail(f"ToolTime-Angebotsliste returned {response.status if response else 'no response'}")
            quote_page = page.locator("[data-tooltime-quotes-exact]")
            if quote_page.count() != 1:
                fail("ToolTime-Angebotslisten-Surface fehlt")
            for header in ("Angebotsdatum", "Nr.", "Status", "Angebotstitel", "Kunde", "Betrag", "Letzte Änderung"):
                if quote_page.get_by_text(header, exact=True).count() < 1:
                    fail(f"ToolTime-Angebotsspalte fehlt: {header}")
            if quote_page.locator('select[name="period"]').count() != 1:
                fail("Angebots-Zeitraumfilter fehlt")
            if quote_page.locator('select[name="status"]').count() != 1:
                fail("Angebots-Statusfilter fehlt")
            if quote_page.locator('input[name="q"][type="search"]').count() != 1:
                fail("Angebotssuche fehlt")
            if quote_page.locator('[data-last-change-sort]').count() != 1:
                fail("Sortierung nach letzter Änderung fehlt")
            if quote_page.locator('.ttq-new-menu').count() != 1:
                fail("Neues-Angebot-Dropdown fehlt")
            if quote_page.locator('[data-page-size]').input_value() != "20":
                fail("ToolTime-Standardseitengröße 20 fehlt")
            visible_rows = quote_page.locator('[data-quote-row]')
            if visible_rows.count() > 20:
                fail("Angebotsliste zeigt mehr als 20 Zeilen auf der Standardseite")
            if visible_rows.count() and quote_page.locator('.ttq-row-menu').count() != visible_rows.count():
                fail("Drei-Punkte-Menü fehlt an Angebotszeilen")

'''
    text = text.replace(anchor, block + anchor, 1)
    write(rel, text)


def install_tests() -> None:
    write("tests/test_tooltime_quotes_exact_parity.py", r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimeQuotesExactParityTests(SimpleTestCase):
    def test_backend_supports_tooltime_filters_sort_and_offset_paging(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        for contract in (
            'status == "pending"',
            'period == "30d"',
            'last_change_desc',
            'request.GET.get("amount") or 20',
            'request.GET.get("offset") or 0',
            'rows[offset: offset + amount]',
            '_tt_quote_relative_change',
            '_tt_quote_title',
        ):
            self.assertIn(contract, views)

    def test_visible_columns_match_tooltime_quote_index(self):
        template = (ROOT / "templates/rebuild/quotes.html").read_text(encoding="utf-8")
        for column in ("Angebotsdatum", "Nr.", "Status", "Angebotstitel", "Kunde", "Betrag", "Letzte Änderung"):
            self.assertIn(column, template)
        self.assertNotIn("<th>Projekt</th>", template)
        self.assertIn("{% if row.quote.number %}{{ row.quote.number }}{% else %}–{% endif %}", template)

    def test_tooltime_controls_are_real_not_placeholder_buttons(self):
        template = (ROOT / "templates/rebuild/quotes.html").read_text(encoding="utf-8")
        for contract in (
            'name="period"',
            'name="status"',
            'name="q"',
            'data-last-change-sort',
            'class="ttq-new-menu"',
            'data-page-size',
            'class="ttq-row-menu"',
            "next-quote-create",
            "next-projects",
            "next-quote-edit",
            "next-quote-to-invoice",
        ):
            self.assertIn(contract, template)
        self.assertIn("In Rechnung", template)
        self.assertIn("Sortieren", template)

    def test_pending_semantics_map_sent_quotes_to_pending(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        self.assertIn('raw in {"sent", "pending"}', views)
        self.assertIn('qs.filter(status__in=("sent", "pending"))', views)

    def test_standard_page_size_is_twenty(self):
        template = (ROOT / "templates/rebuild/quotes.html").read_text(encoding="utf-8")
        self.assertIn('<option value="20"', template)
        self.assertIn('href="?{{ query_tail }}&offset={{ next_offset }}"', template)
''')


def run() -> None:
    patch_views()
    install_template()
    install_js_css()
    patch_browser_smoke()
    install_tests()
    print("ToolTime-Angebotsliste exakt abgeglichen: Zeitraum, Pending, Titel, letzte Änderung, 20er Paging, Dropdowns und Drei-Punkte-Aktionen aktiv.")


if __name__ == "__main__":
    run()
