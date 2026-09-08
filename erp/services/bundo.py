from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from erp.models import AutomationJob, CatalogItem, IntegrationConfig


@dataclass
class PortalResult:
    success: bool
    data: dict
    requires_review: bool = True
    error: str = ""


class BundoPortalClient:
    """Konfigurierbarer Playwright-Adapter. Er liest oder befüllt Formulare und stoppt vor Submit.

    Selektoren werden in IntegrationConfig.config['selectors'] gespeichert, damit Portaländerungen
    ohne Codeänderung angepasst werden können. Ein finaler Submit ist nur nach expliziter
    Job-Freigabe möglich.
    """

    def __init__(self, integration: IntegrationConfig):
        self.integration = integration
        self.config = integration.config or {}
        self.base_url = self.config.get("base_url") or settings.BUNDO_BASE_URL
        self.username = self.config.get("username") or settings.BUNDO_USERNAME
        self.password = self.config.get("password") or settings.BUNDO_PASSWORD
        self.selectors = self.config.get("selectors", {})

    def _require(self):
        if not self.base_url or not self.username or not self.password:
            raise RuntimeError("B&O Portal-Zugang ist nicht vollständig konfiguriert.")

    def read_order(self, order_url: str) -> PortalResult:
        self._require()
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(accept_downloads=False)
            page = context.new_page()
            page.goto(self.base_url, wait_until="domcontentloaded", timeout=60_000)
            page.fill(self.selectors.get("username", "input[name='username']"), self.username)
            page.fill(self.selectors.get("password", "input[type='password']"), self.password)
            page.click(self.selectors.get("login_button", "button[type='submit']"))
            page.wait_for_load_state("networkidle")
            page.goto(order_url, wait_until="networkidle", timeout=60_000)
            data = {
                "url": page.url,
                "title": page.title(),
                "body_text": page.locator("body").inner_text()[:200_000],
            }
            browser.close()
        return PortalResult(True, data)

    def fill_positions(self, order_url: str, positions: list[dict], submit: bool = False) -> PortalResult:
        self._require()
        if submit is True:
            raise PermissionError("Direkter Submit ist gesperrt. Verwende submit_approved_job().")
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(accept_downloads=False)
            page = context.new_page()
            page.goto(self.base_url, wait_until="domcontentloaded", timeout=60_000)
            page.fill(self.selectors.get("username", "input[name='username']"), self.username)
            page.fill(self.selectors.get("password", "input[type='password']"), self.password)
            page.click(self.selectors.get("login_button", "button[type='submit']"))
            page.wait_for_load_state("networkidle")
            page.goto(order_url, wait_until="networkidle", timeout=60_000)
            add_button = self.selectors.get("add_position", "button:has-text('Position hinzufügen')")
            code_selector = self.selectors.get("position_code", "input[name*='code']")
            qty_selector = self.selectors.get("position_quantity", "input[name*='quantity']")
            for position in positions:
                page.click(add_button)
                page.locator(code_selector).last.fill(str(position.get("code", "")))
                page.locator(qty_selector).last.fill(str(position.get("quantity", 1)))
            screenshot = page.screenshot(full_page=True)
            browser.close()
        return PortalResult(True, {"positions": positions, "screenshot_bytes": len(screenshot)}, requires_review=True)


def build_position_suggestions(report_text: str, organization) -> list[dict]:
    """Deterministischer Fallback: katalogbasierte Schlüsselwortsuche, nie automatische Freigabe."""
    lowered = report_text.lower()
    suggestions = []
    for item in CatalogItem.objects.filter(organization=organization, active=True)[:5000]:
        tokens = [t for t in item.name.lower().replace("/", " ").split() if len(t) >= 5]
        matches = [t for t in tokens if t in lowered]
        if matches:
            suggestions.append({
                "code": item.code,
                "description": item.name,
                "quantity": 1,
                "unit": item.unit,
                "unit_price": str(item.sales_price),
                "confidence": min(0.95, 0.45 + 0.1 * len(matches)),
                "evidence": ", ".join(matches),
                "approved": False,
            })
    return sorted(suggestions, key=lambda x: x["confidence"], reverse=True)[:50]


def approve_job(job: AutomationJob, user) -> None:
    job.status = AutomationJob.Status.APPROVED
    job.approved_by = user
    job.approved_at = timezone.now()
    job.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
