from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME FINANCE COMPLETION 2026-08-20"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"ToolTime-Abschluss: Datei fehlt: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_service() -> None:
    rel = "erp/services/tooltime_parity_finance.py"
    text = read(rel)
    text = text.replace(
        '"logo": {"show": True, "position": "right", "size": "large", "document_id": None},\n        "sender_line": {"show": True},\n        "footer": {"show": True, "mode": "standard", "columns": []},',
        '"logo": {"show": True, "position": "right", "size": "large", "document_id": None},\n        "letterhead": {"show": False, "document_id": None},\n        "sender_line": {"show": True},\n        "footer": {"show": True, "mode": "standard", "columns": []},',
        1,
    )
    text = text.replace(
        '"quote_prefix": "A-", "quote_start": 1,\n            "invoice_prefix": "R-", "invoice_start": 1,\n            "credit_prefix": "GS-", "credit_start": 1,\n            "customer_auto": False, "customer_prefix": "K-", "customer_start": 1,',
        '"quote_prefix": "A-", "quote_start": 1, "quote_width": 1,\n            "invoice_prefix": "R-", "invoice_start": 1, "invoice_width": 1,\n            "credit_prefix": "GS-", "credit_start": 1, "credit_width": 1,\n            "customer_auto": False, "customer_prefix": "K-", "customer_start": 1, "customer_width": 1,',
        1,
    )
    old = '''def _number_settings(org, kind):
    cfg = profile_for(org).settings.get("numbering", {})
    if kind == "quote": return str(cfg.get("quote_prefix") or "A-")[:30], int(cfg.get("quote_start") or 1)
    if kind == "credit": return str(cfg.get("credit_prefix") or "GS-")[:30], int(cfg.get("credit_start") or 1)
    return str(cfg.get("customer_prefix") or "K-")[:30], int(cfg.get("customer_start") or 1)


def allocate_number(org, kind):
    prefix, start = _number_settings(org, kind)
    with transaction.atomic():
        seq, created = m.ToolTimeNumberSequence.objects.select_for_update().get_or_create(organization=org, kind=kind, defaults={"prefix": prefix, "next_value": max(1, start), "width": max(1, len(str(start)))})
        if created is False and seq.prefix != prefix:
            seq.prefix = prefix
        if seq.next_value < start:
            seq.next_value = start
        value = seq.next_value
        seq.next_value = value + 1
        seq.width = max(seq.width, len(str(start)))
        seq.save(update_fields=["prefix", "next_value", "width", "updated_at"])
    return f"{prefix}{value:0{seq.width}d}"
'''
    new = '''def _number_settings(org, kind):
    cfg = profile_for(org).settings.get("numbering", {})
    if kind == "quote": return str(cfg.get("quote_prefix") or "A-")[:30], int(cfg.get("quote_start") or 1), int(cfg.get("quote_width") or 1)
    if kind == "credit": return str(cfg.get("credit_prefix") or "GS-")[:30], int(cfg.get("credit_start") or 1), int(cfg.get("credit_width") or 1)
    return str(cfg.get("customer_prefix") or "K-")[:30], int(cfg.get("customer_start") or 1), int(cfg.get("customer_width") or 1)


def allocate_number(org, kind):
    prefix, start, width = _number_settings(org, kind)
    with transaction.atomic():
        seq, created = m.ToolTimeNumberSequence.objects.select_for_update().get_or_create(organization=org, kind=kind, defaults={"prefix": prefix, "next_value": max(1, start), "width": max(1, width)})
        if created is False and seq.prefix != prefix:
            seq.prefix = prefix
        if seq.next_value < start:
            seq.next_value = start
        value = seq.next_value
        seq.next_value = value + 1
        seq.width = max(1, width)
        seq.save(update_fields=["prefix", "next_value", "width", "updated_at"])
    return f"{prefix}{value:0{seq.width}d}"
'''
    if old not in text:
        raise RuntimeError("ToolTime-Abschluss: Nummernservice-Anker fehlt.")
    text = text.replace(old, new, 1)
    write(rel, text)


