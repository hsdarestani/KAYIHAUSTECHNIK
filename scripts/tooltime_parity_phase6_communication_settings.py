from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME PHASE 6 COMMUNICATION SETTINGS 2026-08-20"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Phase 6 target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_service_defaults() -> None:
    rel = "erp/services/tooltime_parity_finance.py"
    text = read(rel)
    old = '''        "communication": {
            "reply_email": "", "show_logo": True,
            "invoice_subject": "Ihre Rechnung von {{ company_name }} ({{ invoice_number }})",
            "invoice_body": "Sehr geehrte Damen und Herren,\\n\\nwie besprochen schicken wir Ihnen die Rechnung mit der Nummer {{ invoice_number }}. Sie finden das Dokument im Anhang.\\n\\nMit freundlichen Grüßen\\n{{ company_name }}",
            "quote_subject": "Ihr Angebot von {{ company_name }} ({{ quote_number }})",
            "quote_body": "Sehr geehrte Damen und Herren,\\n\\nanbei erhalten Sie unser Angebot {{ quote_number }}.\\n\\nMit freundlichen Grüßen\\n{{ company_name }}",
            "sms": "Hallo. Wir bestätigen Ihren Termin am {{ date }}, {{ time }}. {{ address }}",
        },
'''
    new = '''        "communication": {
            "reply_email": "", "sender_name": "", "show_logo": True,
            "invoice_subject": "Ihre Rechnung von {{ company_name }} ({{ invoice_number }})",
            "invoice_body": "Sehr geehrte Damen und Herren,\\n\\nwie besprochen schicken wir Ihnen die Rechnung mit der Nummer {{ invoice_number }}. Sie finden das Dokument im Anhang.\\n\\nMit freundlichen Grüßen\\n{{ company_name }}",
            "quote_subject": "Ihr Angebot von {{ company_name }} ({{ quote_number }})",
            "quote_body": "Sehr geehrte Damen und Herren,\\n\\nanbei erhalten Sie unser Angebot {{ quote_number }}.\\n\\nMit freundlichen Grüßen\\n{{ company_name }}",
            "sms": "Hallo. Wir bestätigen Ihren Termin am {{ date }}, {{ time }}. {{ address }}",
            "sms_provider": "disabled", "sms_endpoint": "", "sms_sender_id": "",
        },
'''
    if '"sms_provider": "disabled"' not in text:
        if old not in text:
            raise RuntimeError("Phase 6 default communication settings anchor missing")
        text = text.replace(old, new, 1)
    write(rel, text)


