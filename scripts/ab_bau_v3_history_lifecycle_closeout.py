from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU V3 HISTORY LIFECYCLE CLOSEOUT 2026-09-08"
CACHE_VERSION = "20260908-v3-closeout1"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"V3 closeout target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_views() -> None:
    rel = "erp/rebuild_views.py"
    text = read(rel)

    if not re.search(r"^from datetime import .*\btimedelta\b", text, re.M):
        future = "from __future__ import annotations\n"
        if future in text:
            text = text.replace(future, future + "\nfrom datetime import timedelta\n", 1)
        else:
            text = "from datetime import timedelta\n" + text

    customer_pattern = re.compile(
        r'@login_required\n@require_http_methods\(\["GET", "POST"\]\)\ndef customer_detail\(request, pk\):.*?(?=\n@login_required\ndef customer_locations_api\(|\n@login_required\ndef project_list\()',
        re.S,
    )
    match = customer_pattern.search(text)
    if not match:
        raise RuntimeError("V3 closeout could not locate current customer_detail view")
    customer = match.group(0)

    if "AB_V3_HISTORY_CUSTOMER_CONTEXT" not in customer:
        customer = customer.replace(
            "    customer = get_object_or_404(m.Customer, pk=pk, organization=org)\n",
            "    customer = get_object_or_404(m.Customer, pk=pk, organization=org)\n"
            "    field_user = _is_field_user(request)\n",
            1,
        )
        projects_anchor = (
            "    projects = (\n"
            "        customer.projects.filter(organization=org)\n"
            "        .select_related(\"object_location\", \"manager\")\n"
        )
        if projects_anchor not in customer:
            raise RuntimeError("V3 closeout customer project-query anchor missing")
        customer = customer.replace(
            projects_anchor,
            "    direct_title = f\"Direktdokumente · Kunde {customer.pk}\"\n"
            "    projects = (\n"
            "        customer.projects.filter(organization=org)\n"
            "        .exclude(title=direct_title)\n"
            "        .select_related(\"object_location\", \"manager\")\n",
            1,
        )
        appointments_anchor = "        m.CalendarEvent.objects.filter(organization=org, project__customer=customer)\n"
        if appointments_anchor not in customer:
            raise RuntimeError("V3 closeout customer appointment-query anchor missing")
        customer = customer.replace(
            appointments_anchor,
            "        m.CalendarEvent.objects.filter(organization=org)\n"
            "        .filter(Q(customer=customer) | Q(project__customer=customer))\n"
            "        .distinct()\n",
            1,
        )

        render_anchor = '    return render(request, "rebuild/customer_detail.html", {\n'
        if render_anchor not in customer:
            raise RuntimeError("V3 closeout customer render anchor missing")
        history = r'''    # AB_V3_HISTORY_CUSTOMER_CONTEXT
    documented_event_ids = set(
        m.Document.objects.filter(
            organization=org,
            customer=customer,
            category="report",
            metadata__event_id__isnull=False,
        ).values_list("metadata__event_id", flat=True)
    )
    documented_event_ids.update(
        m.Document.objects.filter(
            organization=org,
            project__customer=customer,
            category="report",
            metadata__event_id__isnull=False,
        ).values_list("metadata__event_id", flat=True)
    )
    history = []
    for project in projects[:100]:
        history.append({"kind": "project", "at": project.updated_at, "object": project, "status": project.get_status_display()})
    for event in appointments[:100]:
        documented = event.pk in documented_event_ids
        history.append({
            "kind": "appointment",
            "at": event.starts_at,
            "object": event,
            "status": "Termin dokumentiert" if documented else "Termin geplant",
            "documented": documented,
        })
    for quote in quotes[:100]:
        history.append({"kind": "quote", "at": quote.created_at, "object": quote, "status": quote.get_status_display()})
    for invoice in invoices[:100]:
        history.append({"kind": "invoice", "at": invoice.created_at, "object": invoice, "status": invoice.get_status_display()})
    history.sort(key=lambda row: row["at"], reverse=True)

'''
        customer = customer.replace(render_anchor, history + render_anchor, 1)
        context_anchor = '        "open_invoice_gross": open_invoice_gross,\n'
        if context_anchor not in customer:
            raise RuntimeError("V3 closeout customer context anchor missing")
        customer = customer.replace(
            context_anchor,
            context_anchor
            + '        "history": history,\n'
            + '        "field_user": field_user,\n'
            + '        "direct_document_project_title": direct_title,\n',
            1,
        )

    text = text[: match.start()] + customer + text[match.end() :]

    if "def _customer_direct_document_project(" not in text:
        customer_start = text.find('@login_required\n@require_http_methods(["GET", "POST"])\ndef customer_detail(request, pk):')
        if customer_start < 0:
            raise RuntimeError("V3 closeout customer insertion point missing")
        direct_block = r'''def _customer_direct_document_project(org, customer):
    title = f"Direktdokumente · Kunde {customer.pk}"
    project = m.Project.objects.filter(organization=org, customer=customer, title=title).order_by("pk").first()
    if project is None:
        project = m.Project.objects.create(
            organization=org,
            customer=customer,
            number=_unique_number(m.Project, org, "P"),
            title=title,
            status="inquiry",
            archived=True,
        )
    return project


def _customer_bind_document_meta(document, kind, customer):
    if not hasattr(m, "ToolTimeDocumentMeta"):
        return
    lookup = {"organization": document.organization, kind: document}
    meta, _ = m.ToolTimeDocumentMeta.objects.get_or_create(**lookup)
    if hasattr(meta, "customer_id"):
        meta.customer = customer
        update_fields = ["customer"]
        if hasattr(meta, "updated_at"):
            update_fields.append("updated_at")
        meta.save(update_fields=update_fields)


@login_required
@require_POST
def customer_quote_create(request, pk):
    org = _org(request)
    if _is_field_user(request):
        messages.error(request, "Angebote können nur im Büro erstellt werden.")
        return redirect("next-customer-detail", pk=pk)
    customer = get_object_or_404(m.Customer, pk=pk, organization=org, active=True)
    project = _customer_direct_document_project(org, customer)
    quote = m.Quote.objects.create(
        organization=org,
        project=project,
        number="",
        status="draft",
        issue_date=timezone.localdate(),
        discount_percent=0,
        created_by=request.user,
    )
    _customer_bind_document_meta(quote, "quote", customer)
    return redirect("next-quote-edit", pk=quote.pk)


@login_required
@require_POST
def customer_invoice_create(request, pk):
    org = _org(request)
    if _is_field_user(request):
        messages.error(request, "Rechnungen können nur im Büro erstellt werden.")
        return redirect("next-customer-detail", pk=pk)
    customer = get_object_or_404(m.Customer, pk=pk, organization=org, active=True)
    project = _customer_direct_document_project(org, customer)
    today = timezone.localdate()
    invoice = m.Invoice.objects.create(
        organization=org,
        project=project,
        number="",
        status="draft",
        issue_date=today,
        due_date=today + timedelta(days=14),
        service_date=today,
        created_by=request.user,
    )
    _customer_bind_document_meta(invoice, "invoice", customer)
    return redirect("next-invoice-edit", pk=invoice.pk)


'''
        text = text[:customer_start] + direct_block + text[customer_start:]

    project_start = text.find("@login_required\ndef project_detail(request, pk):")
    if project_start < 0:
        raise RuntimeError("V3 closeout could not locate project_detail view")
    project_end = text.find("\n\n@login_required\ndef appointment_list(request):", project_start)
    if project_end < 0:
        raise RuntimeError("V3 closeout project_detail end anchor missing")
    project = text[project_start:project_end]

    if "AB_V3_HISTORY_PROJECT_CONTEXT" not in project:
        render_anchor = '    return render(request, "rebuild/project_detail.html", {\n'
        if render_anchor not in project:
            raise RuntimeError("V3 closeout project render anchor missing")
        history = r'''    # AB_V3_HISTORY_PROJECT_CONTEXT
    documented_event_ids = set(
        m.Document.objects.filter(
            organization=org,
            project=project,
            category="report",
            metadata__event_id__isnull=False,
        ).values_list("metadata__event_id", flat=True)
    )
    history = []
    for event in appointments:
        documented = event.pk in documented_event_ids
        history.append({
            "kind": "appointment",
            "at": event.starts_at,
            "object": event,
            "status": "Termin dokumentiert" if documented else "Termin geplant",
            "documented": documented,
        })
    for quote in quotes:
        history.append({"kind": "quote", "at": quote.created_at, "object": quote, "status": quote.get_status_display()})
    for invoice in invoices:
        history.append({"kind": "invoice", "at": invoice.created_at, "object": invoice, "status": invoice.get_status_display()})
    for document in documents:
        history.append({"kind": "document", "at": document.created_at, "object": document, "status": document.get_category_display()})
    history.sort(key=lambda row: row["at"], reverse=True)

    latest_invoice = invoices[0] if invoices else None
    latest_quote = quotes[0] if quotes else None
    if project.status == "completed":
        tooltime_status = "Projekt abgeschlossen"
    elif project.status == "cancelled":
        tooltime_status = "Projekt abgebrochen"
    elif latest_invoice is not None:
        if latest_invoice.status == "paid":
            tooltime_status = "Rechnung bezahlt"
        elif latest_invoice.status == "overdue":
            tooltime_status = "Rechnung überfällig"
        elif latest_invoice.status in {"dunned", "reminded"}:
            tooltime_status = "Rechnung angemahnt"
        else:
            tooltime_status = "Rechnung angelegt"
    elif latest_quote is not None:
        tooltime_status = "Angebot angenommen" if latest_quote.status == "accepted" else "Angebot erstellt"
    elif documented_event_ids:
        tooltime_status = "Termin dokumentiert"
    elif appointments:
        tooltime_status = "Termin geplant"
    else:
        tooltime_status = "Neues Projekt"
    has_planned_appointments = any(event.pk not in documented_event_ids for event in appointments)

'''
        project = project.replace(render_anchor, history + render_anchor, 1)
        project_context_anchor = '    return render(request, "rebuild/project_detail.html", {\n'
        if project_context_anchor not in project:
            raise RuntimeError("V3 closeout project render-context anchor missing")
        project = project.replace(
            project_context_anchor,
            project_context_anchor
            + '        "history": history,\n'
            + '        "tooltime_status": tooltime_status,\n'
            + '        "has_planned_appointments": has_planned_appointments,\n',
            1,
        )

    text = text[:project_start] + project + text[project_end:]

    if "def project_lifecycle(request, pk):" not in text:
        appointment_anchor = text.find("\n\n@login_required\ndef appointment_list(request):", project_start)
        if appointment_anchor < 0:
            raise RuntimeError("V3 closeout lifecycle insertion point missing")
        lifecycle = r'''

@login_required
@require_POST
def project_lifecycle(request, pk):
    org = _org(request)
    if _is_field_user(request):
        messages.error(request, "Projektstatus kann nur im Büro geändert werden.")
        return redirect("next-project-detail", pk=pk)
    project = get_object_or_404(m.Project, pk=pk, organization=org)
    action = (request.POST.get("action") or "").strip()

    if action in {"complete", "cancel"}:
        event_ids = list(project.events.values_list("pk", flat=True))
        documented = set(
            m.Document.objects.filter(
                organization=org,
                project=project,
                category="report",
                metadata__event_id__in=event_ids,
            ).values_list("metadata__event_id", flat=True)
        )
        if any(event_id not in documented for event_id in event_ids):
            messages.error(
                request,
                "Das Projekt kann erst abgeschlossen oder abgebrochen werden, wenn keine geplanten Termine mehr enthalten sind.",
            )
            return redirect("next-project-detail", pk=project.pk)
        project.status = "completed" if action == "complete" else "cancelled"
        project.archived = True
        update_fields = ["status", "archived", "updated_at"]
        if action == "complete" and hasattr(project, "progress"):
            project.progress = 100
            update_fields.append("progress")
        project.save(update_fields=update_fields)
        messages.success(
            request,
            "Projekt wurde abgeschlossen." if action == "complete" else "Projekt wurde abgebrochen.",
        )
    elif action == "reactivate":
        project.status = "inquiry"
        project.archived = False
        project.save(update_fields=["status", "archived", "updated_at"])
        messages.success(request, "Projekt wurde reaktiviert.")
    else:
        messages.error(request, "Unbekannte Projektaktion.")
    return redirect("next-project-detail", pk=project.pk)
'''
        text = text[:appointment_anchor] + lifecycle + text[appointment_anchor:]

    compile(text, str(ROOT / rel), "exec")
    write(rel, text)