def patch_invoice_numbering() -> None:
    rel = "erp/services/invoice_compliance_service.py"
    text = read(rel)
    old = '''def _number_settings(org):
    settings = _settings(org)
    prefix = str(settings.get("invoice_number_prefix") or "RE").strip()[:20] or "RE"
    digits = max(3, min(int(settings.get("invoice_number_digits") or 5), 12))
    start = max(1, int(settings.get("invoice_number_start") or 1))
    return prefix, digits, start


def allocate_number(invoice) -> str:
    prefix, digits, start = _number_settings(invoice.organization)
    year = invoice.issue_date.year
    seq, created = m.InvoiceNumberSequence.objects.select_for_update().get_or_create(
        organization=invoice.organization,
        year=year,
        prefix=prefix,
        defaults={"digits": digits, "next_value": start},
    )
    if not created and seq.digits != digits:
        seq.digits = digits
    value = seq.next_value
    seq.next_value = value + 1
    seq.save(update_fields=["digits", "next_value", "updated_at"])
    return f"{prefix}-{year}-{value:0{seq.digits}d}"
'''
    new = '''def _number_settings(org):
    try:
        profile = org.tooltime_commercial_profile
        config = profile.settings.get("numbering", {}) if isinstance(profile.settings, dict) else {}
    except Exception:
        config = {}
    prefix = str(config.get("invoice_prefix") or "R-")[:20]
    raw_start = str(config.get("invoice_start") or "1")
    start = max(1, int(raw_start or "1"))
    digits = max(1, min(int(config.get("invoice_width") or len(raw_start) or 1), 12))
    return prefix, digits, start


def allocate_number(invoice) -> str:
    prefix, digits, start = _number_settings(invoice.organization)
    # ToolTime-Parität: ein fortlaufender Nummernkreis, kein erzwungenes Jahressegment.
    seq, created = m.InvoiceNumberSequence.objects.select_for_update().get_or_create(
        organization=invoice.organization,
        year=0,
        prefix=prefix,
        defaults={"digits": digits, "next_value": start},
    )
    if seq.next_value < start:
        seq.next_value = start
    seq.digits = digits
    value = seq.next_value
    seq.next_value = value + 1
    seq.save(update_fields=["digits", "next_value", "updated_at"])
    return f"{prefix}{value:0{seq.digits}d}"
'''
    if old not in text:
        raise RuntimeError("ToolTime-Abschluss: Invoice-Nummernanker fehlt.")
    text = text.replace(old, new, 1)
    write(rel, text)


def patch_tags() -> None:
    rel = "erp/templatetags/tooltime_parity.py"
    text = read(rel)
    old = '    customers = list(m.Customer.objects.filter(organization=org, active=True).order_by("company", "last_name", "first_name")[:300])\n    dunning = list(document.tooltime_dunning_records.select_related("document").all()) if kind == "invoice" and document is not None else []\n    return {"cfg": commercial.settings, "meta": meta, "templates": templates, "customers": customers, "dunning": dunning}\n'
    new = '    customers = list(m.Customer.objects.filter(organization=org, active=True).order_by("company", "last_name", "first_name")[:300])\n    projects = list(m.Project.objects.filter(organization=org, archived=False).select_related("customer").order_by("-updated_at")[:400])\n    dunning = list(document.tooltime_dunning_records.select_related("document").all()) if kind == "invoice" and document is not None else []\n    return {"cfg": commercial.settings, "meta": meta, "templates": templates, "customers": customers, "projects": projects, "dunning": dunning}\n'
    if old not in text:
        raise RuntimeError("ToolTime-Abschluss: Template-Tag-Anker fehlt.")
    write(rel, text.replace(old, new, 1))


