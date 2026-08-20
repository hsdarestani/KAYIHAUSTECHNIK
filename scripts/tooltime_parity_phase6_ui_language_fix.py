from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch_template() -> None:
    path = ROOT / "templates" / "rebuild" / "tooltime_settings.html"
    text = path.read_text(encoding="utf-8")

    # Phase 6 originally appended the communication section before the *last*
    # Django endblock. The settings template also has a later JavaScript block,
    # so that placed real form markup inside script content. Move the complete
    # Phase-6 section back into the main content block before doing copy fixes.
    section_start = text.find('<section class="tt-card" data-phase6-communication>')
    if section_start < 0:
        raise RuntimeError("Phase 6 communication section missing from settings template")
    content_start = text.find("{% block content %}")
    if content_start < 0:
        raise RuntimeError("Phase 6 settings content block missing")
    content_end = text.find("{% endblock %}", content_start)
    if content_end < 0:
        raise RuntimeError("Phase 6 settings content endblock missing")

    if section_start > content_end:
        script_end = text.find("</script>", section_start)
        if script_end < 0:
            raise RuntimeError("Phase 6 communication section script terminator missing")
        section_end = script_end + len("</script>")
        phase6_block = text[section_start:section_end]
        text = text[:section_start] + text[section_end:]
        # Removing a block located after content_end does not shift content_end.
        text = text[:content_end] + "\n" + phase6_block + "\n" + text[content_end:]

    replacements = {
        ">Provider<": ">SMS-Dienst<",
        ">HTTPS Webhook<": ">HTTPS-Schnittstelle<",
        "Webhook-Endpoint": "HTTPS-Endpunkt",
        "Der geheime Provider-Token wird ausschließlich serverseitig über <code>KAYI_SMS_PROVIDER_TOKEN</code> geladen und niemals hier gespeichert.": (
            "Der geheime Zugangstoken wird ausschließlich serverseitig geladen und niemals hier gespeichert."
            "<!-- KAYI_SMS_PROVIDER_TOKEN -->"
        ),
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    # Assembly contract: the communication controls must be actual content DOM,
    # not text trapped in a later JavaScript/template block.
    final_section = text.find('<section class="tt-card" data-phase6-communication>')
    final_content_end = text.find("{% endblock %}", content_start)
    if final_section < 0 or final_section > final_content_end:
        raise RuntimeError("Phase 6 communication section is outside the main content block")
    for selector_token in (
        'name="invoice_body"',
        'name="quote_body"',
        'name="reply_email"',
        'name="sms_provider"',
    ):
        if selector_token not in text[final_section:final_content_end]:
            raise RuntimeError(f"Phase 6 communication control missing from content DOM: {selector_token}")

    # The browser smoke has a strict German-only UI contract. Internal field names
    # remain unchanged because they are API/storage keys, but no English provider
    # terminology may leak into visible settings copy.
    visible_forbidden = (
        ">Provider<",
        ">HTTPS Webhook<",
        "Webhook-Endpoint",
        "Provider-Token",
    )
    for token in visible_forbidden:
        if token in text:
            raise RuntimeError(f"Phase 6 visible communication term is not Germanized: {token}")

    path.write_text(text, encoding="utf-8")


def patch_runtime_copy() -> None:
    path = ROOT / "erp" / "tooltime_parity_views.py"
    text = path.read_text(encoding="utf-8")
    replacements = {
        'return False, "Der konfigurierte SMS-Provider wird nicht unterstützt."':
            'return False, "Der konfigurierte SMS-Dienst wird nicht unterstützt."',
        'return False, "Für den SMS-Webhook ist eine HTTPS-Adresse erforderlich."':
            'return False, "Für die SMS-Schnittstelle ist eine HTTPS-Adresse erforderlich."',
        'return False, "KAYI_SMS_PROVIDER_TOKEN fehlt in der Server-Umgebung."':
            'return False, "Der SMS-Zugangstoken fehlt in der Server-Umgebung."',
        'return True, "SMS-Provider ist serverseitig einsatzbereit."':
            'return True, "SMS-Dienst ist serverseitig einsatzbereit."',
        'messages.error(request, "Der ausgewählte SMS-Provider ist ungültig.")':
            'messages.error(request, "Der ausgewählte SMS-Dienst ist ungültig.")',
        'messages.error(request, "Für den SMS-Webhook ist eine HTTPS-Adresse erforderlich.")':
            'messages.error(request, "Für die SMS-Schnittstelle ist eine HTTPS-Adresse erforderlich.")',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")
    compile(text, str(path), "exec")


def run() -> None:
    patch_template()
    patch_runtime_copy()
    print("ToolTime Phase 6 UI-Fix installiert: Kommunikationsformular liegt im Content-DOM und sichtbare Begriffe sind deutsch.")


if __name__ == "__main__":
    run()
