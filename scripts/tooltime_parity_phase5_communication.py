from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME PHASE 5 COMMUNICATION 2026-08-20"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Phase 5 target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_models_and_migration() -> None:
    rel = "erp/tooltime_parity_finance.py"
    text = read(rel)
    if "class ToolTimeDocumentDelivery" not in text:
        text += r'''


class ToolTimeDocumentDelivery(models.Model):
    CHANNELS = [("email", "E-Mail")]
    STATUSES = [("sent", "Gesendet"), ("failed", "Fehlgeschlagen")]
    organization = models.ForeignKey("erp.Organization", on_delete=models.CASCADE, related_name="tooltime_document_deliveries")
    quote = models.ForeignKey("erp.Quote", null=True, blank=True, on_delete=models.PROTECT, related_name="tooltime_deliveries")
    invoice = models.ForeignKey("erp.Invoice", null=True, blank=True, on_delete=models.PROTECT, related_name="tooltime_deliveries")
    document = models.ForeignKey("erp.Document", null=True, blank=True, on_delete=models.PROTECT, related_name="tooltime_document_deliveries")
    channel = models.CharField(max_length=20, choices=CHANNELS, default="email")
    status = models.CharField(max_length=20, choices=STATUSES)
    recipient_email = models.EmailField()
    subject = models.CharField(max_length=300)
    body_excerpt = models.TextField(blank=True)
    error_message = models.CharField(max_length=500, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="tooltime_document_deliveries")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
'''
        write(rel, text)

    rel = "erp/models.py"
    text = read(rel)
    if "ToolTimeDocumentDelivery" not in text:
        pattern = re.compile(r"from \.tooltime_parity_finance import ([^\n]+)")
        match = pattern.search(text)
        if not match:
            raise RuntimeError("Phase 5 ToolTime model import missing")
        names = match.group(1).rstrip()
        text = text[:match.start()] + f"from .tooltime_parity_finance import {names}, ToolTimeDocumentDelivery" + text[match.end():]
        write(rel, text)

    write("erp/migrations/0017_tooltime_phase5_communication.py", r'''from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("erp", "0016_tooltime_phase3_editor"),
    ]
    operations = [
        migrations.CreateModel(
            name="ToolTimeDocumentDelivery",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("channel", models.CharField(choices=[("email", "E-Mail")], default="email", max_length=20)),
                ("status", models.CharField(choices=[("sent", "Gesendet"), ("failed", "Fehlgeschlagen")], max_length=20)),
                ("recipient_email", models.EmailField(max_length=254)),
                ("subject", models.CharField(max_length=300)),
                ("body_excerpt", models.TextField(blank=True)),
                ("error_message", models.CharField(blank=True, max_length=500)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="tooltime_document_deliveries", to=settings.AUTH_USER_MODEL)),
                ("document", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="tooltime_document_deliveries", to="erp.document")),
                ("invoice", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="tooltime_deliveries", to="erp.invoice")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tooltime_document_deliveries", to="erp.organization")),
                ("quote", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="tooltime_deliveries", to="erp.quote")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
    ]
''')