def patch_views() -> None:
    rel = "erp/tooltime_parity_views.py"
    text = read(rel)
    text = text.replace(
        "from django.core.files.base import ContentFile\nfrom django.db.models import Q",
        "from django.core.files.base import ContentFile\nfrom django.core.mail import EmailMessage\nfrom django.db import transaction\nfrom django.db.models import Q",
        1,
    )
    helper_anchor = "def _redirect_pk(response):\n"
    helper = r'''def _sequence_number_for_customer(org, posted=""):
    cfg = profile_for(org).settings.get("numbering", {})
    if cfg.get("customer_auto"):
        return allocate_number(org, "customer")
    manual = (posted or "").strip()[:30]
    if manual and not m.Customer.objects.filter(organization=org, number=manual).exists():
        return manual
    return base._unique_number(m.Customer, org, "K")


def _ensure_document_project(request, org):
    if request.method != "POST" or request.POST.get("project"):
        return
    customer_id = (request.POST.get("selected_customer") or "").strip()
    if not customer_id.isdigit():
        return
    customer = m.Customer.objects.filter(organization=org, active=True, pk=int(customer_id)).first()
    if customer is None:
        return
    project = m.Project.objects.filter(organization=org, customer=customer, archived=False, title="Allgemeiner Auftrag").first()
    if project is None:
        project = m.Project.objects.create(
            organization=org,
            customer=customer,
            number=base._unique_number(m.Project, org, "P"),
            title="Allgemeiner Auftrag",
            status="inquiry",
        )
    post = request.POST.copy()
    post["project"] = str(project.pk)
    request.POST = post


def _save_upload_document(org, request, upload, title, kind):
    if not upload:
        return None
    document = m.Document(
        organization=org,
        title=title,
        category="contract" if kind in {"terms", "withdrawal"} else "other",
        mime_type=getattr(upload, "content_type", "") or "application/octet-stream",
        size=getattr(upload, "size", 0) or 0,
        metadata={"kind": kind, "source": "einstellungen"},
        uploaded_by=request.user,
    )
    document.file.save(upload.name, upload, save=False)
    document.save()
    return document


'''
    if helper not in text:
        text = text.replace(helper_anchor, helper + helper_anchor, 1)
    text = text.replace('    existing = get_object_or_404(m.Quote, pk=pk, organization=org) if pk else None\n', '    existing = get_object_or_404(m.Quote, pk=pk, organization=org) if pk else None\n    _ensure_document_project(request, org)\n', 1)
    text = text.replace('    existing = get_object_or_404(m.Invoice, pk=pk, organization=org) if pk else None\n', '    existing = get_object_or_404(m.Invoice, pk=pk, organization=org) if pk else None\n    _ensure_document_project(request, org)\n', 1)

    old_layout = '''        if section == "layout":
            cfg["logo"].update({"show": request.POST.get("logo_show") == "on", "position": request.POST.get("logo_position") or "right", "size": request.POST.get("logo_size") or "large"})
            cfg["sender_line"]["show"] = request.POST.get("sender_line_show") == "on"
            cfg["footer"].update({"show": request.POST.get("footer_show") == "on", "mode": request.POST.get("footer_mode") or "standard"})
'''
    new_layout = '''        if section == "layout":
            cfg["logo"].update({"show": request.POST.get("logo_show") == "on", "position": request.POST.get("logo_position") or "right", "size": request.POST.get("logo_size") or "large"})
            logo = request.FILES.get("logo_file")
            if logo:
                ext = (logo.name.rsplit(".", 1)[-1] if "." in logo.name else "").lower()
                if ext not in {"png", "jpg", "jpeg"} or logo.size > 409600:
                    messages.error(request, "Das Logo muss eine PNG- oder JPG-Datei mit maximal 0,4 MB sein.")
                    return redirect("next-settings")
                org.logo.save(logo.name, logo, save=True)
            letterhead = request.FILES.get("letterhead_file")
            if letterhead:
                doc = _save_upload_document(org, request, letterhead, "Briefkopf", "letterhead")
                cfg.setdefault("letterhead", {})["document_id"] = doc.pk
                cfg["letterhead"]["show"] = True
            cfg["sender_line"]["show"] = request.POST.get("sender_line_show") == "on"
            columns = []
            for index in range(1, 5):
                heading = (request.POST.get(f"footer_heading_{index}") or "").strip()[:80]
                lines = [line.strip()[:160] for line in (request.POST.get(f"footer_lines_{index}") or "").splitlines() if line.strip()][:6]
                align = request.POST.get(f"footer_align_{index}") or "left"
                if heading or lines:
                    columns.append({"heading": heading, "lines": lines, "align": align if align in {"left", "center", "right"} else "left"})
            cfg["footer"].update({"show": request.POST.get("footer_show") == "on", "mode": request.POST.get("footer_mode") or "standard", "columns": columns})
'''
    if old_layout not in text:
        raise RuntimeError("ToolTime-Abschluss: Layout-View-Anker fehlt.")
    text = text.replace(old_layout, new_layout, 1)

    old_num = '''            for key in ("quote_start", "invoice_start", "credit_start", "customer_start"):
                try: num[key] = max(1, int(request.POST.get(key) or num.get(key) or 1))
                except ValueError: pass
'''
    new_num = '''            for key in ("quote_start", "invoice_start", "credit_start", "customer_start"):
                raw = (request.POST.get(key) or str(num.get(key) or 1)).strip()
                try:
                    num[key] = max(1, int(raw))
                    num[key.replace("_start", "_width")] = max(1, min(len(raw), 12))
                except ValueError:
                    pass
'''
    if old_num not in text:
        raise RuntimeError("ToolTime-Abschluss: Nummern-View-Anker fehlt.")
    text = text.replace(old_num, new_num, 1)

    dunning_anchor = '''        elif section == "dunning":
'''
    legal_block = '''        elif section == "legal":
            org.legal_name = (request.POST.get("legal_name") or org.legal_name or org.name)[:220]
            org.email = (request.POST.get("company_email") or "").strip()
            org.phone = (request.POST.get("company_phone") or "").strip()[:60]
            org.address = (request.POST.get("company_address") or "").strip()
            org.tax_id = (request.POST.get("tax_number") or "").strip()[:80]
            org.iban = (request.POST.get("iban") or "").strip()[:60]
            settings = org.settings if isinstance(org.settings, dict) else {}
            legal = settings.get("invoice_legal") if isinstance(settings.get("invoice_legal"), dict) else {}
            for field in ("vat_id", "website", "bic", "bank_name", "register_court", "register_number", "managing_director", "legal_form", "mobile"):
                legal[field] = (request.POST.get(field) or "").strip()
            settings["invoice_legal"] = legal
            org.settings = settings
            org.save(update_fields=["legal_name", "email", "phone", "address", "tax_id", "iban", "settings", "updated_at"])
        elif section == "legal_documents":
            docs = cfg.setdefault("legal_documents", {})
            for field, title, kind in (("terms_file", "Allgemeine Geschäftsbedingungen", "terms"), ("withdrawal_file", "Widerrufsbelehrung und Muster-Widerrufsformular", "withdrawal")):
                upload = request.FILES.get(field)
                if upload:
                    if not upload.name.lower().endswith(".pdf") or upload.size > 1800000:
                        messages.error(request, "Rechtliche Dokumente müssen PDF-Dateien mit maximal 1,8 MB sein.")
                        return redirect("next-settings")
                    document = _save_upload_document(org, request, upload, title, kind)
                    docs["terms_document_id" if kind == "terms" else "withdrawal_document_id"] = document.pk
'''
    text = text.replace(dunning_anchor, legal_block + dunning_anchor, 1)

    old_return = '    templates = m.ToolTimeTextTemplate.objects.filter(organization=org)\n    return render(request, "rebuild/tooltime_settings.html", {"organization": org, "integrations": integrations, "profile": profile, "cfg": cfg, "text_templates": templates})\n'
    new_return = '''    templates = m.ToolTimeTextTemplate.objects.filter(organization=org)
    legal = (org.settings or {}).get("invoice_legal", {}) if isinstance(org.settings, dict) else {}
    terms = m.Document.objects.filter(organization=org, pk=cfg.get("legal_documents", {}).get("terms_document_id")).first()
    withdrawal = m.Document.objects.filter(organization=org, pk=cfg.get("legal_documents", {}).get("withdrawal_document_id")).first()
    return render(request, "rebuild/tooltime_settings.html", {"organization": org, "integrations": integrations, "profile": profile, "cfg": cfg, "text_templates": templates, "legal": legal, "terms_document": terms, "withdrawal_document": withdrawal})
'''
    if old_return not in text:
        raise RuntimeError("ToolTime-Abschluss: Settings-Context-Anker fehlt.")
    text = text.replace(old_return, new_return, 1)

    insertion = r'''

@login_required
@require_POST
def quick_customer_create(request):
    org = _org(request)
    number = _sequence_number_for_customer(org, request.POST.get("customer_number"))
    customer = m.Customer.objects.create(
        organization=org,
        number=number,
        type=request.POST.get("customer_type") if request.POST.get("customer_type") in {"private", "business", "insurance", "property_manager"} else "private",
        company=(request.POST.get("company") or "")[:180],
        salutation=(request.POST.get("salutation") or "")[:30],
        first_name=(request.POST.get("first_name") or "")[:100],
        last_name=(request.POST.get("last_name") or "")[:100],
        email=(request.POST.get("email") or "").strip(),
        phone=(request.POST.get("phone") or "")[:60],
        mobile=(request.POST.get("mobile") or "")[:60],
        street=(request.POST.get("street") or "")[:180],
        postal_code=(request.POST.get("postal_code") or "")[:20],
        city=(request.POST.get("city") or "")[:120],
        country=(request.POST.get("country") or "DE")[:2].upper(),
    )
    return JsonResponse({"ok": True, "customer": {"id": customer.pk, "number": customer.number, "name": customer.display_name, "address": f"{customer.street}, {customer.postal_code} {customer.city}".strip(", ")}})


@login_required
@require_POST
def quick_project_create(request):
    org = _org(request)
    customer_id = (request.POST.get("customer_id") or "").strip()
    customer = m.Customer.objects.filter(organization=org, active=True, pk=customer_id).first() if customer_id.isdigit() else None
    if customer is None:
        return JsonResponse({"ok": False, "error": "Bitte zuerst einen Kunden auswählen."}, status=400)
    title = (request.POST.get("title") or "").strip()
    if not title:
        return JsonResponse({"ok": False, "error": "Bitte einen Projekttitel eingeben."}, status=400)
    project = m.Project.objects.create(organization=org, customer=customer, number=base._unique_number(m.Project, org, "P"), title=title[:220], status="inquiry")
    return JsonResponse({"ok": True, "project": {"id": project.pk, "number": project.number, "title": project.title, "customer_id": customer.pk, "address": f"{customer.street}, {customer.postal_code} {customer.city}".strip(", ")}})
'''
    search_anchor = '\n\n@login_required\n@require_GET\ndef article_search(request):\n'
    if insertion not in text:
        text = text.replace(search_anchor, insertion + search_anchor, 1)

    # A second Mahnung replaces the first fee economically; the current/latest fee is authoritative.
    old_created = '    m.ToolTimeDunningRecord.objects.create(organization=org, invoice=invoice, level=level, due_days=due_days, fee=fee, internal_note=request.POST.get("internal_note") or "", recipient_email=email, document=doc, created_by=request.user)\n    messages.success(request, f"{heading} wurde erstellt und bei der Rechnung gespeichert.")\n'
    new_created = '''    record = m.ToolTimeDunningRecord.objects.create(organization=org, invoice=invoice, level=level, due_days=due_days, fee=fee, internal_note=request.POST.get("internal_note") or "", recipient_email=email, document=doc, created_by=request.user)
    if request.POST.get("delivery") == "email":
        if not email:
            messages.error(request, "Beim Kunden ist keine E-Mail-Adresse hinterlegt. Das Mahnschreiben wurde gespeichert, aber nicht versendet.")
        else:
            try:
                message = EmailMessage(subject=f"{heading} zu Rechnung {invoice.number}", body=f"Sehr geehrte Damen und Herren,\n\nanbei erhalten Sie {heading.lower()} zu Rechnung {invoice.number}.\n\nMit freundlichen Grüßen\n{org.name}", to=[email])
                message.attach(f"{heading}-{invoice.number}.pdf", pdf, "application/pdf")
                message.send(fail_silently=False)
                record.sent_at = timezone.now(); record.save(update_fields=["sent_at"])
                messages.success(request, f"{heading} wurde erstellt und per E-Mail versendet.")
                return redirect("next-invoice-edit", pk=pk)
            except Exception:
                messages.error(request, "Das Mahnschreiben wurde gespeichert, konnte aber nicht per E-Mail versendet werden.")
    messages.success(request, f"{heading} wurde erstellt und bei der Rechnung gespeichert.")
'''
    if old_created not in text:
        raise RuntimeError("ToolTime-Abschluss: Mahnungs-Anker fehlt.")
    text = text.replace(old_created, new_created, 1)
    write(rel, text)