def patch_urls() -> None:
    rel = "erp/rebuild_urls.py"
    text = read(rel)

    def insert_after(anchor_name: str, routes: tuple[tuple[str, str], ...]) -> None:
        nonlocal text
        missing = [line for route_name, line in routes if f'name="{route_name}"' not in text]
        if not missing:
            return
        marker = f'name="{anchor_name}"'
        pos = text.find(marker)
        if pos < 0:
            raise RuntimeError(f"V3 closeout URL anchor missing: {anchor_name}")
        line_end = text.find("\n", pos)
        if line_end < 0:
            raise RuntimeError(f"V3 closeout URL line boundary missing: {anchor_name}")
        text = text[: line_end + 1] + "".join(missing) + text[line_end + 1 :]

    insert_after(
        "next-customer-detail",
        (
            ("next-customer-quote-create", '    path("customers/<int:pk>/angebot/neu/", views.customer_quote_create, name="next-customer-quote-create"),\n'),
            ("next-customer-invoice-create", '    path("customers/<int:pk>/rechnung/neu/", views.customer_invoice_create, name="next-customer-invoice-create"),\n'),
        ),
    )
    insert_after(
        "next-project-detail",
        (("next-project-lifecycle", '    path("projects/<int:pk>/aktionen/", views.project_lifecycle, name="next-project-lifecycle"),\n'),),
    )
    compile(text, str(ROOT / rel), "exec")
    write(rel, text)