def patch_views() -> None:
    rel = "erp/tooltime_parity_views.py"
    text = read(rel)

    if "import json\n" not in text:
        text = text.replace("import hashlib\n", "import hashlib\nimport json\nimport os\nimport urllib.error\nimport urllib.request\n", 1)
    if "from email.utils import formataddr\n" not in text:
        anchor = "from decimal import Decimal\n"
        if anchor not in text:
            raise RuntimeError("Phase 6 email utils import anchor missing")
        text = text.replace(anchor, anchor + "from email.utils import formataddr\n", 1)

    helper_anchor = "def _phase5_email_backend_ready():\n"
    helpers = r'''def _phase6_render_communication_template(raw, document, kind):
    customer = _phase5_customer(document, kind)
    project = getattr(document, "project", None)
    issue_date = getattr(document, "issue_date", None)
    values = {
        "company_name": getattr(document.organization, "name", "") or "",
        "document_number": getattr(document, "number", "") or "",
        "quote_number": getattr(document, "number", "") if kind == "quote" else "",
        "invoice_number": getattr(document, "number", "") if kind == "invoice" else "",
        "customer_name": getattr(customer, "display_name", "") if customer else "",
        "project_name": getattr(project, "name", "") if project else "",
        "date": issue_date.strftime("%d.%m.%Y") if issue_date else "",
    }
    rendered = str(raw or "")
    for key, value in values.items():
        rendered = rendered.replace("{{ " + key + " }}", str(value or ""))
        rendered = rendered.replace("{{" + key + "}}", str(value or ""))
        rendered = rendered.replace("{" + key + "}", str(value or ""))
    return rendered


def _phase6_document_message(document, kind):
    cfg = profile_for(document.organization).settings.get("communication", {})
    label = "Angebot" if kind == "quote" else "Rechnung"
    subject_key = "quote_subject" if kind == "quote" else "invoice_subject"
    body_key = "quote_body" if kind == "quote" else "invoice_body"
    fallback_subject = f"{label} {document.number} · {document.organization.name}"
    fallback_body = f"Sehr geehrte Damen und Herren,\n\nanbei erhalten Sie {'unser Angebot' if kind == 'quote' else 'unsere Rechnung'} {document.number} als PDF.\n\nMit freundlichen Grüßen\n{document.organization.name}"
    subject = _phase6_render_communication_template(cfg.get(subject_key) or fallback_subject, document, kind).strip()[:300]
    body = _phase6_render_communication_template(cfg.get(body_key) or fallback_body, document, kind).strip()
    return subject, body, cfg


def _phase6_sms_provider_ready(org):
    cfg = profile_for(org).settings.get("communication", {})
    provider = str(cfg.get("sms_provider") or "disabled").strip().lower()
    if provider == "disabled":
        return False, "SMS-Versand ist deaktiviert."
    if provider != "webhook":
        return False, "Der konfigurierte SMS-Provider wird nicht unterstützt."
    endpoint = str(cfg.get("sms_endpoint") or "").strip()
    if not endpoint.startswith("https://"):
        return False, "Für den SMS-Webhook ist eine HTTPS-Adresse erforderlich."
    if not os.environ.get("KAYI_SMS_PROVIDER_TOKEN"):
        return False, "KAYI_SMS_PROVIDER_TOKEN fehlt in der Server-Umgebung."
    return True, "SMS-Provider ist serverseitig einsatzbereit."


def _phase6_send_sms(org, phone, body):
    ready, reason = _phase6_sms_provider_ready(org)
    if not ready:
        return False, reason
    phone = str(phone or "").strip()
    body = str(body or "").strip()
    if not phone:
        return False, "Eine Mobilnummer ist erforderlich."
    if not body:
        return False, "Die SMS-Nachricht ist leer."
    if len(body) > 160:
        return False, "Die SMS-Nachricht darf maximal 160 Zeichen enthalten."
    cfg = profile_for(org).settings.get("communication", {})
    payload = json.dumps({"to": phone, "message": body, "sender": str(cfg.get("sms_sender_id") or "")[:32]}).encode("utf-8")
    request = urllib.request.Request(
        str(cfg.get("sms_endpoint") or ""),
        data=payload,
        method="POST",
        headers={
            "Authorization": "Bearer " + os.environ["KAYI_SMS_PROVIDER_TOKEN"],
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            status = int(getattr(response, "status", 0) or 0)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
        return False, f"SMS-Versand fehlgeschlagen: {exc}"
    if status < 200 or status >= 300:
        return False, f"SMS-Provider antwortete mit HTTP {status}."
    return True, "SMS wurde vom Provider angenommen."


'''
    if "def _phase6_send_sms(" not in text:
        if helper_anchor not in text:
            raise RuntimeError("Phase 6 communication helper anchor missing")
        text = text.replace(helper_anchor, helpers + helper_anchor, 1)

    old_message = '''    recipient = (request.POST.get("recipient_email") or default_recipient or "").strip()
    subject = (request.POST.get("subject") or f"{'Angebot' if kind == 'quote' else 'Rechnung'} {document.number} · {document.organization.name}").strip()[:300]
    body = (request.POST.get("message") or f"Sehr geehrte Damen und Herren,\\n\\nanbei erhalten Sie {'unser Angebot' if kind == 'quote' else 'unsere Rechnung'} {document.number} als PDF.\\n\\nMit freundlichen Grüßen\\n{document.organization.name}").strip()
'''
    new_message = '''    recipient = (request.POST.get("recipient_email") or default_recipient or "").strip()
    default_subject, default_body, communication_cfg = _phase6_document_message(document, kind)
    subject = (request.POST.get("subject") or default_subject).strip()[:300]
    body = (request.POST.get("message") or default_body).strip()
'''
    if "communication_cfg = _phase6_document_message" not in text:
        if old_message not in text:
            raise RuntimeError("Phase 6 Phase-5 message default anchor missing")
        text = text.replace(old_message, new_message, 1)

    old_email = '''        message = EmailMessage(subject=subject, body=body, to=[recipient])
        if getattr(document.organization, "email", ""):
            message.reply_to = [document.organization.email]
'''
    new_email = '''        from_address = str(getattr(settings, "DEFAULT_FROM_EMAIL", "") or getattr(settings, "EMAIL_HOST_USER", "") or "").strip() or None
        sender_name = str(communication_cfg.get("sender_name") or document.organization.name or "").strip()
        if from_address and sender_name:
            from_address = formataddr((sender_name, from_address))
        message = EmailMessage(subject=subject, body=body, from_email=from_address, to=[recipient])
        reply_email = str(communication_cfg.get("reply_email") or getattr(document.organization, "email", "") or "").strip()
        if reply_email:
            message.reply_to = [reply_email]
'''
    if "sender_name = str(communication_cfg.get" not in text:
        if old_email not in text:
            raise RuntimeError("Phase 6 EmailMessage construction anchor missing")
        text = text.replace(old_email, new_email, 1)

    old_handler = '''        elif section == "communication":
            c = cfg["communication"]
            for key in ("reply_email", "invoice_subject", "invoice_body", "quote_subject", "quote_body", "sms"):
                c[key] = request.POST.get(key) or ""
            c["show_logo"] = request.POST.get("email_show_logo") == "on"
            c["sms"] = c["sms"][:160]
'''
    new_handler = '''        elif section == "communication":
            c = cfg["communication"]
            reply_email = (request.POST.get("reply_email") or "").strip()
            if reply_email:
                try:
                    validate_email(reply_email)
                except ValidationError:
                    messages.error(request, "Bitte eine gültige Antwort-E-Mail-Adresse eingeben.")
                    return redirect("next-settings")
            sms_text = (request.POST.get("sms") or "").strip()
            if len(sms_text) > 160:
                messages.error(request, "Die SMS-Vorlage darf maximal 160 Zeichen enthalten.")
                return redirect("next-settings")
            sms_provider = (request.POST.get("sms_provider") or "disabled").strip().lower()
            if sms_provider not in {"disabled", "webhook"}:
                messages.error(request, "Der ausgewählte SMS-Provider ist ungültig.")
                return redirect("next-settings")
            sms_endpoint = (request.POST.get("sms_endpoint") or "").strip()
            if sms_provider == "webhook" and not sms_endpoint.startswith("https://"):
                messages.error(request, "Für den SMS-Webhook ist eine HTTPS-Adresse erforderlich.")
                return redirect("next-settings")
            c.update({
                "reply_email": reply_email[:254],
                "sender_name": (request.POST.get("sender_name") or "").strip()[:120],
                "invoice_subject": (request.POST.get("invoice_subject") or "").strip()[:300],
                "invoice_body": request.POST.get("invoice_body") or "",
                "quote_subject": (request.POST.get("quote_subject") or "").strip()[:300],
                "quote_body": request.POST.get("quote_body") or "",
                "sms": sms_text,
                "sms_provider": sms_provider,
                "sms_endpoint": sms_endpoint[:500],
                "sms_sender_id": (request.POST.get("sms_sender_id") or "").strip()[:32],
                "show_logo": request.POST.get("email_show_logo") == "on",
            })
'''
    if "sms_provider not in {\"disabled\", \"webhook\"}" not in text:
        if old_handler not in text:
            raise RuntimeError("Phase 6 settings communication handler anchor missing")
        text = text.replace(old_handler, new_handler, 1)

    context_anchor = '    templates = m.ToolTimeTextTemplate.objects.filter(organization=org)\n'
    context_extra = context_anchor + '    sms_provider_ready, sms_provider_reason = _phase6_sms_provider_ready(org)\n'
    if "sms_provider_ready, sms_provider_reason" not in text:
        if context_anchor not in text:
            raise RuntimeError("Phase 6 settings context anchor missing")
        text = text.replace(context_anchor, context_extra, 1)
    if '"sms_provider_ready": sms_provider_ready' not in text:
        anchor = '"text_templates": templates'
        if anchor not in text:
            raise RuntimeError("Phase 6 settings render dictionary anchor missing")
        text = text.replace(anchor, anchor + ', "sms_provider_ready": sms_provider_ready, "sms_provider_reason": sms_provider_reason', 1)

    write(rel, text)