def patch_urls() -> None:
    rel = "erp/rebuild_urls.py"
    text = read(rel)
    anchor = '    path("pricing/artikel-suche/", tooltime_parity.article_search, name="next-article-search"),\n'
    routes = '    path("documents/kunde-schnell-anlegen/", tooltime_parity.quick_customer_create, name="next-quick-customer-create"),\n    path("documents/projekt-schnell-anlegen/", tooltime_parity.quick_project_create, name="next-quick-project-create"),\n'
    if 'name="next-quick-customer-create"' not in text:
        if anchor not in text:
            raise RuntimeError("ToolTime-Abschluss: URL-Anker fehlt.")
        text = text.replace(anchor, anchor + routes, 1)
    write(rel, text)


def patch_document_template() -> None:
    rel = "templates/rebuild/document_editor.html"
    text = read(rel)
    old = '''<section class="tt-card tt-document-top"><h2>Kunde und Projekt</h2><div class="tt-two"><label>Kunde auswählen<select class="nx-control" data-customer-preview><option value="">Kunde auswählen</option>{% for c in tt.customers %}<option value="{{ c.pk }}" data-address="{{ c.street|default:'' }}, {{ c.postal_code|default:'' }} {{ c.city|default:'' }}">{{ c.display_name }}</option>{% endfor %}</select></label><label>Projekt auswählen {{ form.project }}</label></div><div class="tt-address-preview" data-address-preview>{% if document and document.project %}<strong>Adresse</strong><span>{{ document.project.customer.street }} · {{ document.project.customer.postal_code }} {{ document.project.customer.city }}</span>{% else %}<span>Bitte zuerst einen Kunden oder ein Projekt auswählen.</span>{% endif %}</div></section>'''
    new = '''<section class="tt-card tt-document-top" data-quick-customer-url="{% url 'next-quick-customer-create' %}" data-quick-project-url="{% url 'next-quick-project-create' %}"><h2>Kunde und Projekt</h2><div class="tt-two"><label>Kunde auswählen<div class="tt-picker-row"><select class="nx-control" name="selected_customer" data-customer-preview><option value="">Kunde auswählen</option>{% for c in tt.customers %}<option value="{{ c.pk }}" data-address="{{ c.street|default:'' }}, {{ c.postal_code|default:'' }} {{ c.city|default:'' }}" {% if document and document.project.customer_id == c.pk %}selected{% endif %}>{{ c.display_name }}</option>{% endfor %}</select><button class="nx-btn" type="button" data-new-customer>＋</button></div></label><label>Projekt auswählen<div class="tt-picker-row"><select class="nx-control" name="project" data-project-preview><option value="">Projekt auswählen (optional)</option>{% for p in tt.projects %}<option value="{{ p.pk }}" data-customer-id="{{ p.customer_id }}" data-address="{{ p.customer.street|default:'' }}, {{ p.customer.postal_code|default:'' }} {{ p.customer.city|default:'' }}" {% if document and document.project_id == p.pk %}selected{% endif %}>{{ p.number }} · {{ p.title }}</option>{% endfor %}</select><button class="nx-btn" type="button" data-new-project>＋</button></div></label></div><div class="tt-address-preview" data-address-preview>{% if document and document.project %}<strong>Adresse</strong><span>{{ document.project.customer.street }} · {{ document.project.customer.postal_code }} {{ document.project.customer.city }}</span>{% else %}<span>Bitte zuerst einen Kunden oder ein Projekt auswählen.</span>{% endif %}</div></section>'''
    if old not in text:
        raise RuntimeError("ToolTime-Abschluss: Kunde/Projekt-Template-Anker fehlt.")
    text = text.replace(old, new, 1)

    modal_anchor = '<div class="tt-modal" data-article-modal hidden>'
    quick_modals = r'''<div class="tt-modal" data-customer-modal hidden><form class="tt-modal-card" data-quick-customer-form><header><h2>Neuen Kunden anlegen</h2><button type="button" data-close-modal>×</button></header><div class="tt-two"><label>Kundentyp<select class="nx-control" name="customer_type"><option value="private">Privatkunde</option><option value="business">Geschäftskunde</option><option value="insurance">Versicherung</option><option value="property_manager">Hausverwaltung</option></select></label><label>Kundennummer (optional)<input class="nx-control" name="customer_number"></label><label>Firma<input class="nx-control" name="company"></label><label>Anrede<input class="nx-control" name="salutation"></label><label>Vorname<input class="nx-control" name="first_name"></label><label>Nachname<input class="nx-control" name="last_name"></label><label>E-Mail<input class="nx-control" type="email" name="email"></label><label>Telefon<input class="nx-control" name="phone"></label><label>Mobil<input class="nx-control" name="mobile"></label><label>Straße<input class="nx-control" name="street"></label><label>PLZ<input class="nx-control" name="postal_code"></label><label>Ort<input class="nx-control" name="city"></label></div><input type="hidden" name="country" value="DE"><button class="nx-btn nx-btn-accent" type="submit">Kunden anlegen</button><p class="tt-form-error" data-quick-error></p></form></div><div class="tt-modal" data-project-modal hidden><form class="tt-modal-card" data-quick-project-form><header><h2>Neues Projekt anlegen</h2><button type="button" data-close-modal>×</button></header><label>Projekttitel<input class="nx-control" name="title" required></label><button class="nx-btn nx-btn-accent" type="submit">Projekt anlegen</button><p class="tt-form-error" data-quick-error></p></form></div>
'''
    if quick_modals not in text:
        text = text.replace(modal_anchor, quick_modals + modal_anchor, 1)
    text = text.replace('<button class="nx-btn nx-btn-accent" type="submit">Mahnung erstellen</button>', '<div class="tt-two"><button class="nx-btn" type="submit" name="delivery" value="save">Speichern</button><button class="nx-btn nx-btn-accent" type="submit" name="delivery" value="email">Per E-Mail senden</button></div>', 1)
    write(rel, text)