def patch_v3_customer_template_source() -> None:
    rel = "design/v3/phase2/customer_detail.html"
    text = read(rel)
    if "data-ab-v3-customer-history" not in text:
        action_anchor = (
            '      <a class="is-primary" href="{% url \'next-project-create\' %}?customer={{ customer.pk }}">＋ Projekt starten</a>\n'
            "    </div>"
        )
        if action_anchor not in text:
            raise RuntimeError("V3 closeout customer hero-action anchor missing")
        actions = r'''      <a class="is-primary" href="{% url 'next-project-create' %}?customer={{ customer.pk }}">＋ Projekt starten</a>
      {% if not field_user %}
      <form class="ab-v3-inline-action" method="post" action="{% url 'next-customer-quote-create' customer.pk %}">{% csrf_token %}<button type="submit">＋ Angebot</button></form>
      <form class="ab-v3-inline-action" method="post" action="{% url 'next-customer-invoice-create' customer.pk %}">{% csrf_token %}<button type="submit">＋ Rechnung</button></form>
      {% endif %}
    </div>'''
        text = text.replace(action_anchor, actions, 1)

        overview_anchor = "        {% if active_tab == 'overview' %}\n        <div class=\"tt-tab-panel\">\n"
        if overview_anchor not in text:
            raise RuntimeError("V3 closeout customer overview anchor missing")
        history = r'''        {% if active_tab == 'overview' %}
        <div class="tt-tab-panel">
          <section class="tt-section ab-v3-work-section" data-ab-v3-customer-history>
            <div class="tt-section-title ab-v3-section-head"><h3>Kundenverlauf <span>· {{ history|length }}</span></h3></div>
            {% if history %}<div class="ab-v3-history-list">{% for row in history %}<article class="ab-v3-history-row"><time>{{ row.at|date:'d.m.Y' }}<small>{{ row.at|date:'H:i' }}</small></time><div class="ab-v3-history-copy">{% if row.kind == 'project' %}<a href="{% url 'next-project-detail' row.object.pk %}">{{ row.object.title }}</a><span>Projekt · {{ row.object.number }}</span>{% elif row.kind == 'appointment' %}<a href="{% url 'next-appointment-detail' row.object.pk %}">{{ row.object.title }}</a><span>Termin</span>{% elif row.kind == 'quote' %}<a href="{% url 'next-quote-edit' row.object.pk %}">{{ row.object.number|default:'Angebotsentwurf' }}</a><span>Angebot</span>{% else %}<a href="{% url 'next-invoice-edit' row.object.pk %}">{{ row.object.number|default:'Rechnungsentwurf' }}</a><span>Rechnung</span>{% endif %}</div><span class="ab-v3-status">{{ row.status }}</span></article>{% endfor %}</div>{% else %}<div class="tt-empty ab-v3-empty">Noch keine Einträge im Kundenverlauf.</div>{% endif %}
          </section>
'''
        text = text.replace(overview_anchor, history, 1)

        text = text.replace(
            "<td>{{ quote.project.title }}</td>",
            "<td>{% if quote.project.title == direct_document_project_title %}Direkt für Kunde{% else %}{{ quote.project.title }}{% endif %}</td>",
        )
        text = text.replace(
            "<td>{{ invoice.project.title }}</td>",
            "<td>{% if invoice.project.title == direct_document_project_title %}Direkt für Kunde{% else %}{{ invoice.project.title }}{% endif %}</td>",
        )

    if "next-appointment-create" in text:
        raise RuntimeError("V3 closeout would reintroduce duplicate customer appointment creation")
    write(rel, text)