def patch_views_and_urls() -> None:
    rel = "erp/tooltime_parity_views.py"
    text = read(rel)
    if "import hashlib\n" not in text:
        text = text.replace("from __future__ import annotations\n", "from __future__ import annotations\n\nimport hashlib\nimport html\nimport io\n", 1)
    if "from django.conf import settings\n" not in text:
        text = text.replace("from django.contrib import messages\n", "from django.conf import settings\nfrom django.contrib import messages\n", 1)
    if "from django.core.exceptions import ValidationError\n" not in text:
        text = text.replace("from django.core.files.base import ContentFile\n", "from django.core.exceptions import ValidationError\nfrom django.core.files.base import ContentFile\n", 1)
    if "from django.core.mail import EmailMessage\n" not in text:
        text = text.replace("from django.core.files.base import ContentFile\n", "from django.core.files.base import ContentFile\nfrom django.core.mail import EmailMessage\n", 1)
    if "from django.core.validators import validate_email\n" not in text:
        text = text.replace("from django.core.mail import EmailMessage\n", "from django.core.mail import EmailMessage\nfrom django.core.validators import validate_email\n", 1)
    text = text.replace("from django.http import JsonResponse\n", "from django.http import FileResponse, Http404, JsonResponse\n", 1)
    compliance_import = "from .services.invoice_compliance_service import audit as invoice_compliance_audit, get_compliance\n"
    if compliance_import not in text:
        anchor = "from .services.field_authorization import html_to_pdf_bytes\n"
        if anchor not in text:
            raise RuntimeError("Phase 5 compliance import anchor missing")
        text = text.replace(anchor, anchor + compliance_import, 1)

    anchor = "@login_required\n@require_http_methods([\"GET\", \"POST\"])\ndef quote_editor(request, pk=None):\n"
    helpers = r'''def _phase5_customer(document, kind):
    meta = meta_for(document, kind, create=False)
    customer = getattr(meta, "customer", None) if meta else None
    if customer is not None:
        return customer
    project = getattr(document, "project", None)
    return getattr(project, "customer", None) if project else None


def _phase5_email_backend_ready():
    backend = str(getattr(settings, "EMAIL_BACKEND", "") or "").lower()
    non_delivery = ("console", "locmem", "dummy", "filebased")
    if any(part in backend for part in non_delivery):
        return False, "Es ist kein produktiver E-Mail-Versand konfiguriert. Bitte SMTP in den Einstellungen hinterlegen."
    return True, ""


def _phase5_quote_pdf_bytes(quote):
    meta = meta_for(quote, "quote", create=False)
    if not meta or not meta.finalized_at:
        raise ValueError("PDF und Versand sind erst nach dem Fertigstellen des Angebots verfügbar.")
    customer = _phase5_customer(quote, "quote")
    totals = base._quote_total(quote)
    net = money(totals.get("net", 0)); gross = money(totals.get("gross", net)); tax = money(totals.get("tax", gross - net))
    rows = []
    for item in quote.items.all().order_by("position", "pk"):
        quantity = getattr(item, "quantity", 0) or 0
        unit_price = money(getattr(item, "unit_price", 0))
        line_total = money(quantity * unit_price)
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(getattr(item, 'position', '') or ''))}</td>"
            f"<td>{html.escape(str(getattr(item, 'description', '') or ''))}</td>"
            f"<td style='text-align:right'>{html.escape(str(quantity))} {html.escape(str(getattr(item, 'unit', '') or ''))}</td>"
            f"<td style='text-align:right'>{unit_price:.2f} €</td>"
            f"<td style='text-align:right'>{line_total:.2f} €</td>"
            "</tr>"
        )
    customer_name = getattr(customer, "display_name", "") if customer else ""
    address = " · ".join(filter(None, [getattr(customer, "street", "") if customer else "", " ".join(filter(None, [getattr(customer, "postal_code", "") if customer else "", getattr(customer, "city", "") if customer else ""]))]))
    intro = html.escape(str(getattr(quote, "intro_text", "") or "")).replace("\n", "<br>")
    outro = html.escape(str(getattr(quote, "outro_text", "") or "")).replace("\n", "<br>")
    body = f'''<html><body style="font-family:Arial,sans-serif;font-size:11px;color:#202428">