def patch_settings_template() -> None:
    rel = "templates/rebuild/tooltime_settings.html"
    text = read(rel)
    text = text.replace('<form method="post"><input type="hidden" name="section" value="layout">', '<form method="post" enctype="multipart/form-data"><input type="hidden" name="section" value="layout">', 1)
    old_layout_tail = '<label class="tt-check"><input type="checkbox" name="sender_line_show" {% if cfg.sender_line.show %}checked{% endif %}> Absenderzeile anzeigen</label><div class="tt-two"><label>Fußzeile<select class="nx-control" name="footer_mode"><option value="standard" {% if cfg.footer.mode == \'standard\' %}selected{% endif %}>Standard</option><option value="custom" {% if cfg.footer.mode == \'custom\' %}selected{% endif %}>Benutzerdefiniert</option></select></label><label class="tt-check"><input type="checkbox" name="footer_show" {% if cfg.footer.show %}checked{% endif %}> Fußzeile anzeigen</label></div><button class="nx-btn nx-btn-accent" type="submit">Layout speichern</button></form></section>'
    new_layout_tail = '''<div class="tt-two"><label>Logo hochladen<input class="nx-control" type="file" name="logo_file" accept="image/png,image/jpeg"><small>PNG/JPG, maximal 0,4 MB.</small></label><label>Briefkopf hochladen<input class="nx-control" type="file" name="letterhead_file" accept="image/png,image/jpeg"><small>Empfohlen: 2434 × 242 px.</small></label></div><label class="tt-check"><input type="checkbox" name="sender_line_show" {% if cfg.sender_line.show %}checked{% endif %}> Absenderzeile anzeigen</label><div class="tt-two"><label>Fußzeile<select class="nx-control" name="footer_mode"><option value="standard" {% if cfg.footer.mode == 'standard' %}selected{% endif %}>Standard</option><option value="custom" {% if cfg.footer.mode == 'custom' %}selected{% endif %}>Benutzerdefiniert</option></select></label><label class="tt-check"><input type="checkbox" name="footer_show" {% if cfg.footer.show %}checked{% endif %}> Fußzeile anzeigen</label></div><div class="tt-footer-editor"><h3>Benutzerdefinierte Fußzeile</h3>{% for column in cfg.footer.columns %}<div class="tt-footer-column"><input class="nx-control" name="footer_heading_{{ forloop.counter }}" value="{{ column.heading }}" placeholder="Überschrift"><textarea class="nx-control" name="footer_lines_{{ forloop.counter }}" rows="6" placeholder="Bis zu 6 Zeilen">{% for line in column.lines %}{{ line }}{% if not forloop.last %}\n{% endif %}{% endfor %}</textarea><select class="nx-control" name="footer_align_{{ forloop.counter }}"><option value="left" {% if column.align == 'left' %}selected{% endif %}>Linksbündig</option><option value="center" {% if column.align == 'center' %}selected{% endif %}>Zentriert</option><option value="right" {% if column.align == 'right' %}selected{% endif %}>Rechtsbündig</option></select></div>{% endfor %}{% for _ in "1234" %}{% if forloop.counter > cfg.footer.columns|length %}<div class="tt-footer-column"><input class="nx-control" name="footer_heading_{{ forloop.counter }}" placeholder="Überschrift"><textarea class="nx-control" name="footer_lines_{{ forloop.counter }}" rows="6" placeholder="Bis zu 6 Zeilen"></textarea><select class="nx-control" name="footer_align_{{ forloop.counter }}"><option value="left">Linksbündig</option><option value="center">Zentriert</option><option value="right">Rechtsbündig</option></select></div>{% endif %}{% endfor %}</div><button class="nx-btn nx-btn-accent" type="submit">Layout speichern</button></form></section>'''
    if old_layout_tail not in text:
        raise RuntimeError("ToolTime-Abschluss: Layout-Template-Anker fehlt.")
    text = text.replace(old_layout_tail, new_layout_tail, 1)

    legal_section = r'''<section class="tt-card"><h2>Angaben auf Ihren Dokumenten</h2><p>Diese Angaben erscheinen auf Rechnungen, Angeboten und in der E-Mail-Signatur und sind rechtlich relevant.</p><form method="post"><input type="hidden" name="section" value="legal">{% csrf_token %}<div class="tt-three"><div><h3>Geschäftsanschrift</h3><label>Firmenname<input class="nx-control" name="legal_name" value="{{ organization.legal_name|default:organization.name }}"></label><label>Anschrift<textarea class="nx-control" name="company_address" rows="3">{{ organization.address }}</textarea></label><label>Steuernummer<input class="nx-control" name="tax_number" value="{{ organization.tax_id }}"></label><label>USt-IdNr.<input class="nx-control" name="vat_id" value="{{ legal.vat_id|default:'' }}"></label></div><div><h3>Bankverbindung</h3><label>IBAN<input class="nx-control" name="iban" value="{{ organization.iban }}"></label><label>BIC<input class="nx-control" name="bic" value="{{ legal.bic|default:'' }}"></label><label>Bank<input class="nx-control" name="bank_name" value="{{ legal.bank_name|default:'' }}"></label></div><div><h3>Kontakt & Register</h3><label>Webseite<input class="nx-control" name="website" value="{{ legal.website|default:'' }}"></label><label>E-Mail<input class="nx-control" type="email" name="company_email" value="{{ organization.email }}"></label><label>Telefon<input class="nx-control" name="company_phone" value="{{ organization.phone }}"></label><label>Mobil<input class="nx-control" name="mobile" value="{{ legal.mobile|default:'' }}"></label><label>Rechtsform<input class="nx-control" name="legal_form" value="{{ legal.legal_form|default:'' }}"></label><label>Geschäftsführung / Inhaber<input class="nx-control" name="managing_director" value="{{ legal.managing_director|default:'' }}"></label><label>Registergericht<input class="nx-control" name="register_court" value="{{ legal.register_court|default:'' }}"></label><label>Handelsregisternummer<input class="nx-control" name="register_number" value="{{ legal.register_number|default:'' }}"></label></div></div><button class="nx-btn nx-btn-accent" type="submit">Unternehmensangaben speichern</button></form></section><section class="tt-card"><h2>Rechtliche Informationen</h2><form method="post" enctype="multipart/form-data"><input type="hidden" name="section" value="legal_documents">{% csrf_token %}<div class="tt-two"><label>Allgemeine Geschäftsbedingungen<input class="nx-control" type="file" name="terms_file" accept="application/pdf">{% if terms_document %}<a href="{{ terms_document.file.url }}" target="_blank">Aktuelle AGB öffnen</a>{% endif %}</label><label>Widerrufsbelehrung und Muster-Widerrufsformular<input class="nx-control" type="file" name="withdrawal_file" accept="application/pdf">{% if withdrawal_document %}<a href="{{ withdrawal_document.file.url }}" target="_blank">Aktuelles Dokument öffnen</a>{% endif %}</label></div><small>PDF-Dateien, maximal 1,8 MB.</small><button class="nx-btn nx-btn-accent" type="submit">Rechtliche Dokumente speichern</button></form></section>'''
    number_anchor = '<section class="tt-card"><h2>Nummernkreise für Dokumente</h2>'
    if legal_section not in text:
        text = text.replace(number_anchor, legal_section + number_anchor, 1)
    write(rel, text)