def patch_v3_project_template_source() -> None:
    rel = "design/v3/phase2/project_detail.html"
    text = read(rel)
    if "data-ab-v3-project-history" not in text:
        text = text.replace(
            '<span class="ab-v3-status">{{ project.get_status_display }}</span>',
            '<span class="ab-v3-status">{{ tooltime_status|default:project.get_status_display }}</span>',
            1,
        )
        actions_anchor = (
            "      {% if not field_user %}<a href=\"{% url 'next-quote-create' %}?project={{ project.pk }}\">＋ Angebot</a><a class=\"is-primary\" href=\"{% url 'next-invoice-create' %}?project={{ project.pk }}\">＋ Rechnung</a>{% else %}<a class=\"is-primary\" href=\"{% url 'next-field' %}\">✎ Dokumentieren</a>{% endif %}\n"
            "    </div>"
        )
        if actions_anchor not in text:
            raise RuntimeError("V3 closeout project hero-action anchor missing")
        lifecycle = r'''      {% if not field_user %}<a href="{% url 'next-quote-create' %}?project={{ project.pk }}">＋ Angebot</a><a class="is-primary" href="{% url 'next-invoice-create' %}?project={{ project.pk }}">＋ Rechnung</a>{% else %}<a class="is-primary" href="{% url 'next-field' %}">✎ Dokumentieren</a>{% endif %}
      {% if not field_user %}<details class="ab-v3-lifecycle"><summary>Aktionen ▾</summary><div>{% if project.archived %}<form method="post" action="{% url 'next-project-lifecycle' project.pk %}">{% csrf_token %}<input type="hidden" name="action" value="reactivate"><button type="submit">Projekt reaktivieren</button></form>{% else %}<form method="post" action="{% url 'next-project-lifecycle' project.pk %}">{% csrf_token %}<input type="hidden" name="action" value="complete"><button type="submit" {% if has_planned_appointments %}title="Geplante Termine müssen zuerst dokumentiert werden"{% endif %}>Projekt abschließen</button></form><form method="post" action="{% url 'next-project-lifecycle' project.pk %}">{% csrf_token %}<input type="hidden" name="action" value="cancel"><button type="submit">Projekt abbrechen</button></form>{% endif %}</div></details>{% endif %}
    </div>'''
        text = text.replace(actions_anchor, lifecycle, 1)

        overview_anchor = '        <div class="tt-pd-panel is-active" data-tab-panel="overview">\n'
        if overview_anchor not in text:
            raise RuntimeError("V3 closeout project overview anchor missing")
        history = r'''        <div class="tt-pd-panel is-active" data-tab-panel="overview">
          <section class="tt-pd-section ab-v3-work-section" data-ab-v3-project-history>
            <div class="ab-v3-section-head"><h3>Projektverlauf <span>· {{ history|length }}</span></h3><span class="ab-v3-status">{{ tooltime_status }}</span></div>
            {% if history %}<div class="ab-v3-history-list">{% for row in history %}<article class="ab-v3-history-row"><time>{{ row.at|date:'d.m.Y' }}<small>{{ row.at|date:'H:i' }}</small></time><div class="ab-v3-history-copy">{% if row.kind == 'appointment' %}<a href="{% url 'next-appointment-detail' row.object.pk %}">{{ row.object.title }}</a><span>Termin</span>{% elif row.kind == 'quote' %}<a href="{% url 'next-quote-edit' row.object.pk %}">{{ row.object.number|default:'Angebotsentwurf' }}</a><span>Angebot</span>{% elif row.kind == 'invoice' %}<a href="{% url 'next-invoice-edit' row.object.pk %}">{{ row.object.number|default:'Rechnungsentwurf' }}</a><span>Rechnung</span>{% else %}{% if row.object.file %}<a href="{{ row.object.file.url }}" target="_blank" rel="noopener">{{ row.object.title }}</a>{% else %}<strong>{{ row.object.title }}</strong>{% endif %}<span>Dokument</span>{% endif %}</div><span class="ab-v3-status">{{ row.status }}</span></article>{% endfor %}</div>{% else %}<div class="tt-pd-empty ab-v3-empty">Noch keine Einträge im Projektverlauf.</div>{% endif %}
          </section>
'''
        text = text.replace(overview_anchor, history, 1)

    if "next-room-planner" not in text:
        raise RuntimeError("V3 closeout lost Room Planner Pro")
    if "{% url 'configurator'" in text or "next-configurator" in text:
        raise RuntimeError("V3 closeout reintroduced a legacy configurator route")
    finance_guard = '{% if not field_user %}\n        <div class="tt-pd-panel" data-tab-panel="finance">'
    if finance_guard not in text:
        raise RuntimeError("V3 closeout lost the field-user finance guard")
    write(rel, text)