<h1 style="margin-bottom:4px">{html.escape(meta.document_title or 'Angebot')} {html.escape(quote.number or meta.final_number or '')}</h1>
<p style="margin-top:0">Angebotsdatum: {quote.issue_date:%d.%m.%Y}</p>
<div style="margin:20px 0"><strong>{html.escape(str(customer_name))}</strong><br>{html.escape(address)}</div>
<p>{intro}</p>
<table style="width:100%;border-collapse:collapse" cellpadding="6"><thead><tr style="border-bottom:1px solid #bbb"><th>Pos.</th><th style="text-align:left">Leistung</th><th style="text-align:right">Menge</th><th style="text-align:right">Einzelpreis</th><th style="text-align:right">Gesamt</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<div style="margin:18px 0 18px auto;width:260px"><p>Nettobetrag <strong style="float:right">{net:.2f} €</strong></p><p>Umsatzsteuer <strong style="float:right">{tax:.2f} €</strong></p><p style="font-size:13px;border-top:1px solid #bbb;padding-top:7px">Gesamtbetrag <strong style="float:right">{gross:.2f} €</strong></p></div>
<p>{outro}</p>
</body></html>'''
    return html_to_pdf_bytes(inject_business_pdf_identity(body, org=quote.organization, document_kind="Angebot"))


def _phase5_store_quote_delivery_pdf(quote, payload, user):
    customer = _phase5_customer(quote, "quote")
    filename = f"angebot-{quote.number or quote.pk}.pdf"
    doc = m.Document(
        organization=quote.organization,
        project=quote.project,
        customer=customer,
        uploaded_by=user if getattr(user, "is_authenticated", False) else None,
        title=filename,
        category="quote",
        mime_type="application/pdf",
        size=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        metadata={"source": "tooltime_email_delivery", "quote_id": quote.pk, "final_number": quote.number or ""},
    )
    doc.file.save(filename, ContentFile(payload), save=False)
    doc.save()
    return doc


def _phase5_legal_attachments(document, kind, skip_document_id=None):
    meta = meta_for(document, kind, create=False)
    ids = list(getattr(meta, "default_attachment_ids", []) or []) if meta else []
    if not ids:
        return []
    result = []
    for attachment in m.Document.objects.filter(organization=document.organization, pk__in=ids):
        if skip_document_id and attachment.pk == skip_document_id:
            continue
        if not getattr(attachment, "file", None):
            continue
        try:
            with attachment.file.open("rb") as handle:
                payload = handle.read()
        except (OSError, ValueError):
            continue
        result.append((attachment.title or f"anlage-{attachment.pk}", payload, attachment.mime_type or "application/octet-stream"))
    return result


def _phase5_delivery_failure(*, document, kind, recipient, subject, body, error, user, pdf_document=None):
    return m.ToolTimeDocumentDelivery.objects.create(
        organization=document.organization,
        quote=document if kind == "quote" else None,
        invoice=document if kind == "invoice" else None,
        document=pdf_document,
        channel="email",
        status="failed",
        recipient_email=recipient,
        subject=subject[:300],
        body_excerpt=body[:1000],
        error_message=str(error)[:500],
        created_by=user,
    )


def _phase5_send_email(request, document, kind):
    meta = meta_for(document, kind, create=False)
    if kind == "quote":
        if not meta or not meta.finalized_at:
            messages.error(request, "Angebote können erst nach dem Fertigstellen versendet werden.")
            return False
        pdf = _phase5_quote_pdf_bytes(document)
        pdf_document = _phase5_store_quote_delivery_pdf(document, pdf, request.user)
        filename = pdf_document.title
        extra_attachments = _phase5_legal_attachments(document, kind, skip_document_id=pdf_document.pk)
        xml_attachment = None
    else:
        compliance = get_compliance(document)
        if not compliance or compliance.state == "draft" or not compliance.original_pdf_document_id:
            messages.error(request, "Rechnungen können nur mit dem finalisierten Original-PDF versendet werden.")
            return False
        pdf_document = compliance.original_pdf_document
        try:
            with pdf_document.file.open("rb") as handle:
                pdf = handle.read()
        except (OSError, ValueError):
            messages.error(request, "Das finalisierte Original-PDF ist nicht lesbar. Der Versand wurde abgebrochen.")
            return False
        filename = pdf_document.title or f"rechnung-{compliance.final_number}.pdf"
        extra_attachments = _phase5_legal_attachments(document, kind, skip_document_id=pdf_document.pk)
        xml_attachment = None
        if compliance.original_xml_document_id and compliance.e_invoice_status == "valid":
            xml_doc = compliance.original_xml_document
            try:
                with xml_doc.file.open("rb") as handle:
                    xml_attachment = (xml_doc.title or f"xrechnung-{compliance.final_number}.xml", handle.read(), xml_doc.mime_type or "application/xml")
            except (OSError, ValueError):
                xml_attachment = None

    customer = _phase5_customer(document, kind)
    default_recipient = getattr(customer, "email", "") if customer else ""
    if kind == "invoice" and customer:
        try:
            default_recipient = customer.invoice_profile.invoice_email or default_recipient
        except (AttributeError, m.CustomerInvoiceProfile.DoesNotExist):
            pass
    recipient = (request.POST.get("recipient_email") or default_recipient or "").strip()
    subject = (request.POST.get("subject") or f"{'Angebot' if kind == 'quote' else 'Rechnung'} {document.number} · {document.organization.name}").strip()[:300]
    body = (request.POST.get("message") or f"Sehr geehrte Damen und Herren,\n\nanbei erhalten Sie {'unser Angebot' if kind == 'quote' else 'unsere Rechnung'} {document.number} als PDF.\n\nMit freundlichen Grüßen\n{document.organization.name}").strip()
    try:
        validate_email(recipient)
    except ValidationError:
        _phase5_delivery_failure(document=document, kind=kind, recipient=recipient or "invalid@example.invalid", subject=subject, body=body, error="Ungültige Empfängeradresse", user=request.user, pdf_document=pdf_document)
        messages.error(request, "Bitte eine gültige Empfänger-E-Mail-Adresse eingeben.")
        return False

    ready, reason = _phase5_email_backend_ready()
    if not ready:
        _phase5_delivery_failure(document=document, kind=kind, recipient=recipient, subject=subject, body=body, error=reason, user=request.user, pdf_document=pdf_document)
        messages.error(request, reason)
        return False

    delivery = m.ToolTimeDocumentDelivery.objects.create(
        organization=document.organization,
        quote=document if kind == "quote" else None,
        invoice=document if kind == "invoice" else None,
        document=pdf_document,
        channel="email",
        status="failed",
        recipient_email=recipient,
        subject=subject,
        body_excerpt=body[:1000],
        created_by=request.user,
    )
    try:
        message = EmailMessage(subject=subject, body=body, to=[recipient])
        if getattr(document.organization, "email", ""):
            message.reply_to = [document.organization.email]
        message.attach(filename, pdf, "application/pdf")
        for attachment_name, attachment_payload, attachment_mime in extra_attachments:
            message.attach(attachment_name, attachment_payload, attachment_mime)
        if xml_attachment:
            message.attach(*xml_attachment)
        message.send(fail_silently=False)
    except Exception as exc:
        delivery.error_message = str(exc)[:500]
        delivery.save(update_fields=["error_message"])
        messages.error(request, "Der E-Mail-Versand ist fehlgeschlagen. Es wurde kein Versandserfolg gespeichert.")
        return False

    delivery.status = "sent"
    delivery.sent_at = timezone.now()
    delivery.error_message = ""
    delivery.save(update_fields=["status", "sent_at", "error_message"])
    if kind == "invoice":
        invoice_compliance_audit(
            document,
            "invoice.emailed",
            user=request.user,
            request=request,
            new={"recipient": recipient, "delivery_id": delivery.pk},
            metadata={"original_pdf_document_id": pdf_document.pk},
        )
    messages.success(request, f"{'Angebot' if kind == 'quote' else 'Rechnung'} wurde per E-Mail an {recipient} gesendet.")
    return True


@login_required
@require_GET
def quote_pdf(request, pk):
    org = _org(request)
    quote = get_object_or_404(m.Quote, organization=org, pk=pk)
    try:
        payload = _phase5_quote_pdf_bytes(quote)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("next-quote-edit", pk=quote.pk)
    return FileResponse(io.BytesIO(payload), as_attachment=True, content_type="application/pdf", filename=f"angebot-{quote.number or quote.pk}.pdf")


@login_required
@require_POST
def quote_send_email(request, pk):
    org = _org(request)
    quote = get_object_or_404(m.Quote.objects.select_related("project__customer"), organization=org, pk=pk)
    _phase5_send_email(request, quote, "quote")
    return redirect("next-quote-edit", pk=quote.pk)


@login_required
@require_POST
def invoice_send_email(request, pk):
    org = _org(request)
    invoice = get_object_or_404(m.Invoice.objects.select_related("project__customer"), organization=org, pk=pk)
    _phase5_send_email(request, invoice, "invoice")
    return redirect("next-invoice-edit", pk=invoice.pk)


'''
    if "def _phase5_send_email" not in text:
        if anchor not in text:
            raise RuntimeError("Phase 5 quote editor anchor missing")
        text = text.replace(anchor, helpers + anchor, 1)
    write(rel, text)

    rel = "erp/rebuild_urls.py"
    urls = read(rel)
    routes = '''    path("quotes/<int:pk>/pdf/", tooltime_parity.quote_pdf, name="next-quote-pdf"),
    path("quotes/<int:pk>/send-email/", tooltime_parity.quote_send_email, name="next-quote-send-email"),
    path("invoices/<int:pk>/send-email/", tooltime_parity.invoice_send_email, name="next-invoice-send-email"),
'''
    if 'name="next-quote-send-email"' not in urls:
        anchor = "urlpatterns = [\n"
        if anchor not in urls:
            raise RuntimeError("Phase 5 URL list anchor missing")
        urls = urls.replace(anchor, anchor + routes, 1)
        write(rel, urls)


