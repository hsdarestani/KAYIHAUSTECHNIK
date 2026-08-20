from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SMOKE = ROOT / "scripts" / "production_browser_smoke.py"
text = SMOKE.read_text(encoding="utf-8")

marker = "            # A+BAU TOOLTIME PHASE 8 ONLINE ACCEPTANCE\n"
marker_pos = text.find(marker)
if marker_pos < 0:
    raise RuntimeError("Phase 8 online-acceptance browser-smoke marker missing")

browser_action = "            response = page.goto(urljoin(base_url, phase8_path.lstrip(\"/\")), wait_until=\"domcontentloaded\", timeout=30_000)\n"
action_pos = text.find(browser_action, marker_pos)
if action_pos < 0:
    raise RuntimeError("Phase 8 online-acceptance browser action anchor missing")

# Django ORM is synchronous. Playwright's sync facade internally owns an async
# loop while a browser context is active, so Django correctly rejects ORM calls
# made there. Prepare the database fixture before entering sync_playwright and
# let the browser section consume only the resulting public URL path.
browser_prefix = marker + '''            phase8_path = os.environ.get("KAYI_PHASE8_PUBLIC_PATH", "")\n            if not phase8_path:\n                fail("Online-Annahme-Smoke-Pfad wurde vor dem Browserstart nicht vorbereitet")\n'''
text = text[:marker_pos] + browser_prefix + text[action_pos:]

fixture_anchor = "    old_password_hash = user.password\n"
fixture = '''    # A+BAU TOOLTIME PHASE 8 ONLINE ACCEPTANCE FIXTURE\n    from django.urls import reverse as phase8_reverse\n    from django.utils import timezone as phase8_timezone\n    from erp import models as phase8_models\n    from erp.services.tooltime_parity_finance import finalize_quote as phase8_finalize_quote\n\n    phase8_quote = (\n        phase8_models.Quote.objects.filter(organization_id=organization_id, project__isnull=False)\n        .select_related("project__customer")\n        .order_by("-pk")\n        .first()\n    )\n    if phase8_quote is None:\n        fail("Online-Annahme-Smoke benötigt mindestens ein Demo-Angebot")\n    phase8_customer = phase8_quote.project.customer\n    phase8_customer.postal_code = "60313"\n    phase8_customer.type = "private"\n    phase8_customer.save(update_fields=["postal_code", "type", "updated_at"])\n    phase8_meta = phase8_finalize_quote(phase8_quote)\n    phase8_quote.status = "sent"\n    phase8_quote.save(update_fields=["status", "updated_at"])\n    phase8_meta.web_view_enabled = True\n    phase8_meta.accepted_at = None\n    phase8_meta.rejected_at = None\n    phase8_meta.withdrawn_at = None\n    phase8_meta.acceptance_details = {}\n    phase8_meta.finalized_at = phase8_meta.finalized_at or phase8_timezone.now()\n    phase8_meta.save(update_fields=["web_view_enabled", "accepted_at", "rejected_at", "withdrawn_at", "acceptance_details", "finalized_at", "updated_at"])\n    os.environ["KAYI_PHASE8_PUBLIC_PATH"] = phase8_reverse("next-public-quote", args=[phase8_meta.web_token])\n\n'''

if "A+BAU TOOLTIME PHASE 8 ONLINE ACCEPTANCE FIXTURE" not in text:
    anchor_pos = text.find(fixture_anchor)
    if anchor_pos < 0:
        raise RuntimeError("Phase 8 pre-Playwright fixture anchor missing")
    text = text[:anchor_pos] + fixture + text[anchor_pos:]

# Guard against reintroducing ORM work into the active browser context.
office_start = text.find("def run_office_surface(")
field_start = text.find("\ndef run_field_surface(", office_start)
phase8_pos = text.find(marker, office_start, field_start)
if phase8_pos < 0:
    raise RuntimeError("Phase 8 browser check is not inside office surface")
phase8_browser_segment = text[phase8_pos:text.find("            context.close()\n", phase8_pos)]
for forbidden in ("phase8_models.", "get_user_model().objects", "phase8_finalize_quote("):
    if forbidden in phase8_browser_segment:
        raise RuntimeError(f"Phase 8 browser context still performs synchronous ORM work: {forbidden}")

SMOKE.write_text(text, encoding="utf-8")
compile(text, str(SMOKE), "exec")
print("ToolTime Phase 8 browser fixture is prepared before Playwright; browser context performs no Django ORM calls.")
