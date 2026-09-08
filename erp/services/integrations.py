from __future__ import annotations

import imaplib

import requests
from django.conf import settings

from erp.models import IntegrationConfig


class IntegrationDisabledError(RuntimeError):
    pass


AVAILABLE_PROVIDERS = {
    IntegrationConfig.Provider.GMX,
    IntegrationConfig.Provider.OPENAI,
    IntegrationConfig.Provider.MARKETPLACE,
    IntegrationConfig.Provider.WEBPUSH,
}


def get_integration(organization, provider: str) -> IntegrationConfig:
    integration, _ = IntegrationConfig.objects.get_or_create(organization=organization, provider=provider)
    return integration


def integration_available(provider: str) -> bool:
    return provider in AVAILABLE_PROVIDERS


def integration_configured(organization, provider: str, integration: IntegrationConfig | None = None) -> bool:
    config = (integration.config or {}) if integration else {}
    if provider == IntegrationConfig.Provider.OPENAI:
        return bool(str(settings.OPENAI_API_KEY).strip())
    if provider == IntegrationConfig.Provider.GMX:
        return bool(str(settings.GMX_EMAIL).strip() and str(settings.GMX_PASSWORD).strip())
    if provider == IntegrationConfig.Provider.MARKETPLACE:
        return bool(str(config.get("search_url") or "").strip())
    if provider == IntegrationConfig.Provider.WEBPUSH:
        return True
    return False


def integration_enabled(organization, provider: str) -> bool:
    if not integration_available(provider):
        return False
    integration = IntegrationConfig.objects.filter(organization=organization, provider=provider, enabled=True).first()
    return bool(integration and integration_configured(organization, provider, integration))


def require_integration_enabled(organization, provider: str) -> IntegrationConfig:
    integration = get_integration(organization, provider)
    if not integration_available(provider):
        raise IntegrationDisabledError(f"{integration.get_provider_display()} ist noch nicht als Live-Integration freigegeben.")
    if not integration.enabled:
        raise IntegrationDisabledError(f"{integration.get_provider_display()} ist deaktiviert.")
    if not integration_configured(organization, provider, integration):
        raise IntegrationDisabledError(f"{integration.get_provider_display()} ist nicht vollständig konfiguriert.")
    return integration


def integration_cards(organization) -> list[dict]:
    existing = {item.provider: item for item in IntegrationConfig.objects.filter(organization=organization)}
    descriptions = {
        IntegrationConfig.Provider.GMX: "E-Mail-Eingang und Versand über das serverseitige GMX-Konto.",
        IntegrationConfig.Provider.TOOLTIME: "ToolTime-Daten können bereits über das Import Center als CSV/XLSX übernommen werden.",
        IntegrationConfig.Provider.BUNDO: "Portal-Automation ist vorbereitet, aber noch nicht für den Live-Betrieb freigegeben.",
        IntegrationConfig.Provider.OPENAI: f"KI-Funktionen über das serverseitige Modell {settings.OPENAI_MODEL}.",
        IntegrationConfig.Provider.DATEV: "DATEV ist als Platzhalter vorgesehen; eine Live-Schnittstelle ist noch nicht implementiert.",
        IntegrationConfig.Provider.MARKETPLACE: "Externe Materialsuche über eine konfigurierte Supplier-API.",
        IntegrationConfig.Provider.WEBPUSH: "Browser-Benachrichtigungen der installierten A+Bau-PWA.",
    }
    cards = []
    for value, label in IntegrationConfig.Provider.choices:
        item = existing.get(value)
        enabled = bool(item and item.enabled)
        available = integration_available(value)
        configured = integration_configured(organization, value, item) if available else False
        if not available:
            state = "unavailable"
            status = "Noch nicht verfügbar"
        elif enabled and configured:
            state = "connected"
            status = "Verbunden"
        elif not configured:
            state = "setup"
            status = "Einrichtung erforderlich"
        else:
            state = "disabled"
            status = "Deaktiviert"
        cards.append({
            "value": value,
            "label": label,
            "item": item,
            "enabled": enabled,
            "available": available,
            "configured": configured,
            "state": state,
            "status": status,
            "description": descriptions.get(value, ""),
            "can_toggle": available and (enabled or configured),
            "can_test": available and configured,
        })
    return cards


def test_integration_connection(organization, provider: str) -> str:
    integration = get_integration(organization, provider)
    if not integration_available(provider):
        raise RuntimeError(f"{integration.get_provider_display()} ist noch nicht für den Live-Betrieb freigegeben.")
    if not integration_configured(organization, provider, integration):
        raise RuntimeError(f"{integration.get_provider_display()} ist nicht vollständig konfiguriert.")

    if provider == IntegrationConfig.Provider.OPENAI:
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        client.models.retrieve(settings.OPENAI_MODEL)
        return f"OpenAI erreichbar · Modell: {settings.OPENAI_MODEL}"

    if provider == IntegrationConfig.Provider.GMX:
        with imaplib.IMAP4_SSL(settings.GMX_IMAP_HOST, timeout=15) as mailbox:
            mailbox.login(settings.GMX_EMAIL, settings.GMX_PASSWORD)
            mailbox.noop()
        return f"GMX erreichbar · Konto: {settings.GMX_EMAIL}"

    if provider == IntegrationConfig.Provider.MARKETPLACE:
        config = integration.config or {}
        headers = {"Authorization": f"Bearer {config.get('token')}"} if config.get("token") else {}
        response = requests.get(
            config["search_url"],
            params={config.get("query_param", "q"): "test"},
            headers=headers,
            timeout=12,
        )
        response.raise_for_status()
        return f"Marketplace API erreichbar · HTTP {response.status_code}"

    if provider == IntegrationConfig.Provider.WEBPUSH:
        return "PWA-Benachrichtigungen sind serverseitig verfügbar. Die Browser-Berechtigung wird pro Gerät verwaltet."

    raise RuntimeError("Für diese Integration ist kein Verbindungstest verfügbar.")