def patch_template_context_and_ui() -> None:
    rel = "erp/templatetags/tooltime_parity.py"
    text = read(rel)
    old_return = '    return {"cfg": commercial.settings, "meta": meta, "templates": templates, "customers": customers, "projects": projects, "dunning": dunning}\n'
    new_block = r'''    deliveries = []
    recipient_email = ""
    email_subject = ""
    email_body = ""
    if document is not None:
        deliveries_qs = m.ToolTimeDocumentDelivery.objects.filter(organization=org)
        deliveries_qs = deliveries_qs.filter(quote=document) if kind == "quote" else deliveries_qs.filter(invoice=document)
        deliveries = list(deliveries_qs.select_related("document")[:8])
        customer = getattr(meta, "customer", None) if meta else None
        if customer is None and getattr(document, "project_id", None):
            customer = getattr(document.project, "customer", None)
        recipient_email = getattr(customer, "email", "") if customer else ""
        if kind == "invoice" and customer:
            try:
                recipient_email = customer.invoice_profile.invoice_email or recipient_email
            except (AttributeError, m.CustomerInvoiceProfile.DoesNotExist):
                pass
        label = "Angebot" if kind == "quote" else "Rechnung"
        email_subject = f"{label} {document.number or ''} · {org.name}".strip()
        email_body = f"Sehr geehrte Damen und Herren,\n\nanbei erhalten Sie {'unser Angebot' if kind == 'quote' else 'unsere Rechnung'} {document.number or ''} als PDF.\n\nMit freundlichen Grüßen\n{org.name}"
    return {"cfg": commercial.settings, "meta": meta, "templates": templates, "customers": customers, "projects": projects, "dunning": dunning, "deliveries": deliveries, "recipient_email": recipient_email, "email_subject": email_subject, "email_body": email_body}
'''
    if "\"deliveries\": deliveries" not in text:
        if old_return not in text:
            raise RuntimeError("Phase 5 template context return anchor missing")
        text = text.replace(old_return, new_block, 1)
        write(rel, text)

    write("templates/rebuild/_tooltime_communication.html", r'''<section class="tt-card tt-communication-panel" data-document-communication>
  <div class="tt-section-title"><div><span class="tt-eyebrow">Kommunikation</span><h2>PDF & Versand</h2><p>Versendet wird immer die fertiggestellte Dokumentversion. Rechnungen verwenden ausschließlich das revisionssichere Original-PDF.</p></div><div class="tt-head-actions">
    {% if kind == 'quote' %}<a class="nx-btn" href="{% url 'next-quote-pdf' document.pk %}">PDF herunterladen</a>{% else %}<a class="nx-btn" href="{% url 'invoice-compliance-pdf' document.pk %}">Original-PDF herunterladen</a>{% endif %}
    <button class="nx-btn nx-btn-accent" type="button" data-document-email-open>Per E-Mail senden</button>
  </div></div>
  {% if tt.deliveries %}<div class="tt-delivery-history"><strong>Versandverlauf</strong>{% for delivery in tt.deliveries %}<div class="tt-delivery-row"><span class="tt-state {% if delivery.status == 'sent' %}tt-state-paid{% else %}tt-state-overdue{% endif %}">{{ delivery.get_status_display }}</span><span>{{ delivery.recipient_email }}</span><span>{{ delivery.created_at|date:'d.m.Y H:i' }}</span>{% if delivery.status == 'failed' and delivery.error_message %}<small>{{ delivery.error_message }}</small>{% endif %}</div>{% endfor %}</div>{% endif %}
</section>
<div class="tt-modal" data-document-email-modal hidden><form class="tt-modal-card" method="post" action="{% if kind == 'quote' %}{% url 'next-quote-send-email' document.pk %}{% else %}{% url 'next-invoice-send-email' document.pk %}{% endif %}">{% csrf_token %}<header><div><span class="tt-eyebrow">Dokumentversand</span><h2>Per E-Mail senden</h2><p>Das PDF wird als echter Anhang versendet. Standardanhänge aus den Dokumenteinstellungen werden mitgesendet.</p></div><button type="button" data-document-email-close aria-label="Schließen">×</button></header><label>Empfänger<input class="nx-control" type="email" name="recipient_email" value="{{ tt.recipient_email }}" required></label><label>Betreff<input class="nx-control" name="subject" maxlength="300" value="{{ tt.email_subject }}" required></label><label>Nachricht<textarea class="nx-control" name="message" rows="8" required>{{ tt.email_body }}</textarea></label><p class="tt-modal-note">Ein Versand wird nur dann als „Gesendet“ protokolliert, wenn das konfigurierte E-Mail-Backend den Versand ohne Fehler bestätigt.</p><button class="nx-btn nx-btn-accent" type="submit">E-Mail jetzt senden</button></form></div>
''')

    rel = "templates/rebuild/document_editor.html"
    editor = read(rel)
    if "tooltime-parity-communication.js" not in editor:
        script_anchor = "</script>"
        # The editor already contains external script tags rather than an inline script in the final build.
        first_form = '<form class="tt-document-form"'
        idx = editor.find(first_form)
        if idx < 0:
            raise RuntimeError("Phase 5 document form anchor missing")
        communication = r'''{% if document %}{% if kind == 'quote' and tt.meta and tt.meta.finalized_at %}{% include 'rebuild/_tooltime_communication.html' %}{% elif kind == 'invoice' and invoice_compliance and invoice_compliance.state != 'draft' %}{% include 'rebuild/_tooltime_communication.html' %}{% endif %}{% endif %}
'''
        editor = editor[:idx] + communication + editor[idx:]
        # Load after the existing finance JS include; defer keeps document rendering fast.
        finance_script = "<script src=\"{% static 'js/tooltime-parity-finance.js' %}?v=20260820-1\" defer></script>"
        if finance_script in editor:
            editor = editor.replace(finance_script, finance_script + "\n<script src=\"{% static 'js/tooltime-parity-communication.js' %}?v=20260820-5\" defer></script>", 1)
        else:
            # Later phases can bump the finance query version. Insert next to the first static finance JS occurrence.
            match = re.search(r"<script src=\"\{% static 'js/tooltime-parity-finance\.js' %\}[^\"]*\" defer></script>", editor)
            if not match:
                raise RuntimeError("Phase 5 finance JS include anchor missing")
            editor = editor[:match.end()] + "\n<script src=\"{% static 'js/tooltime-parity-communication.js' %}?v=20260820-5\" defer></script>" + editor[match.end():]
        write(rel, editor)

    write("static/js/tooltime-parity-communication.js", r'''(() => {
  const modal = document.querySelector('[data-document-email-modal]');
  const open = document.querySelector('[data-document-email-open]');
  if (!modal || !open) return;
  const close = modal.querySelector('[data-document-email-close]');
  const hide = () => { modal.hidden = true; document.body.classList.remove('tt-modal-open'); };
  open.addEventListener('click', () => { modal.hidden = false; document.body.classList.add('tt-modal-open'); const input = modal.querySelector('input[name="recipient_email"]'); if (input) input.focus(); });
  if (close) close.addEventListener('click', hide);
  modal.addEventListener('click', (event) => { if (event.target === modal) hide(); });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && !modal.hidden) hide(); });
})();
''')

    rel = "static/css/tooltime-parity-finance.css"
    css = read(rel)
    marker = "/* A+BAU PHASE 5 COMMUNICATION */"
    if marker not in css:
        css += r'''

/* A+BAU PHASE 5 COMMUNICATION */
.tt-communication-panel{margin-bottom:18px}.tt-delivery-history{display:grid;gap:8px;margin-top:14px;padding-top:14px;border-top:1px solid rgba(20,28,38,.1)}.tt-delivery-row{display:grid;grid-template-columns:auto minmax(180px,1fr) auto;gap:10px;align-items:center;font-size:13px}.tt-delivery-row small{grid-column:2/-1;color:#9b3b2f}.tt-modal-open{overflow:hidden}@media(max-width:760px){.tt-delivery-row{grid-template-columns:1fr}.tt-delivery-row small{grid-column:auto}.tt-communication-panel .tt-section-title{align-items:flex-start}.tt-communication-panel .tt-head-actions{width:100%;flex-wrap:wrap}}
'''
        write(rel, css)


