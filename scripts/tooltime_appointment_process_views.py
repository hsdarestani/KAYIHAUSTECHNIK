from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _block(text: str, start_marker: str, end_markers: tuple[str, ...], label: str):
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f"Appointment parity: {label} start fehlt")
    ends = [text.find(marker, start + len(start_marker)) for marker in end_markers]
    ends = [value for value in ends if value >= 0]
    if not ends:
        raise RuntimeError(f"Appointment parity: {label} end fehlt")
    end = min(ends)
    return start, end, text[start:end]


def patch_views(module) -> None:
    rel = "erp/rebuild_views.py"
    text = module.read(rel)
    if "from django.urls import reverse\n" not in text:
        anchor = "from django.utils import timezone\n"
        if anchor not in text:
            raise RuntimeError("Appointment parity: timezone import fehlt")
        text = text.replace(anchor, anchor + "from django.urls import reverse\n", 1)

    create_marker = '@login_required\n@require_http_methods(["GET", "POST"])\ndef appointment_create(request):\n'
    if "def _appointment_source_quote(" not in text:
        pos = text.find(create_marker)
        if pos < 0:
            raise RuntimeError("Appointment parity: appointment_create fehlt")
        helpers = r'''def _appointment_event_customer(event):
    if event.project_id and getattr(event.project, "customer_id", None):
        return event.project.customer
    return getattr(event, "customer", None)


def _appointment_source_quote(request, org):
    raw = (request.POST.get("source_quote") if request.method == "POST" else request.GET.get("quote")) or ""
    raw = str(raw).strip()
    if not raw.isdigit():
        return None
    return m.Quote.objects.filter(
        organization=org, pk=int(raw), status="accepted"
    ).select_related("project__customer").prefetch_related("items").first()


def _appointment_seed_groups(*, event=None, quote=None, request=None):
    if request is not None and request.method == "POST" and request.POST.get("service_editor_present") == "1":
        titles = request.POST.getlist("service_group_title")
        group_indexes = request.POST.getlist("service_group_index")
        descriptions = request.POST.getlist("service_description")
        kinds = request.POST.getlist("service_kind")
        quantities = request.POST.getlist("service_quantity")
        units = request.POST.getlist("service_unit")
        catalog_ids = request.POST.getlist("service_catalog_id")
        purchase_prices = request.POST.getlist("service_purchase_price")
        unit_prices = request.POST.getlist("service_unit_price")
        taxes = request.POST.getlist("service_tax_rate")
        mixed_payloads = request.POST.getlist("service_mixed_json")
        source_ids = request.POST.getlist("service_source_quote_item_id")
        result = []
        for group_index, title in enumerate(titles):
            items = []
            for index, description in enumerate(descriptions):
                if index >= len(group_indexes) or str(group_indexes[index]) != str(group_index):
                    continue
                description = (description or "").strip()
                if not description:
                    continue
                items.append({
                    "kind": kinds[index] if index < len(kinds) else "other",
                    "quantity": quantities[index] if index < len(quantities) else "1",
                    "unit": units[index] if index < len(units) else "Stk.",
                    "description": description,
                    "catalog_item_id": catalog_ids[index] if index < len(catalog_ids) else "",
                    "purchase_price": purchase_prices[index] if index < len(purchase_prices) else "0",
                    "unit_price": unit_prices[index] if index < len(unit_prices) else "0",
                    "tax_rate": taxes[index] if index < len(taxes) else "19",
                    "mixed_json": mixed_payloads[index] if index < len(mixed_payloads) else "[]",
                    "source_quote_item_id": source_ids[index] if index < len(source_ids) else "",
                })
            result.append({"title": (title or "").strip(), "items": items})
        return result
    if event is not None:
        result = []
        for group in event.service_groups.prefetch_related("items__catalog_item").all().order_by("position", "id"):
            items = []
            for item in group.items.all().order_by("position", "id"):
                items.append({
                    "kind": item.kind, "quantity": str(item.quantity), "unit": item.unit,
                    "description": item.description, "catalog_item_id": item.catalog_item_id or "",
                    "purchase_price": str(item.purchase_price), "unit_price": str(item.unit_price),
                    "tax_rate": str(item.tax_rate),
                    "mixed_json": json.dumps(item.mixed_payload or [], ensure_ascii=False),
                    "source_quote_item_id": item.source_quote_item_id or "",
                })
            result.append({"title": group.title, "items": items})
        return result
    if quote is not None:
        grouped, order = {}, []
        items = quote.items.select_related("catalog_item").prefetch_related("tooltime_mixed_subitems").order_by("position", "pk")
        for item in items:
            try:
                meta = item.commercial_meta
            except Exception:
                meta = None
            title = (getattr(meta, "group_title", "") or "").strip()
            key = title or "__default__"
            if key not in grouped:
                grouped[key] = []
                order.append(key)
            mixed = [{
                "item_type": sub.item_type, "description": sub.description,
                "quantity": str(sub.quantity), "unit": sub.unit,
                "purchase_price": str(sub.purchase_price), "sales_price": str(sub.sales_price),
            } for sub in item.tooltime_mixed_subitems.all().order_by("sort_order", "id")]
            grouped[key].append({
                "kind": getattr(meta, "position_type", "other") if meta else "other",
                "quantity": str(item.quantity), "unit": item.unit, "description": item.description,
                "catalog_item_id": item.catalog_item_id or "",
                "purchase_price": str(getattr(meta, "purchase_price", 0) or 0),
                "unit_price": str(item.unit_price), "tax_rate": str(item.tax_rate),
                "mixed_json": json.dumps(mixed, ensure_ascii=False), "source_quote_item_id": item.pk,
            })
        return [{"title": "" if key == "__default__" else key, "items": grouped[key]} for key in order]
    return []


def _appointment_save_services(event, request, source_quote=None):
    if request.POST.get("service_editor_present") != "1" and source_quote is None:
        return
    groups = _appointment_seed_groups(quote=source_quote, request=request)
    event.service_items.all().delete()
    event.service_groups.all().delete()
    for group_position, row in enumerate(groups, start=1):
        group = m.AppointmentServiceGroup.objects.create(
            organization=event.organization, event=event,
            title=(row.get("title") or "")[:220], position=group_position,
        )
        for item_position, row_item in enumerate(row.get("items") or [], start=1):
            catalog = None
            catalog_id = str(row_item.get("catalog_item_id") or "").strip()
            if catalog_id.isdigit():
                catalog = m.CatalogItem.objects.filter(
                    organization=event.organization, active=True, pk=int(catalog_id)
                ).first()
            source_item = None
            source_id = str(row_item.get("source_quote_item_id") or "").strip()
            if source_id.isdigit():
                source_item = m.QuoteItem.objects.filter(
                    quote__organization=event.organization, pk=int(source_id)
                ).first()
            kind = str(row_item.get("kind") or "other")
            if kind not in {"labour", "material", "mixed", "other"}:
                kind = "other"
            try:
                mixed = json.loads(row_item.get("mixed_json") or "[]")
            except (TypeError, ValueError, json.JSONDecodeError):
                mixed = []
            m.AppointmentServiceItem.objects.create(
                organization=event.organization, event=event, group=group,
                catalog_item=catalog, source_quote_item=source_item, position=item_position, kind=kind,
                code=(catalog.code if catalog else "")[:80],
                description=str(row_item.get("description") or "").strip(),
                quantity=_money(row_item.get("quantity") or 1),
                unit=str(row_item.get("unit") or (catalog.unit if catalog else "Stk."))[:30],
                purchase_price=max(Decimal("0"), _money(row_item.get("purchase_price") or (catalog.purchase_price if catalog else 0))),
                unit_price=max(Decimal("0"), _money(row_item.get("unit_price") or (catalog.sales_price if catalog else 0))),
                tax_rate=max(Decimal("0"), _money(row_item.get("tax_rate") or (catalog.tax_rate if catalog else 19))),
                mixed_payload=mixed if isinstance(mixed, list) else [],
            )


def _appointment_clone_services(source, target):
    target.service_items.all().delete()
    target.service_groups.all().delete()
    for group in source.service_groups.prefetch_related("items").all().order_by("position", "id"):
        target_group = m.AppointmentServiceGroup.objects.create(
            organization=target.organization, event=target, title=group.title, position=group.position
        )
        for item in group.items.all().order_by("position", "id"):
            m.AppointmentServiceItem.objects.create(
                organization=target.organization, event=target, group=target_group,
                catalog_item=item.catalog_item, source_quote_item=item.source_quote_item,
                position=item.position, kind=item.kind, code=item.code, description=item.description,
                quantity=item.quantity, unit=item.unit, purchase_price=item.purchase_price,
                unit_price=item.unit_price, tax_rate=item.tax_rate, mixed_payload=item.mixed_payload,
            )


def _appointment_service_snapshot(event):
    rows = []
    for group in event.service_groups.prefetch_related("items").all().order_by("position", "id"):
        for item in group.items.all().order_by("position", "id"):
            rows.append({
                "group": group.title, "kind": item.kind, "description": item.description,
                "quantity": str(item.quantity), "unit": item.unit, "catalog_item_id": item.catalog_item_id,
            })
    return rows


def _appointment_direct_project(event):
    if event.project_id:
        return event.project
    customer = _appointment_event_customer(event)
    if customer is None:
        return None
    title = f"Direktdokumente · Kunde {customer.pk}"
    project = m.Project.objects.filter(
        organization=event.organization, customer=customer, title=title
    ).order_by("pk").first()
    if project is None:
        project = m.Project.objects.create(
            organization=event.organization, customer=customer,
            number=_unique_number(m.Project, event.organization, "P"), title=title,
            status="inquiry", archived=True,
        )
    return project


def _appointment_bind_customer_meta(document, kind, customer):
    if customer is None or not hasattr(m, "ToolTimeDocumentMeta"):
        return
    lookup = {"organization": document.organization, kind: document}
    meta, _ = m.ToolTimeDocumentMeta.objects.get_or_create(**lookup)
    if hasattr(meta, "customer_id"):
        meta.customer = customer
        meta.save(update_fields=["customer", "updated_at"])


def _appointment_copy_services_to_document(event, document, kind):
    for item in event.service_items.select_related("catalog_item", "group").all().order_by("group__position", "position", "id"):
        kwargs = {
            "position": item.position, "description": item.description,
            "quantity": item.quantity, "unit": item.unit, "unit_price": item.unit_price,
            "tax_rate": item.tax_rate, "catalog_item": item.catalog_item,
        }
        kwargs[kind] = document
        target = (m.QuoteItem if kind == "quote" else m.InvoiceItem).objects.create(**kwargs)
        if hasattr(m, "CommercialItemMeta"):
            meta_kwargs = {
                "organization": event.organization,
                "position_type": item.kind,
                "purchase_price": item.purchase_price,
                "markup_percent": (((item.unit_price / item.purchase_price) - Decimal("1")) * Decimal("100")) if item.purchase_price > 0 else Decimal("0"),
                "group_title": item.group.title if item.group_id else "",
                ("quote_item" if kind == "quote" else "invoice_item"): target,
            }
            m.CommercialItemMeta.objects.create(**meta_kwargs)
        if item.mixed_payload and hasattr(m, "ToolTimeMixedSubitem"):
            for sub_index, sub in enumerate(item.mixed_payload):
                if not isinstance(sub, dict) or not str(sub.get("description") or "").strip():
                    continue
                sub_kwargs = {
                    "organization": event.organization,
                    "item_type": str(sub.get("item_type") or "other")[:16],
                    "description": str(sub.get("description") or "")[:300],
                    "quantity": _money(sub.get("quantity") or 1),
                    "unit": str(sub.get("unit") or "Stk.")[:30],
                    "purchase_price": max(Decimal("0"), _money(sub.get("purchase_price") or 0)),
                    "sales_price": max(Decimal("0"), _money(sub.get("sales_price") or 0)),
                    "sort_order": sub_index,
                    ("quote_item" if kind == "quote" else "invoice_item"): target,
                }
                m.ToolTimeMixedSubitem.objects.create(**sub_kwargs)


def _appointment_apply_field_services(event, request):
    ids = request.POST.getlist("document_service_id")
    kinds = request.POST.getlist("document_service_kind")
    quantities = request.POST.getlist("document_service_quantity")
    units = request.POST.getlist("document_service_unit")
    descriptions = request.POST.getlist("document_service_description")
    catalog_ids = request.POST.getlist("document_service_catalog_id")
    onsite_group = None
    for index, description in enumerate(descriptions):
        description = (description or "").strip()
        if not description:
            continue
        raw_id = ids[index] if index < len(ids) else ""
        item = event.service_items.filter(pk=int(raw_id)).first() if str(raw_id).isdigit() else None
        catalog = None
        raw_catalog = catalog_ids[index] if index < len(catalog_ids) else ""
        if str(raw_catalog).isdigit():
            catalog = m.CatalogItem.objects.filter(
                organization=event.organization, active=True, pk=int(raw_catalog)
            ).first()
        kind = kinds[index] if index < len(kinds) else "other"
        if catalog is not None:
            kind = "labour" if catalog.kind == "service" else ("material" if catalog.kind == "material" else "other")
        if kind not in {"labour", "material", "mixed", "other"}:
            kind = "other"
        if item is None:
            if onsite_group is None:
                onsite_group, _ = m.AppointmentServiceGroup.objects.get_or_create(
                    organization=event.organization, event=event, title="Vor Ort ergänzt",
                    defaults={"position": event.service_groups.count() + 1},
                )
            item = m.AppointmentServiceItem(
                organization=event.organization, event=event, group=onsite_group,
                position=onsite_group.items.count() + 1,
                purchase_price=catalog.purchase_price if catalog else 0,
                unit_price=catalog.sales_price if catalog else 0,
                tax_rate=catalog.tax_rate if catalog else 19,
            )
        elif catalog is not None and item.catalog_item_id != catalog.pk:
            item.purchase_price, item.unit_price, item.tax_rate = catalog.purchase_price, catalog.sales_price, catalog.tax_rate
        item.catalog_item = catalog or item.catalog_item
        item.kind = kind
        item.description = description
        item.quantity = _money(quantities[index] if index < len(quantities) else 1)
        item.unit = (units[index] if index < len(units) else (catalog.unit if catalog else "Stk.")) or "Stk."
        item.save()


'''
        text = text[:pos] + helpers + text[pos:]

    start, end, create = _block(
        text, create_marker,
        ('\n\n@login_required\n@require_http_methods(["GET", "POST"])\ndef appointment_edit(request, pk):\n',),
        "appointment_create",
    )
    if "source_quote = _appointment_source_quote(request, org)" not in create:
        create = create.replace("    org = _org(request)\n", "    org = _org(request)\n    source_quote = _appointment_source_quote(request, org)\n", 1)
    initial_anchor = '    initial = {"starts_at": now + timedelta(hours=1), "ends_at": now + timedelta(hours=2)}\n'
    initial_new = initial_anchor + '    if source_quote is not None and source_quote.project_id and not request.GET.get("project"):\n        initial["project"] = str(source_quote.project_id)\n'
    if initial_new not in create:
        if initial_anchor not in create:
            raise RuntimeError("Appointment parity: create initial anchor fehlt")
        create = create.replace(initial_anchor, initial_new, 1)
    if "event.source_quote = source_quote" not in create:
        anchor = "        event.created_by = request.user\n"
        if anchor not in create:
            raise RuntimeError("Appointment parity: create author anchor fehlt")
        create = create.replace(
            anchor,
            anchor + '        event.source_quote = source_quote\n        event.work_report = (request.POST.get("work_report") or "").strip()\n',
            1,
        )
    if "_appointment_save_services(event, request, source_quote)" not in create:
        anchor = "        form.save_m2m()\n"
        if anchor not in create:
            raise RuntimeError("Appointment parity: create m2m anchor fehlt")
        create = create.replace(anchor, anchor + "        _appointment_save_services(event, request, source_quote)\n", 1)
    if "source_quote=event.source_quote" not in create:
        anchor = "                    created_by=event.created_by,\n"
        if anchor not in create:
            raise RuntimeError("Appointment parity: recurrence author anchor fehlt")
        create = create.replace(
            anchor,
            anchor + "                    source_quote=event.source_quote,\n                    work_report=event.work_report,\n",
            1,
        )
    if "_appointment_clone_services(event, occurrence)" not in create:
        anchor = "                if attendees:\n                    occurrence.attendees.set(attendees)\n"
        if anchor not in create:
            raise RuntimeError("Appointment parity: recurrence attendees anchor fehlt")
        create = create.replace(anchor, anchor + "                _appointment_clone_services(event, occurrence)\n", 1)
    context_anchor = '''        "repeat_until": repeat_until.isoformat() if repeat_until else "",
    })'''
    context_new = '''        "repeat_until": repeat_until.isoformat() if repeat_until else "",
        "appointment_service_groups": _appointment_seed_groups(quote=source_quote, request=request),
        "appointment_catalog": m.CatalogItem.objects.filter(organization=org, active=True).order_by("name")[:500],
        "source_quote": source_quote,
    })'''
    if context_new not in create:
        if context_anchor not in create:
            raise RuntimeError("Appointment parity: create context anchor fehlt")
        create = create.replace(context_anchor, context_new, 1)
    text = text[:start] + create + text[end:]

    edit_marker = '@login_required\n@require_http_methods(["GET", "POST"])\ndef appointment_edit(request, pk):\n'
    start, end, edit = _block(
        text, edit_marker,
        ('\n\n@login_required\n@require_POST\ndef appointment_delete(request, pk):\n', '\n\n@login_required\ndef appointment_detail(request, pk):\n'),
        "appointment_edit",
    )
    if "_appointment_save_services(updated, request, None)" not in edit:
        anchor = "        form.save_m2m()\n"
        if anchor not in edit:
            raise RuntimeError("Appointment parity: edit m2m anchor fehlt")
        edit = edit.replace(
            anchor,
            anchor + '        updated.work_report = (request.POST.get("work_report") or "").strip()\n        updated.save(update_fields=["work_report", "updated_at"])\n        _appointment_save_services(updated, request, None)\n',
            1,
        )
    if "_appointment_clone_services(updated, occurrence)" not in edit:
        anchor = "                occurrence.attendees.set(attendees)\n"
        if anchor not in edit:
            raise RuntimeError("Appointment parity: series attendee anchor fehlt")
        edit = edit.replace(anchor, anchor + "                _appointment_clone_services(updated, occurrence)\n", 1)
    if "occurrence.work_report = updated.work_report" not in edit:
        anchor = "                occurrence.notes = updated.notes\n"
        if anchor not in edit:
            raise RuntimeError("Appointment parity: series notes anchor fehlt")
        edit = edit.replace(anchor, anchor + "                occurrence.work_report = updated.work_report\n", 1)
    context_anchor = '''        "repeat_until": event.recurrence_until.isoformat() if event.recurrence_until else "",
    })'''
    context_new = '''        "repeat_until": event.recurrence_until.isoformat() if event.recurrence_until else "",
        "appointment_service_groups": _appointment_seed_groups(event=event, request=request),
        "appointment_catalog": m.CatalogItem.objects.filter(organization=org, active=True).order_by("name")[:500],
        "source_quote": event.source_quote,
    })'''
    if context_new not in edit:
        if context_anchor not in edit:
            raise RuntimeError("Appointment parity: edit context anchor fehlt")
        edit = edit.replace(context_anchor, context_new, 1)
    text = text[:start] + edit + text[end:]

    detail_marker = '@login_required\ndef appointment_detail(request, pk):\n'
    start, end, _ = _block(text, detail_marker, ('\n\n@login_required\ndef field_home(request):\n',), "appointment_detail")
    detail = r'''@login_required
def appointment_detail(request, pk):
    org = _org(request)
    event = get_object_or_404(
        m.CalendarEvent.objects.select_related("project", "project__customer", "project__object_location", "customer", "source_quote"),
        pk=pk, organization=org,
    )
    docs = m.Document.objects.filter(organization=org, metadata__event_id=event.pk).order_by("-created_at")
    documented = docs.filter(category="report").exists()
    employee = _employee(request, org)
    running = None
    if employee and event.project:
        running = m.TimeEntry.objects.filter(
            organization=org, employee=employee, project=event.project, ended_at__isnull=True
        ).order_by("-started_at").first()
    return render(request, "rebuild/appointment_detail.html", {
        "event": event, "documents": docs, "documented": documented,
        "running": running, "employee": employee,
        "service_groups": event.service_groups.prefetch_related("items__catalog_item").all().order_by("position", "id"),
        "appointment_catalog": m.CatalogItem.objects.filter(organization=org, active=True).order_by("name")[:500],
        "event_customer": _appointment_event_customer(event),
    })
'''
    text = text[:start] + detail + text[end:]

    document_marker = '@login_required\n@require_POST\ndef appointment_document(request, pk):\n'
    start, end, _ = _block(
        text, document_marker,
        ('\n\n@login_required\n@require_POST\ndef ai_structure_report(request, pk):\n',),
        "appointment_document",
    )
    document = r'''@login_required
@require_POST
def appointment_document(request, pk):
    org = _org(request)
    event = get_object_or_404(
        m.CalendarEvent.objects.select_related("project", "project__customer", "customer"), pk=pk, organization=org
    )
    customer = _appointment_event_customer(event)
    if customer is None:
        return JsonResponse({"ok": False, "error": "Dem Termin muss ein Kunde zugeordnet sein."}, status=400)
    _appointment_apply_field_services(event, request)
    report_text = (request.POST.get("report_text") or "").strip()
    services = (request.POST.get("services") or "").strip()
    material = (request.POST.get("material") or "").strip()
    customer_name = (request.POST.get("customer_name") or "").strip()
    body = report_text or event.work_report or "Vor-Ort-Dokumentation"
    payload = {
        "event_id": event.pk, "event_title": event.title,
        "services": services, "material": material, "customer_name": customer_name,
        "service_items": _appointment_service_snapshot(event), "source": "kayi-next-field",
    }
    report = m.Document(
        organization=org, customer=customer, project=event.project,
        title=f"Arbeitsbericht · {event.title} · {timezone.localdate():%d.%m.%Y}",
        category="report", mime_type="text/plain", size=len(body.encode("utf-8")),
        metadata=payload, uploaded_by=request.user,
    )
    report.file.save(f"arbeitsbericht-{event.pk}-{timezone.now():%Y%m%d%H%M%S}.txt", ContentFile(body.encode("utf-8")), save=False)
    report.save()
    for upload in request.FILES.getlist("photos"):
        photo = m.Document(
            organization=org, customer=customer, project=event.project,
            title=upload.name, category="photo", mime_type=getattr(upload, "content_type", "") or "",
            size=getattr(upload, "size", 0) or 0,
            metadata={"event_id": event.pk, "source": "kayi-next-field"}, uploaded_by=request.user,
        )
        photo.file.save(upload.name, upload, save=False)
        photo.save()
    signature_data = request.POST.get("signature_data") or ""
    if signature_data.startswith("data:image/png;base64,"):
        try:
            raw = base64.b64decode(signature_data.split(",", 1)[1])
            signature = m.Document(
                organization=org, customer=customer, project=event.project,
                title=f"Kundenunterschrift · {customer_name or customer.display_name}", category="other",
                mime_type="image/png", size=len(raw),
                metadata={"event_id": event.pk, "kind": "customer_signature"}, uploaded_by=request.user,
            )
            signature.file.save(f"signature-{event.pk}.png", ContentFile(raw), save=False)
            signature.save()
        except Exception:
            pass
    if event.project and event.project.status in {"inquiry", "planning", "quoted", "confirmed"}:
        event.project.status = "in_progress"
        event.project.actual_start = event.project.actual_start or timezone.localdate()
        event.project.save(update_fields=["status", "actual_start", "updated_at"])
    return JsonResponse({"ok": True, "redirect": f"/appointments/{event.pk}/"})
'''
    text = text[:start] + document + text[end:]

    quote_list_marker = '\n\n@login_required\ndef quote_list(request):\n'
    if "def appointment_from_quote(request, pk):" not in text:
        pos = text.find(quote_list_marker)
        if pos < 0:
            raise RuntimeError("Appointment parity: quote_list anchor fehlt")
        actions = r'''

@login_required
@require_POST
def appointment_from_quote(request, pk):
    org = _org(request)
    if _is_field_user(request):
        messages.error(request, "Termine aus Angeboten können nur im Büro erstellt werden.")
        return redirect("next-quotes")
    quote = get_object_or_404(m.Quote.objects.select_related("project__customer"), organization=org, pk=pk)
    if quote.status != "accepted":
        messages.error(request, "Ein Termin kann erst aus einem angenommenen Angebot erstellt werden.")
        return redirect("next-quote-edit", pk=quote.pk)
    return redirect(f"{reverse('next-appointment-create')}?quote={quote.pk}")


@login_required
@require_POST
def appointment_to_quote(request, pk):
    org = _org(request)
    if _is_field_user(request):
        messages.error(request, "Angebote können nur im Büro erstellt werden.")
        return redirect("next-appointment-detail", pk=pk)
    event = get_object_or_404(
        m.CalendarEvent.objects.select_related("project__customer", "customer"), organization=org, pk=pk
    )
    customer = _appointment_event_customer(event)
    if customer is None:
        messages.error(request, "Für ein Angebot muss dem Termin ein Kunde zugeordnet sein.")
        return redirect("next-appointment-detail", pk=event.pk)
    quote = m.Quote.objects.create(
        organization=org, project=_appointment_direct_project(event), source_event=event,
        number="", status="draft", issue_date=timezone.localdate(), discount_percent=0, created_by=request.user,
    )
    _appointment_bind_customer_meta(quote, "quote", customer)
    _appointment_copy_services_to_document(event, quote, "quote")
    messages.success(request, "Angebotsentwurf wurde aus dem Termin erstellt. Alle Leistungen wurden übernommen.")
    return redirect("next-quote-edit", pk=quote.pk)


@login_required
@require_POST
def appointment_to_invoice(request, pk):
    org = _org(request)
    if _is_field_user(request):
        messages.error(request, "Rechnungen können nur im Büro erstellt werden.")
        return redirect("next-appointment-detail", pk=pk)
    event = get_object_or_404(
        m.CalendarEvent.objects.select_related("project__customer", "customer"), organization=org, pk=pk
    )
    customer = _appointment_event_customer(event)
    if customer is None:
        messages.error(request, "Für eine Rechnung muss dem Termin ein Kunde zugeordnet sein.")
        return redirect("next-appointment-detail", pk=event.pk)
    documented = m.Document.objects.filter(
        organization=org, category="report", metadata__event_id=event.pk
    ).exists()
    if not documented:
        messages.error(request, "Eine Rechnung kann erst aus einem dokumentierten Termin erstellt werden.")
        return redirect("next-appointment-detail", pk=event.pk)
    today = timezone.localdate()
    invoice = m.Invoice.objects.create(
        organization=org, project=_appointment_direct_project(event), source_event=event,
        number="", status="draft", issue_date=today, due_date=today + timedelta(days=14),
        service_date=today, created_by=request.user,
    )
    _appointment_bind_customer_meta(invoice, "invoice", customer)
    _appointment_copy_services_to_document(event, invoice, "invoice")
    messages.success(request, "Rechnungsentwurf wurde aus dem dokumentierten Termin erstellt. Alle Leistungen und gespeicherten Preise wurden übernommen.")
    return redirect("next-invoice-edit", pk=invoice.pk)
'''
        text = text[:pos] + actions + text[pos:]

    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def patch_urls(module) -> None:
    rel = "erp/rebuild_urls.py"
    text = module.read(rel)
    appt_anchor = '    path("appointments/<int:pk>/edit/", views.appointment_edit, name="next-appointment-edit"),\n'
    routes = (
        '    path("appointments/<int:pk>/angebot/", views.appointment_to_quote, name="next-appointment-to-quote"),\n'
        '    path("appointments/<int:pk>/rechnung/", views.appointment_to_invoice, name="next-appointment-to-invoice"),\n'
    )
    if routes[0] not in text:
        if appt_anchor not in text:
            raise RuntimeError("Appointment parity: appointment URL anchor fehlt")
        text = text.replace(appt_anchor, appt_anchor + "".join(routes), 1)
    quote_anchor = '    path("quotes/<int:pk>/rechnung/", tooltime_parity.quote_to_invoice, name="next-quote-to-invoice"),\n'
    quote_route = '    path("quotes/<int:pk>/termin/", views.appointment_from_quote, name="next-quote-to-appointment"),\n'
    if quote_route not in text:
        if quote_anchor not in text:
            raise RuntimeError("Appointment parity: quote URL anchor fehlt")
        text = text.replace(quote_anchor, quote_route + quote_anchor, 1)
    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def run(module) -> None:
    patch_views(module)
    patch_urls(module)
