from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch_template() -> None:
    path = ROOT / "templates" / "rebuild" / "tooltime_settings.html"
    text = path.read_text(encoding="utf-8")

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
    print("ToolTime Phase 6 UI-Sprachfix installiert: Kommunikationseinstellungen sind sichtbar vollständig deutsch.")


if __name__ == "__main__":
    run()