def install_tests() -> None:
    write("tests/test_tooltime_phase5_communication_contract.py", r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase5CommunicationContractTests(SimpleTestCase):
    def test_delivery_model_and_migration_are_persistent(self):
        models = (ROOT / "erp/tooltime_parity_finance.py").read_text(encoding="utf-8")
        migration = (ROOT / "erp/migrations/0017_tooltime_phase5_communication.py").read_text(encoding="utf-8")
        self.assertIn("class ToolTimeDocumentDelivery", models)
        self.assertIn('("erp", "0016_tooltime_phase3_editor")', migration)
        self.assertIn('status = models.CharField', models)
        self.assertIn('error_message = models.CharField', models)

    def test_real_email_routes_and_pdf_download_are_post_finalization_only(self):
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        for name in ("next-quote-pdf", "next-quote-send-email", "next-invoice-send-email"):
            self.assertIn(f'name="{name}"', urls)
        self.assertIn("Angebote können erst nach dem Fertigstellen versendet werden.", views)
        self.assertIn("PDF und Versand sind erst nach dem Fertigstellen des Angebots verfügbar.", views)

    def test_invoice_email_uses_canonical_frozen_pdf(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        self.assertIn("compliance.original_pdf_document", views)
        self.assertIn("original_pdf_document_id", views)
        self.assertIn('"invoice.emailed"', views)
        self.assertNotIn("_phase5_quote_pdf_bytes(document)\n        pdf_document = compliance", views)

    def test_fake_mail_backends_cannot_record_success(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        for backend in ("console", "locmem", "dummy", "filebased"):
            self.assertIn(f'"{backend}"', views)
        self.assertIn("message.send(fail_silently=False)", views)
        self.assertIn('delivery.status = "sent"', views)
        self.assertIn("Es wurde kein Versandserfolg gespeichert", views)

    def test_german_communication_ui_is_real(self):
        partial = (ROOT / "templates/rebuild/_tooltime_communication.html").read_text(encoding="utf-8")
        editor = (ROOT / "templates/rebuild/document_editor.html").read_text(encoding="utf-8")
        js = (ROOT / "static/js/tooltime-parity-communication.js").read_text(encoding="utf-8")
        for phrase in ("PDF & Versand", "Per E-Mail senden", "Empfänger", "Betreff", "E-Mail jetzt senden", "Versandverlauf"):
            self.assertIn(phrase, partial)
        self.assertIn("_tooltime_communication.html", editor)
        self.assertIn("data-document-email-open", partial)
        self.assertIn("data-document-email-modal", js)
''')


def validate() -> None:
    for rel in (
        "erp/tooltime_parity_finance.py",
        "erp/tooltime_parity_views.py",
        "erp/templatetags/tooltime_parity.py",
        "tests/test_tooltime_phase5_communication_contract.py",
    ):
        path = ROOT / rel
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    required = {
        "erp/tooltime_parity_views.py": ("def quote_send_email", "def invoice_send_email", "compliance.original_pdf_document", "message.send(fail_silently=False)"),
        "templates/rebuild/_tooltime_communication.html": ("Per E-Mail senden", "Original-PDF herunterladen", "E-Mail jetzt senden"),
        "erp/rebuild_urls.py": ('name="next-quote-send-email"', 'name="next-invoice-send-email"'),
    }
    for rel, markers in required.items():
        source = read(rel)
        for marker in markers:
            if marker not in source:
                raise RuntimeError(f"Phase 5 validation marker missing in {rel}: {marker}")


def main() -> None:
    patch_models_and_migration()
    patch_views_and_urls()
    patch_template_context_and_ui()
    install_tests()
    validate()
    print("ToolTime Phase 5 installiert: finalisierte PDFs, echter E-Mail-Versand, Versandhistorie und canonical Invoice-PDF sind verbunden.")


if __name__ == "__main__":
    main()