def patch_js_css() -> None:
    rel = "static/js/tooltime-parity-finance.js"
    text = read(rel)
    anchor = "  document.querySelector('[data-customer-preview]')?.addEventListener('change',e=>{const opt=e.target.selectedOptions[0];const p=document.querySelector('[data-address-preview]');if(p)p.textContent=opt?.dataset.address||'Bitte ein Projekt auswählen.'});\n"
    replacement = r'''  const customerSelect=document.querySelector('[data-customer-preview]'),projectSelect=document.querySelector('[data-project-preview]'),top=document.querySelector('.tt-document-top');
  const setAddress=(value)=>{const p=document.querySelector('[data-address-preview]');if(p)p.innerHTML=value?`<strong>Adresse</strong><span>${value}</span>`:'<span>Bitte zuerst einen Kunden oder ein Projekt auswählen.</span>'};
  customerSelect?.addEventListener('change',e=>{const opt=e.target.selectedOptions[0];setAddress(opt?.dataset.address||'');if(projectSelect){[...projectSelect.options].forEach(o=>{if(!o.value)return;o.hidden=!!e.target.value&&o.dataset.customerId!==e.target.value});if(projectSelect.selectedOptions[0]?.hidden)projectSelect.value=''}});
  projectSelect?.addEventListener('change',e=>{const opt=e.target.selectedOptions[0];if(opt?.dataset.customerId&&customerSelect){customerSelect.value=opt.dataset.customerId}setAddress(opt?.dataset.address||customerSelect?.selectedOptions[0]?.dataset.address||'')});
  document.querySelector('[data-new-customer]')?.addEventListener('click',()=>modal('[data-customer-modal]',true));document.querySelector('[data-new-project]')?.addEventListener('click',()=>{if(!customerSelect?.value){alert('Bitte zuerst einen Kunden auswählen.');return}modal('[data-project-modal]',true)});
  const csrf=()=>form.querySelector('[name=csrfmiddlewaretoken]')?.value||'';
  document.querySelector('[data-quick-customer-form]')?.addEventListener('submit',async e=>{e.preventDefault();const error=e.target.querySelector('[data-quick-error]');if(error)error.textContent='';try{const r=await fetch(top.dataset.quickCustomerUrl,{method:'POST',headers:{'X-CSRFToken':csrf(),'X-Requested-With':'XMLHttpRequest'},body:new FormData(e.target)}),d=await r.json();if(!r.ok||!d.ok)throw new Error(d.error||'Kunde konnte nicht angelegt werden.');const o=new Option(`${d.customer.number} · ${d.customer.name}`,d.customer.id,true,true);o.dataset.address=d.customer.address||'';customerSelect.appendChild(o);customerSelect.dispatchEvent(new Event('change',{bubbles:true}));modal('[data-customer-modal]',false);e.target.reset()}catch(err){if(error)error.textContent=err.message}});
  document.querySelector('[data-quick-project-form]')?.addEventListener('submit',async e=>{e.preventDefault();const fd=new FormData(e.target);fd.set('customer_id',customerSelect.value);const error=e.target.querySelector('[data-quick-error]');if(error)error.textContent='';try{const r=await fetch(top.dataset.quickProjectUrl,{method:'POST',headers:{'X-CSRFToken':csrf(),'X-Requested-With':'XMLHttpRequest'},body:fd}),d=await r.json();if(!r.ok||!d.ok)throw new Error(d.error||'Projekt konnte nicht angelegt werden.');const o=new Option(`${d.project.number} · ${d.project.title}`,d.project.id,true,true);o.dataset.customerId=String(d.project.customer_id);o.dataset.address=d.project.address||'';projectSelect.appendChild(o);projectSelect.dispatchEvent(new Event('change',{bubbles:true}));modal('[data-project-modal]',false);e.target.reset()}catch(err){if(error)error.textContent=err.message}});
'''
    if anchor not in text:
        raise RuntimeError("ToolTime-Abschluss: JS-Kunde-Anker fehlt.")
    write(rel, text.replace(anchor, replacement, 1))

    rel = "static/css/tooltime-parity-finance.css"
    css = read(rel)
    css += r'''
/* A+BAU TOOLTIME FINANCE COMPLETION 2026-08-20 */
.tt-picker-row{display:grid;grid-template-columns:minmax(0,1fr) 42px;gap:7px}.tt-form-error{color:#b42318;font-weight:700;min-height:18px}.tt-footer-editor{margin:14px 0;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.tt-footer-column{display:grid;gap:7px;border:1px solid #e4e9ef;border-radius:10px;padding:10px}.tt-card small{font-weight:400;color:#6e7a88}.tt-settings form{display:grid;gap:12px}@media(max-width:1000px){.tt-footer-editor{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:650px){.tt-footer-editor{grid-template-columns:1fr}}
'''
    write(rel, css)