def patch_template_context() -> None:
    rel = "erp/templatetags/tooltime_parity.py"
    text = read(rel)
    old = '''        label = "Angebot" if kind == "quote" else "Rechnung"
        email_subject = f"{label} {document.number or ''} · {org.name}".strip()
        email_body = f"Sehr geehrte Damen und Herren,\\n\\nanbei erhalten Sie {'unser Angebot' if kind == 'quote' else 'unsere Rechnung'} {document.number or ''} als PDF.\\n\\nMit freundlichen Grüßen\\n{org.name}"
'''
    new = '''        communication = (commercial.settings or {}).get("communication", {})
        subject_key = "quote_subject" if kind == "quote" else "invoice_subject"
        body_key = "quote_body" if kind == "quote" else "invoice_body"
        label = "Angebot" if kind == "quote" else "Rechnung"
        raw_subject = communication.get(subject_key) or f"{label} {document.number or ''} · {org.name}"
        raw_body = communication.get(body_key) or f"Sehr geehrte Damen und Herren,\\n\\nanbei erhalten Sie {'unser Angebot' if kind == 'quote' else 'unsere Rechnung'} {document.number or ''} als PDF.\\n\\nMit freundlichen Grüßen\\n{org.name}"
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
'''
    if "def render_communication(raw):" not in text:
        if old not in text:
            raise RuntimeError("Phase 6 document communication context anchor missing")
        text = text.replace(old, new, 1)
    write(rel, text)