def patch_v3_css_source() -> None:
    rel = "design/v3/ab-bau-v3-phase2.css"
    text = read(rel)
    if MARKER not in text:
        text += r'''

/* A+BAU V3 HISTORY LIFECYCLE CLOSEOUT 2026-09-08 */
body.ab-v3 .ab-v3-inline-action{display:inline-flex;margin:0}
body.ab-v3 .ab-v3-inline-action button,body.ab-v3 .ab-v3-lifecycle>summary{min-height:42px;display:inline-flex;align-items:center;justify-content:center;padding:0 14px;border:1px solid rgba(255,255,255,.12);border-radius:11px;background:rgba(255,255,255,.04);color:#e6e4de;font:inherit;font-size:10.5px;font-weight:780;cursor:pointer;white-space:nowrap}
body.ab-v3 .ab-v3-inline-action button:hover,body.ab-v3 .ab-v3-lifecycle>summary:hover{border-color:rgba(227,200,117,.45);color:#fff4cf}
body.ab-v3 .ab-v3-lifecycle{position:relative}.ab-v3-lifecycle>summary{list-style:none}.ab-v3-lifecycle>summary::-webkit-details-marker{display:none}.ab-v3-lifecycle>div{position:absolute;z-index:90;right:0;top:calc(100% + 7px);min-width:190px;padding:6px;border:1px solid rgba(255,255,255,.11);border-radius:12px;background:#101319;box-shadow:0 20px 54px rgba(0,0,0,.34)}
body.ab-v3 .ab-v3-lifecycle form{margin:0}.ab-v3-lifecycle button{width:100%;padding:10px;border:0;border-radius:8px;background:transparent;color:#dedbd3;text-align:left;font:inherit;font-size:10px;cursor:pointer}.ab-v3-lifecycle button:hover{background:rgba(255,255,255,.06)}
body.ab-v3 .ab-v3-history-list{display:grid;border:1px solid #e6dfd3;border-radius:14px;overflow:hidden;background:#fffdf9}.ab-v3-history-row{display:grid;grid-template-columns:92px minmax(0,1fr) auto;gap:13px;align-items:center;padding:12px 13px;border-bottom:1px solid #eee8de}.ab-v3-history-row:last-child{border-bottom:0}.ab-v3-history-row time{display:grid;color:#625f59;font-size:9px;font-weight:760}.ab-v3-history-row time small{margin-top:2px;color:#9b958c;font-size:8px;font-weight:600}.ab-v3-history-copy{min-width:0;display:grid;gap:3px}.ab-v3-history-copy a,.ab-v3-history-copy strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#24272b;font-size:10.5px;font-weight:760;text-decoration:none}.ab-v3-history-copy span{color:#999188;font-size:8.5px}
@media(max-width:640px){body.ab-v3 .ab-v3-history-row{grid-template-columns:64px minmax(0,1fr);gap:9px}.ab-v3-history-row>.ab-v3-status{grid-column:2;justify-self:start}.ab-v3-entity-actions .ab-v3-inline-action,.ab-v3-entity-actions .ab-v3-inline-action button,.ab-v3-entity-actions .ab-v3-lifecycle,.ab-v3-entity-actions .ab-v3-lifecycle>summary{width:100%}.ab-v3-lifecycle>div{left:0;right:auto;min-width:100%}}
'''
    write(rel, text)


