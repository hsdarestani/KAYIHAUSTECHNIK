from django import template
from erp import models as m
from erp.services.tooltime_parity_finance import default_settings, meta_for, profile_for

register = template.Library()


@register.simple_tag
def tooltime_context(request, document, kind):
    profile = getattr(getattr(request.user, "profile", None), "organization", None)
    org = profile or getattr(document, "organization", None) or m.Organization.objects.first()
    if org is None:
        return {"cfg": default_settings(), "meta": None, "templates": [], "customers": [], "phase7_appointment": phase7_appointment, "phase7_order_confirmation": phase7_order_confirmation, "phase7_invoice": phase7_invoice}
    commercial = profile_for(org)
    meta = meta_for(document, kind) if document is not None else None
    templates = list(m.ToolTimeTextTemplate.objects.filter(organization=org, document_kind=kind))
    customers = list(m.Customer.objects.filter(organization=org, active=True).order_by("company", "last_name", "first_name")[:300])
    projects = list(m.Project.objects.filter(organization=org, archived=False).select_related("customer").order_by("-updated_at")[:300])
    projects = list(m.Project.objects.filter(organization=org, archived=False).select_related("customer").order_by("-updated_at")[:400])
    dunning = list(document.tooltime_dunning_records.select_related("document").all()) if kind == "invoice" and document is not None else []
    phase7_appointment = None
    phase7_order_confirmation = None
    phase7_invoice = None
    if kind == "quote" and document is not None and getattr(document, "project_id", None):
        phase7_appointment = m.CalendarEvent.objects.filter(organization=org, project_id=document.project_id).order_by("-starts_at", "-pk").first()
        phase7_invoice = m.Invoice.objects.filter(organization=org, quote=document).order_by("pk").first()
        for candidate in m.Document.objects.filter(organization=org, project_id=document.project_id, category="contract").order_by("-pk")[:50]:
            metadata = candidate.metadata or {}
            if metadata.get("kind") == "order_confirmation" and str(metadata.get("quote_id")) == str(document.pk):
                phase7_order_confirmation = candidate
                break
    deliveries = []
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
        communication = (commercial.settings or {}).get("communication", {})
        subject_key = "quote_subject" if kind == "quote" else "invoice_subject"
        body_key = "quote_body" if kind == "quote" else "invoice_body"
        label = "Angebot" if kind == "quote" else "Rechnung"
        raw_subject = communication.get(subject_key) or f"{label} {document.number or ''} · {org.name}"
        raw_body = communication.get(body_key) or f"Sehr geehrte Damen und Herren,\n\nanbei erhalten Sie {'unser Angebot' if kind == 'quote' else 'unsere Rechnung'} {document.number or ''} als PDF.\n\nMit freundlichen Grüßen\n{org.name}"
        values = {
            "company_name": org.name or "",
            "document_number": document.number or "",
            "quote_number": document.number or "" if kind == "quote" else "",
            "invoice_number": document.number or "" if kind == "invoice" else "",
            "customer_name": getattr(customer, "display_name", "") if customer else "",
            "project_name": getattr(getattr(document, "project", None), "name", "") or "",
        }
        def render_communication(raw):
            rendered = str(raw or "")
            for key, value in values.items():
                rendered = rendered.replace("{{ " + key + " }}", str(value or "")).replace("{{" + key + "}}", str(value or "")).replace("{" + key + "}", str(value or ""))
            return rendered
        email_subject = render_communication(raw_subject).strip()[:300]
        email_body = render_communication(raw_body).strip()
    return {"cfg": commercial.settings, "meta": meta, "templates": templates, "customers": customers, "projects": projects, "dunning": dunning, "deliveries": deliveries, "recipient_email": recipient_email, "email_subject": email_subject, "email_body": email_body}
