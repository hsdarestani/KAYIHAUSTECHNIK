from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "overlays" / "ai_scope_planner"
MARKER = "A+Bau AI scope authoritative catalog 2026-08-16"
VERSION = "20260816-scope-2"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Missing authoritative scope target: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def copy_catalog_service() -> None:
    source = OVERLAY / "erp" / "ai_scope_catalog.py"
    target = ROOT / "erp" / "ai_scope_catalog.py"
    if not source.exists():
        raise RuntimeError("AI scope catalog overlay missing")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def patch_backend() -> None:
    rel = "erp/assistant_views.py"
    text = read(rel)
    import_line = "from .ai_scope_catalog import enrich_scope_with_authoritative_catalog\n"
    if import_line not in text:
        anchor = "from .ai_scope_planner import plan_scope_message\n"
        if anchor not in text:
            raise RuntimeError("Authoritative scope backend import anchor changed")
        text = text.replace(anchor, anchor + import_line, 1)
    old = '''    scope_plan = plan_scope_message(message, request.session, payload.get("catalog") or [])
    if scope_plan is not None:
        return JsonResponse(scope_plan)
'''
    new = '''    scope_plan = plan_scope_message(message, request.session, payload.get("catalog") or [])
    if scope_plan is not None:
        scope_plan = enrich_scope_with_authoritative_catalog(scope_plan, organization, request)
        return JsonResponse(scope_plan)
'''
    if new not in text:
        if old not in text:
            raise RuntimeError("Authoritative scope response hook changed")
        text = text.replace(old, new, 1)
    if MARKER not in text:
        text = "# " + MARKER + "\n" + text
    write(rel, text)


def patch_bo_direct_search_frontend() -> None:
    rel = "static/js/bo-direct-search.js"
    text = read(rel)
    old = "  const addPosition = (item) => isABBau() ? addABBauPosition(item) : addLegacyPosition(item);\n"
    new = r'''  const addPosition = (item) => isABBau() ? addABBauPosition(item) : addLegacyPosition(item);

  // Public draft-only handoff for the A+Bau assistant. It uses the exact same
  // B&O row insertion logic as a manual click, then replaces the default quantity
  // with the deterministic trade quantity. Unknown quantities stay empty rather
  // than being invented as 1.
  window.ABBauAddPricedPosition = (item, quantity = null) => {
    if (!item || !item.id) return false;
    addPosition(item);
    const rows = Array.from(table.querySelectorAll('[data-bo-reference-id],.ab-item-row,tbody tr'));
    const row = rows.reverse().find((candidate) => String(candidate.dataset.boReferenceId || '') === String(item.id || ''));
    if (!row) return false;
    const field = row.querySelector('[name="item_quantity"]');
    if (field) {
      field.value = quantity === null || quantity === undefined ? '' : String(quantity);
      emit(field, 'input');
      emit(field, 'change');
    }
    row.classList.add('nx-ai-filled');
    return true;
  };
'''
    if "window.ABBauAddPricedPosition" not in text:
        if old not in text:
            raise RuntimeError("B&O direct-search addPosition anchor changed")
        text = text.replace(old, new, 1)
    if MARKER not in text:
        text = "// " + MARKER + "\n" + text
    write(rel, text)


def patch_global_assistant() -> None:
    rel = "static/js/kayi-next.js"
    text = read(rel)
    catalog_branch = "      } else if (action.type === 'catalog_add') {\n"
    bo_branch = r'''      } else if (action.type === 'bo_catalog_add') {
        if (action.item && typeof window.ABBauAddPricedPosition === 'function') {
          const inserted = window.ABBauAddPricedPosition(action.item, action.quantity ?? null);
          if (inserted) changed += 1;
        }
      } else if (action.type === 'catalog_add') {
'''
    if "action.type === 'bo_catalog_add'" not in text:
        if catalog_branch not in text:
            raise RuntimeError("Global assistant catalog branch anchor changed")
        text = text.replace(catalog_branch, bo_branch, 1)
    if MARKER not in text:
        text = "// " + MARKER + "\n" + text
    write(rel, text)


def bump_assets() -> None:
    base = "templates/rebuild/base.html"
    text = read(base)
    updated = re.sub(r"(kayi-next\.(?:css|js)'\s*%\}\?v=)[^\"'\s<]+", rf"\g<1>{VERSION}", text)
    write(base, updated)

    editor = "templates/rebuild/document_editor.html"
    text = read(editor)
    text = re.sub(r"(bo-direct-search\.js'\s*%\}\?v=)[^\"'\s<]+", rf"\g<1>{VERSION}", text)
    write(editor, text)