def patch_phase2_cache_version() -> None:
    rel = "scripts/ab_bau_v3_phase2_customers_projects.py"
    text = read(rel)
    if CACHE_VERSION not in text:
        if "20260908-1" not in text:
            raise RuntimeError("V3 closeout phase2 cache-version anchor missing")
        text = text.replace("20260908-1", CACHE_VERSION)
        write(rel, text)


def install_functional_tests() -> None:
    test = r'''from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from erp.models import CalendarEvent, Customer, Organization, Project, Quote, UserProfile


class ABauV3HistoryLifecycleTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="A+Bau V3 Closeout Test")
        User = get_user_model()
        self.user = User.objects.create_user(username="v3-closeout-office", password="secret")
        profile = self.user.profile
        profile.organization = self.org
        profile.role = UserProfile.Role.ADMIN
        profile.is_mobile_worker = False
        profile.save()
        self.client.force_login(self.user)
        self.customer = Customer.objects.create(
            organization=self.org,
            number="K-V3C",
            type="private",
            first_name="Mara",
            last_name="Muster",
            active=True,
        )
        self.project = Project.objects.create(
            organization=self.org,
            customer=self.customer,
            number="P-V3C",
            title="Badmodernisierung",
            status="inquiry",
            archived=False,
        )

    def test_customer_v3_keeps_cockpit_and_adds_history_and_direct_documents(self):
        response = self.client.get(reverse("next-customer-detail", args=[self.customer.pk]))
        self.assertEqual(response.status_code, 200)
        for marker in ("data-ab-v3-customer-detail", "Kundenverlauf", "＋ Angebot", "＋ Rechnung", "Umsatz (netto)"):
            self.assertContains(response, marker)
        self.assertNotContains(response, "next-appointment-create")

    def test_direct_quote_uses_hidden_customer_document_project(self):
        response = self.client.post(reverse("next-customer-quote-create", args=[self.customer.pk]))
        self.assertEqual(response.status_code, 302)
        quote = Quote.objects.get(organization=self.org)
        self.assertEqual(quote.project.customer_id, self.customer.pk)
        self.assertTrue(quote.project.archived)
        self.assertEqual(quote.status, "draft")
        detail = self.client.get(reverse("next-customer-detail", args=[self.customer.pk]))
        self.assertContains(detail, "Direkt für Kunde")
        self.assertNotContains(detail, quote.project.title)

    def test_project_v3_keeps_room_planner_finance_guard_and_adds_lifecycle(self):
        response = self.client.get(reverse("next-project-detail", args=[self.project.pk]))
        self.assertEqual(response.status_code, 200)
        for marker in ("data-ab-v3-project-detail", "Projektverlauf", "Projekt abschließen", "Projekt abbrechen", "Raum & 3D", "Finanzen"):
            self.assertContains(response, marker)

    def test_planned_appointment_blocks_project_completion(self):
        CalendarEvent.objects.create(
            organization=self.org,
            project=self.project,
            customer=self.customer,
            created_by=self.user,
            title="Montage",
            type="installation",
            starts_at=timezone.now() + timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=1, hours=1),
        )
        response = self.client.post(reverse("next-project-lifecycle", args=[self.project.pk]), {"action": "complete"})
        self.assertEqual(response.status_code, 302)
        self.project.refresh_from_db()
        self.assertFalse(self.project.archived)
        self.assertNotEqual(self.project.status, "completed")

    def test_empty_project_can_complete_and_reactivate(self):
        self.client.post(reverse("next-project-lifecycle", args=[self.project.pk]), {"action": "complete"})
        self.project.refresh_from_db()
        self.assertTrue(self.project.archived)
        self.assertEqual(self.project.status, "completed")
        self.client.post(reverse("next-project-lifecycle", args=[self.project.pk]), {"action": "reactivate"})
        self.project.refresh_from_db()
        self.assertFalse(self.project.archived)
        self.assertEqual(self.project.status, "inquiry")
'''
    write("tests/test_ab_v3_history_lifecycle.py", test)
    compile(test, str(ROOT / "tests" / "test_ab_v3_history_lifecycle.py"), "exec")


