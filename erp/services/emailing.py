from __future__ import annotations

import email
import imaplib
import smtplib
import ssl
from email.header import decode_header, make_header
from email.message import EmailMessage as MIMEMessage
from email.utils import parsedate_to_datetime
from django.conf import settings
from django.utils import timezone
from erp.models import EmailMessage, IntegrationConfig
from erp.services.integrations import require_integration_enabled


def send_approved_email(message: EmailMessage) -> None:
    if message.status != EmailMessage.Status.APPROVED or not message.approved_by_id:
        raise PermissionError("E-Mail wurde nicht menschlich freigegeben.")
    require_integration_enabled(message.organization, IntegrationConfig.Provider.GMX)
    recipients = [r for r in message.recipients if r]
    if not recipients:
        raise ValueError("Kein Empfänger angegeben.")
    mime = MIMEMessage()
    mime["From"] = settings.GMX_EMAIL
    mime["To"] = ", ".join(recipients)
    if message.cc:
        mime["Cc"] = ", ".join(message.cc)
    mime["Subject"] = message.subject
    mime.set_content(message.body_text or "")
    if message.body_html:
        mime.add_alternative(message.body_html, subtype="html")
    attachment_kind = (message.classification or {}).get("attachment_kind")
    attachment_id = (message.classification or {}).get("attachment_id")
    if attachment_kind and attachment_id:
        from erp.models import ChangeOrder, Invoice, Quote, SiteReport
        from erp.services.pdf import build_change_order_pdf, build_invoice_pdf, build_quote_pdf, build_site_report_pdf
        builders = {
            "quote": (Quote, build_quote_pdf, "Angebot.pdf"),
            "invoice": (Invoice, build_invoice_pdf, "Rechnung.pdf"),
            "change_order": (ChangeOrder, build_change_order_pdf, "Zusatzarbeit.pdf"),
            "site_report": (SiteReport, build_site_report_pdf, "Vor-Ort-Bericht.pdf"),
        }
        if attachment_kind in builders:
            model, builder, filename = builders[attachment_kind]
            document = model.objects.get(pk=attachment_id, organization=message.organization)
            mime.add_attachment(builder(document), maintype="application", subtype="pdf", filename=filename)
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(settings.GMX_SMTP_HOST, settings.GMX_SMTP_PORT, context=context, timeout=30) as server:
        server.login(settings.GMX_EMAIL, settings.GMX_PASSWORD)
        server.send_message(mime)
    message.status = EmailMessage.Status.SENT
    message.direction = EmailMessage.Direction.OUTBOUND
    message.sent_at = timezone.now()
    message.save(update_fields=["status", "direction", "sent_at", "updated_at"])


def _decode(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def sync_gmx(organization, limit: int = 100) -> int:
    require_integration_enabled(organization, IntegrationConfig.Provider.GMX)
    count = 0
    with imaplib.IMAP4_SSL(settings.GMX_IMAP_HOST) as mailbox:
        mailbox.login(settings.GMX_EMAIL, settings.GMX_PASSWORD)
        mailbox.select("INBOX", readonly=True)
        status, data = mailbox.search(None, "ALL")
        if status != "OK":
            return 0
        ids = data[0].split()[-limit:]
        for uid in ids:
            status, payload = mailbox.fetch(uid, "(BODY.PEEK[])")
            if status != "OK" or not payload or not isinstance(payload[0], tuple):
                continue
            msg = email.message_from_bytes(payload[0][1])
            message_id = msg.get("Message-ID", "").strip() or f"gmx-{uid.decode()}"
            if EmailMessage.objects.filter(organization=organization, message_id=message_id).exists():
                continue
            text_body = ""
            html_body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    disposition = str(part.get("Content-Disposition", ""))
                    if "attachment" in disposition:
                        continue
                    content_type = part.get_content_type()
                    raw = part.get_payload(decode=True) or b""
                    charset = part.get_content_charset() or "utf-8"
                    decoded = raw.decode(charset, errors="replace")
                    if content_type == "text/plain" and not text_body:
                        text_body = decoded
                    elif content_type == "text/html" and not html_body:
                        html_body = decoded
            else:
                raw = msg.get_payload(decode=True) or b""
                text_body = raw.decode(msg.get_content_charset() or "utf-8", errors="replace")
            try:
                received = parsedate_to_datetime(msg.get("Date")) if msg.get("Date") else timezone.now()
            except Exception:
                received = timezone.now()
            EmailMessage.objects.create(
                organization=organization,
                message_id=message_id,
                direction=EmailMessage.Direction.INBOUND,
                sender=email.utils.parseaddr(msg.get("From", ""))[1],
                recipients=[email.utils.parseaddr(v)[1] for v in msg.get_all("To", [])],
                subject=_decode(msg.get("Subject")),
                body_text=text_body[:500_000],
                body_html=html_body[:500_000],
                received_at=received,
            )
            count += 1
    return count