def patch_tests() -> None:
    rel = "tests/test_tooltime_finance_parity_batch.py"
    text = read(rel)
    marker = "    def test_invoice_type_mixing_guard_exists(self):\n"
    extras = '''    def test_completion_layer_is_installed(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text()
        settings = (ROOT / "templates/rebuild/tooltime_settings.html").read_text()
        editor = (ROOT / "templates/rebuild/document_editor.html").read_text()
        self.assertIn("quick_customer_create", views)
        self.assertIn("quick_project_create", views)
        self.assertIn("Angaben auf Ihren Dokumenten", settings)
        self.assertIn("Rechtliche Informationen", settings)
        self.assertIn("Briefkopf hochladen", settings)
        self.assertIn("Neuen Kunden anlegen", editor)
        self.assertIn("Neues Projekt anlegen", editor)

    def test_invoice_number_has_no_forced_year_segment(self):
        service = (ROOT / "erp/services/invoice_compliance_service.py").read_text()
        self.assertIn("year=0", service)
        self.assertIn('return f"{prefix}{value:0{seq.digits}d}"', service)

'''
    if extras not in text:
        if marker not in text:
            raise RuntimeError("ToolTime-Abschluss: Test-Anker fehlt.")
        text = text.replace(marker, extras + marker, 1)
    write(rel, text)


def run() -> None:
    patch_service()
    patch_invoice_numbering()
    patch_tags()
    patch_views()
    patch_urls()
    patch_document_template()
    patch_settings_template()
    patch_js_css()
    patch_tests()
    print("ToolTime-Finanzparität vervollständigt: Kunde/Projekt im Entwurf, Layout-Uploads, Rechtsangaben, Footer, Nummernkreise und Mahnversand.")


if __name__ == "__main__":
    run()