def install_tests() -> None:
    rel = "tests/test_ai_scope_authoritative_catalog.py"
    write(rel, r'''from decimal import Decimal
from pathlib import Path

from django.test import TestCase

from erp.ai_scope_catalog import enrich_scope_with_authoritative_catalog
from erp.models import Organization, PriceItem, PriceSource


class DummyProfile:
    role = "office"
    is_mobile_worker = False


class DummyUser:
    profile = DummyProfile()


class DummyRequest:
    user = DummyUser()


class AIScopeAuthoritativeCatalogTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="A+Bau scope catalog")
        self.source = PriceSource.objects.create(
            organization=self.org, name="B&O VA04", original_filename="B&O-VA04.xlsx",
            sha256="c" * 64, active=True,
        )
        self.primer = PriceItem.objects.create(
            organization=self.org, source=self.source, code="VA04-MAL-GR",
            description="Wandfläche grundieren", unit="m²", sales_price=Decimal("2.40"),
        )
        self.paint = PriceItem.objects.create(
            organization=self.org, source=self.source, code="VA04-MAL-DS",
            description="Wandfläche mit Dispersionsfarbe streichen", unit="m²", sales_price=Decimal("7.80"),
        )

    def test_scope_can_resolve_real_price_rows_outside_visible_catalog(self):
        plan = {
            "actions": [],
            "scope_items": [
                {"key":"paint.wall.primer","label":"Grundierung Wände","quantity":225.0,"unit":"m²","catalog_terms":["Wände grundieren","Grundierung Wand"],"catalog_match":None},
                {"key":"paint.wall.coat","label":"Dispersionsfarbanstrich Wände","quantity":225.0,"unit":"m²","catalog_terms":["Dispersionsfarbe Wände","Wände streichen"],"catalog_match":None},
            ],
        }
        result = enrich_scope_with_authoritative_catalog(plan, self.org, DummyRequest())
        actions = {a["scope_key"]: a for a in result["actions"]}
        self.assertEqual(actions["paint.wall.primer"]["type"], "bo_catalog_add")
        self.assertEqual(actions["paint.wall.primer"]["quantity"], 225.0)
        self.assertEqual(actions["paint.wall.coat"]["quantity"], 225.0)
        self.assertEqual(result["scope_items"][0]["catalog_match"]["code"], "VA04-MAL-GR")

    def test_technician_never_receives_priced_catalog_payload(self):
        request = DummyRequest()
        request.user.profile.role = "technician"
        plan = {"actions": [], "scope_items": [{"key":"x","label":"Grundierung Wände","quantity":225.0,"unit":"m²","catalog_terms":["Grundierung Wand"],"catalog_match":None}]}
        result = enrich_scope_with_authoritative_catalog(plan, self.org, request)
        self.assertEqual(result["actions"], [])
        self.assertIsNone(result["scope_items"][0]["catalog_match"])

    def test_frontend_uses_same_direct_search_row_inserter(self):
        js = Path("static/js/bo-direct-search.js").read_text(encoding="utf-8")
        assistant = Path("static/js/kayi-next.js").read_text(encoding="utf-8")
        self.assertIn("window.ABBauAddPricedPosition", js)
        self.assertIn("quantity === null", js)
        self.assertIn("bo_catalog_add", assistant)
''')


def guard() -> None:
    checks = {
        "erp/ai_scope_catalog.py": ["enrich_scope_with_authoritative_catalog", "search_bo_prices", "_can_see_prices"],
        "erp/assistant_views.py": ["enrich_scope_with_authoritative_catalog(scope_plan, organization, request)"],
        "static/js/bo-direct-search.js": ["window.ABBauAddPricedPosition", "quantity === null"],
        "static/js/kayi-next.js": ["bo_catalog_add", "ABBauAddPricedPosition"],
        "tests/test_ai_scope_authoritative_catalog.py": ["test_scope_can_resolve_real_price_rows_outside_visible_catalog", "test_technician_never_receives_priced_catalog_payload"],
        "templates/rebuild/base.html": [VERSION],
        "templates/rebuild/document_editor.html": [VERSION],
    }
    missing = []
    for rel, needles in checks.items():
        text = read(rel)
        for needle in needles:
            if needle not in text:
                missing.append(f"{rel}: {needle}")
    if missing:
        raise RuntimeError("A+Bau authoritative scope catalog guard failed: " + "; ".join(missing))


def main() -> None:
    copy_catalog_service()
    patch_backend()
    patch_bo_direct_search_frontend()
    patch_global_assistant()
    bump_assets()
    install_tests()
    guard()
    print("A+Bau AI scope now resolves authoritative priced B&O rows beyond the visible quick catalog and inserts draft quantities without price leakage.")


if __name__ == "__main__":
    main()