def patch_settings_template() -> None:
    rel = "templates/rebuild/tooltime_settings.html"
    text = read(rel)
    marker = "data-phase6-communication"
    if marker not in text:
        anchor = "{% endblock %}"
        pos = text.rfind(anchor)
        if pos < 0:
            raise RuntimeError("Phase 6 settings template endblock anchor missing")
        block = r'''
<section class="tt-card" data-phase6-communication>
  <div class="tt-section-title"><div><span class="tt-eyebrow">Kommunikation</span><h2>E-Mail & SMS</h2><p>Absender, Antwortadresse und Vorlagen gelten zentral für zukünftige Dokumentversände.</p></div><span class="nx-badge">{% if sms_provider_ready %}SMS bereit{% else %}SMS nicht bereit{% endif %}</span></div>
  <form method="post" data-phase6-communication-form>{% csrf_token %}<input type="hidden" name="section" value="communication">
    <div class="tt-two"><label>Absendername<input class="nx-control" name="sender_name" maxlength="120" value="{{ cfg.communication.sender_name|default:'' }}" placeholder="{{ organization.name }}"></label><label>Antwortadresse (Reply-To)<input class="nx-control" type="email" name="reply_email" value="{{ cfg.communication.reply_email|default:'' }}" placeholder="info@firma.de"></label></div>
    <label class="tt-check"><input type="checkbox" name="email_show_logo" {% if cfg.communication.show_logo %}checked{% endif %}> Firmenlogo in E-Mails verwenden</label>
    <div class="tt-variable-bar"><strong>Verfügbare Variablen</strong><code>{{ '{{ company_name }}' }}</code><code>{{ '{{ customer_name }}' }}</code><code>{{ '{{ document_number }}' }}</code><code>{{ '{{ quote_number }}' }}</code><code>{{ '{{ invoice_number }}' }}</code><code>{{ '{{ project_name }}' }}</code></div>
    <div class="tt-two tt-template-grid">
      <div><h3>Angebot</h3><label>Betreff<input class="nx-control" name="quote_subject" maxlength="300" value="{{ cfg.communication.quote_subject|default:'' }}" data-phase6-template-input="quote-subject"></label><label>Nachricht<textarea class="nx-control" name="quote_body" rows="8" data-phase6-template-input="quote-body">{{ cfg.communication.quote_body|default:'' }}</textarea></label></div>
      <div><h3>Rechnung</h3><label>Betreff<input class="nx-control" name="invoice_subject" maxlength="300" value="{{ cfg.communication.invoice_subject|default:'' }}" data-phase6-template-input="invoice-subject"></label><label>Nachricht<textarea class="nx-control" name="invoice_body" rows="8" data-phase6-template-input="invoice-body">{{ cfg.communication.invoice_body|default:'' }}</textarea></label></div>
    </div>
    <div class="tt-two tt-preview-grid"><div class="tt-number-preview"><strong>Angebot · Live-Vorschau</strong><div data-phase6-preview="quote-subject"></div><pre data-phase6-preview="quote-body"></pre></div><div class="tt-number-preview"><strong>Rechnung · Live-Vorschau</strong><div data-phase6-preview="invoice-subject"></div><pre data-phase6-preview="invoice-body"></pre></div></div>
    <hr><h3>SMS-Terminbestätigung</h3><div class="tt-three"><label>Provider<select class="nx-control" name="sms_provider"><option value="disabled" {% if cfg.communication.sms_provider != 'webhook' %}selected{% endif %}>Deaktiviert</option><option value="webhook" {% if cfg.communication.sms_provider == 'webhook' %}selected{% endif %}>HTTPS Webhook</option></select></label><label>Webhook-Endpoint<input class="nx-control" type="url" name="sms_endpoint" value="{{ cfg.communication.sms_endpoint|default:'' }}" placeholder="https://sms-provider.example/send"></label><label>Sender-ID<input class="nx-control" name="sms_sender_id" maxlength="32" value="{{ cfg.communication.sms_sender_id|default:'' }}" placeholder="A+Bau"></label></div>
    <label>SMS-Vorlage<textarea class="nx-control" name="sms" rows="3" maxlength="160" data-phase6-sms>{{ cfg.communication.sms|default:'' }}</textarea><small><span data-phase6-sms-count>0</span>/160 Zeichen · Variablen: <code>{{ '{{ date }}' }}</code> <code>{{ '{{ time }}' }}</code> <code>{{ '{{ address }}' }}</code> <code>{{ '{{ company_name }}' }}</code></small></label>
    <p class="tt-modal-note">{{ sms_provider_reason }} Der geheime Provider-Token wird ausschließlich serverseitig über <code>KAYI_SMS_PROVIDER_TOKEN</code> geladen und niemals hier gespeichert.</p>
    <button class="nx-btn nx-btn-accent" type="submit">Kommunikation speichern</button>
  </form>
</section>
<script>
(() => {
  const root = document.querySelector('[data-phase6-communication]'); if (!root) return;
  const values = {company_name: {{ organization.name|default:'Firma'|escapejs|json_script:'phase6-company-name' }}, customer_name:'Max Mustermann', document_number:'A-2026-001', quote_number:'A-2026-001', invoice_number:'R-2026-001', project_name:'Musterprojekt', date:'20.08.2026', time:'10:00', address:'Musterstraße 1'};
  const companyNode = document.getElementById('phase6-company-name'); if (companyNode) { try { values.company_name = JSON.parse(companyNode.textContent); } catch (_) {} }
  const render = raw => { let out = raw || ''; Object.entries(values).forEach(([key,value]) => { out = out.split('{{ '+key+' }}').join(value).split('{{'+key+'}}').join(value).split('{'+key+'}').join(value); }); return out; };
  const refresh = () => { root.querySelectorAll('[data-phase6-template-input]').forEach(input => { const out = root.querySelector('[data-phase6-preview="'+input.dataset.phase6TemplateInput+'"]'); if (out) out.textContent = render(input.value); }); const sms=root.querySelector('[data-phase6-sms]'), count=root.querySelector('[data-phase6-sms-count]'); if (sms&&count) count.textContent=String(sms.value.length); };
  root.addEventListener('input', refresh); refresh();
})();
</script>
'''
        # json_script must emit its own script element, not be embedded in an object literal.
        block = block.replace("const values = {company_name: {{ organization.name|default:'Firma'|escapejs|json_script:'phase6-company-name' }},", "{{ organization.name|default:'Firma'|json_script:'phase6-company-name' }}\n  const values = {company_name:'Firma',")
        text = text[:pos] + block + text[pos:]
    write(rel, text)

    rel = "static/css/tooltime-parity-finance.css"
    css = read(rel)
    if "/* A+BAU PHASE 6 COMMUNICATION SETTINGS */" not in css:
        css += r'''

/* A+BAU PHASE 6 COMMUNICATION SETTINGS */
.tt-variable-bar{display:flex;gap:7px;align-items:center;flex-wrap:wrap;margin:12px 0 18px}.tt-variable-bar code,.tt-modal-note code{padding:3px 7px;border-radius:7px;background:rgba(20,28,38,.06);font-size:12px}.tt-template-grid h3{margin-top:0}.tt-preview-grid{margin:10px 0 18px}.tt-preview-grid .tt-number-preview{display:block;min-height:120px}.tt-preview-grid pre{white-space:pre-wrap;font:inherit;margin:8px 0 0;color:inherit}@media(max-width:760px){.tt-template-grid,.tt-preview-grid{grid-template-columns:1fr}}
'''
        write(rel, css)