def guard() -> None:
    views = read("erp/rebuild_views.py")
    urls = read("erp/rebuild_urls.py")
    customer = read("design/v3/phase2/customer_detail.html")
    project = read("design/v3/phase2/project_detail.html")
    css = read("design/v3/ab-bau-v3-phase2.css")

    for marker in (
        "def customer_quote_create",
        "def customer_invoice_create",
        "AB_V3_HISTORY_CUSTOMER_CONTEXT",
        "AB_V3_HISTORY_PROJECT_CONTEXT",
        "def project_lifecycle",
    ):
        if marker not in views:
            raise RuntimeError(f"V3 closeout view guard missing: {marker}")
    for marker in ("next-customer-quote-create", "next-customer-invoice-create", "next-project-lifecycle"):
        if marker not in urls:
            raise RuntimeError(f"V3 closeout route guard missing: {marker}")
    for marker in ("data-ab-v3-customer-history", "Kundenverlauf", "next-customer-quote-create", "next-customer-invoice-create"):
        if marker not in customer:
            raise RuntimeError(f"V3 closeout customer UI guard missing: {marker}")
    if "next-appointment-create" in customer:
        raise RuntimeError("V3 closeout customer detail restored duplicate appointment creation")
    for marker in ("data-ab-v3-project-history", "Projektverlauf", "next-project-lifecycle", "next-room-planner", 'data-tab-panel="finance"'):
        if marker not in project:
            raise RuntimeError(f"V3 closeout project UI guard missing: {marker}")
    if "{% url 'configurator'" in project or "next-configurator" in project:
        raise RuntimeError("V3 closeout project detail restored legacy configurator")
    if '{% if not field_user %}\n        <div class="tt-pd-panel" data-tab-panel="finance">' not in project:
        raise RuntimeError("V3 closeout finance visibility guard missing")
    if MARKER not in css:
        raise RuntimeError("V3 closeout CSS marker missing")


def main() -> None:
    patch_views()
    patch_urls()
    patch_v3_customer_template_source()
    patch_v3_project_template_source()
    patch_v3_css_source()
    patch_phase2_cache_version()
    install_functional_tests()
    guard()
    print(f"{MARKER}: current V3 cockpits retain Room Planner/finance safety and gain history, direct documents and project lifecycle.")


if __name__ == "__main__":
    main()