def install_tests() -> None:
    write("tests/test_tooltime_phase6_communication_settings_contract.py", r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase6CommunicationSettingsContractTests(SimpleTestCase):
    def test_email_sender_reply_to_and_templates_feed_real_delivery(self):
        service = (ROOT / "erp/services/tooltime_parity_finance.py").read_text(encoding="utf-8")
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        tags = (ROOT / "erp/templatetags/tooltime_parity.py").read_text(encoding="utf-8")
        self.assertIn('"sender_name": ""', service)
        self.assertIn('communication_cfg = _phase6_document_message', views)
        self.assertIn('formataddr((sender_name, from_address))', views)
        self.assertIn('communication_cfg.get("reply_email")', views)
        self.assertIn('communication = (commercial.settings or {}).get("communication", {})', tags)

    def test_sms_provider_never_reports_fake_success_without_real_provider(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        self.assertIn('KAYI_SMS_PROVIDER_TOKEN', views)
        self.assertIn('urllib.request.urlopen(request, timeout=12)', views)
        self.assertIn('if status < 200 or status >= 300:', views)
        self.assertIn('return True, "SMS wurde vom Provider angenommen."', views)
        self.assertIn('return False, "SMS-Versand ist deaktiviert."', views)

    def test_settings_ui_has_live_email_preview_and_160_char_sms_guard(self):
        template = (ROOT / "templates/rebuild/tooltime_settings.html").read_text(encoding="utf-8")
        for token in ('data-phase6-communication', 'name="sender_name"', 'name="reply_email"', 'name="quote_subject"', 'name="invoice_subject"', 'name="sms_provider"', 'name="sms_endpoint"', 'data-phase6-preview'):
            self.assertIn(token, template)
        self.assertIn('maxlength="160"', template)
        self.assertIn('KAYI_SMS_PROVIDER_TOKEN', template)
''')


def run() -> None:
    patch_service_defaults()
    patch_views()
    patch_template_context()
    patch_settings_template()
    install_tests()
    for rel in ("erp/services/tooltime_parity_finance.py", "erp/tooltime_parity_views.py", "erp/templatetags/tooltime_parity.py"):
        path = ROOT / rel
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    print("ToolTime Phase 6 installiert: E-Mail-Absender/Reply-To/Vorlagen, Live-Vorschau und echter SMS-Webhook ohne Fake-Erfolg.")


if __name__ == "__main__":
    run()
