from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "overlays" / "ai_scope_planner"
MARKER = "A+Bau deterministic trade scope planner 2026-08-16"
VERSION = "20260816-scope-1"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Missing AI scope planner target: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def copy(rel: str) -> None:
    source = OVERLAY / rel
    target = ROOT / rel
    if not source.exists():
        raise RuntimeError(f"Missing AI scope planner overlay: {rel}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def patch_backend() -> None:
    copy("erp/ai_scope_planner.py")
    rel = "erp/assistant_views.py"
    text = read(rel)
    import_line = "from .ai_scope_planner import plan_scope_message\n"
    if import_line not in text:
        anchor = "from .store_views import has_ai_consent\n"
        if anchor not in text:
            raise RuntimeError("AI scope backend import anchor changed")
        text = text.replace(anchor, anchor + import_line, 1)

    if "scope_plan = plan_scope_message(" not in text:
        command_at = text.find("def assistant_command(request):")
        if command_at < 0:
            raise RuntimeError("AI scope assistant_command missing")
        organization_anchor = "    organization = _org(request)\n"
        organization_at = text.find(organization_anchor, command_at)
        if organization_at < 0:
            context_anchor = "    context = _compact_ui_context(payload)\n"
            context_at = text.find(context_anchor, command_at)
            if context_at < 0:
                raise RuntimeError("AI scope organization/context anchor changed")
            text = text[:context_at] + organization_anchor + text[context_at:]
            organization_at = context_at
        insert_at = organization_at + len(organization_anchor)
        hook = '''    # A+Bau deterministic scope planning runs before generic LLM/entity handling.
    # It only activates for trade-work messages or an active scope follow-up.
    scope_plan = plan_scope_message(message, request.session, payload.get("catalog") or [])
    if scope_plan is not None:
        return JsonResponse(scope_plan)
'''
        text = text[:insert_at] + hook + text[insert_at:]

    if MARKER not in text:
        text = "# " + MARKER + "\n" + text
    write(rel, text)


def patch_frontend() -> None:
    rel = "static/js/kayi-next.js"
    text = read(rel)

    if "const addScopeItems = (items, complete = false) =>" not in text:
        anchor = "  const applyActions = (actions) => {\n"
        if anchor not in text:
            raise RuntimeError("AI scope frontend applyActions anchor changed")
        helper = r'''
  // A+Bau deterministic trade scope planner.
  const setScopeQuantityNearCatalog = (button, action) => {
    if (!button || action?.quantity === null || action?.quantity === undefined) return;
    const quantity = String(action.quantity);
    const candidates = [];
    const row = button.closest('tr,[data-selected-item],[data-document-row],.nx-position-row,.position-row,.catalog-row');
    if (row) candidates.push(row);
    const labelled = $$('tr,[data-selected-item],[data-document-row],.nx-position-row,.position-row').filter((node) => {
      const haystack = normalize(node.textContent || '');
      return haystack.includes(normalize(action.label || '')) || haystack.includes(normalize(action.value || ''));
    });
    candidates.push(...labelled.slice(-3));
    for (const scope of candidates) {
      const input = scope.querySelector('input[data-quantity],input[data-menge],input[name*="quantity" i],input[name*="qty" i],input[name*="menge" i]');
      if (!input) continue;
      input.value = quantity;
      input.dispatchEvent(new Event('input',{bubbles:true}));
      input.dispatchEvent(new Event('change',{bubbles:true}));
      input.classList.add('nx-ai-filled');
      break;
    }
  };

  const addScopeItems = (items, complete = false) => {
    if (!chat || !Array.isArray(items) || !items.length) return;
    const card = document.createElement('section');
    card.className = 'nx-ai-scope-card';
    const title = document.createElement('div');
    title.className = 'nx-ai-scope-head';
    title.innerHTML = `<b>Leistungsansatz</b><span>${complete ? 'vollständig' : 'wird ergänzt'}</span>`;
    card.append(title);
    const list = document.createElement('div');
    list.className = 'nx-ai-scope-list';
    items.forEach((item) => {
      const row = document.createElement('div');
      row.className = 'nx-ai-scope-row';
      const qty = item.quantity_display || (item.quantity ?? 'offen');
      const match = item.catalog_match?.name ? `<small class="nx-ai-scope-match">Katalog: ${escapeHtml(item.catalog_match.name)}</small>` : '';
      row.innerHTML = `<div><b>${escapeHtml(item.label || 'Leistung')}</b><small>${escapeHtml(item.basis || '')}</small>${match}</div><strong>${escapeHtml(qty)} ${escapeHtml(item.unit || '')}</strong>`;
      list.append(row);
    });
    card.append(list);
    chat.append(card);
    chat.scrollTop = chat.scrollHeight;
  };

'''
        text = text.replace(anchor, helper + anchor, 1)

    old_click = "ranked.filter((item) => item.score > 0).slice(0, amount).forEach((item) => { item.button.click(); item.button.classList.add('nx-ai-filled'); changed += 1; });"
    new_click = "ranked.filter((item) => item.score > 0).slice(0, amount).forEach((item) => { item.button.click(); item.button.classList.add('nx-ai-filled'); changed += 1; if (action.scope_key) setTimeout(() => setScopeQuantityNearCatalog(item.button, action), 0); });"
    if new_click not in text:
        if old_click not in text:
            raise RuntimeError("AI scope catalog_add frontend anchor changed")
        text = text.replace(old_click, new_click, 1)

    reply_anchor = "      rememberAssistantTurn('assistant', replyText);\n"
    scope_reply = reply_anchor + "      if (!applied.navigated) addScopeItems(data.scope_items || [], Boolean(data.scope_complete));\n"
    if scope_reply not in text:
        if reply_anchor not in text:
            raise RuntimeError("AI scope frontend reply anchor changed")
        text = text.replace(reply_anchor, scope_reply, 1)

    if MARKER not in text:
        text = "// " + MARKER + "\n" + text
    write(rel, text)


def patch_styles() -> None:
    rel = "static/css/kayi-next.css"
    text = read(rel)
    if ".nx-ai-scope-card" not in text:
        text += r'''

/* A+Bau deterministic trade scope planner 2026-08-16 */
.nx-ai-scope-card {
  display: grid;
  gap: 9px;
  margin: 4px 0 14px;
  padding: 12px;
  border: 1px solid var(--nx-line, #dedbd2);
  border-radius: 14px;
  background: var(--nx-card, #fff);
}
.nx-ai-scope-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.nx-ai-scope-head b { font-size: 14px; }
.nx-ai-scope-head span {
  padding: 3px 7px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 800;
  background: rgba(173,137,43,.12);
}
.nx-ai-scope-list { display: grid; gap: 6px; }
.nx-ai-scope-row {
  display: grid;
  grid-template-columns: minmax(0,1fr) auto;
  gap: 10px;
  align-items: start;
  padding: 8px 0;
  border-top: 1px solid var(--nx-line, #ece9e1);
}
.nx-ai-scope-row:first-child { border-top: 0; }
.nx-ai-scope-row > div { display: grid; gap: 2px; min-width: 0; }
.nx-ai-scope-row b { font-size: 13px; line-height: 1.3; }
.nx-ai-scope-row small { color: var(--nx-muted, #72767c); font-size: 11.5px; line-height: 1.35; }
.nx-ai-scope-row strong { white-space: nowrap; font-size: 13px; }
.nx-ai-scope-match { color: #80671f !important; }
'''
    write(rel, text)


def install_tests() -> None:
    rel = "tests/test_ai_scope_planner.py"
    test = r'''from django.test import SimpleTestCase

from erp.ai_scope_planner import WALL_AREA_FACTOR, plan_scope_message


class Session(dict):
    modified = False


class AIScopePlannerTests(SimpleTestCase):
    def test_wall_painting_uses_floor_area_factor_and_required_coats(self):
        session = Session()
        result = plan_scope_message(
            "Wir haben eine Wohnung mit 90 qm und alle Wände müssen gestrichen werden.",
            session,
            [],
        )
        by_key = {item["key"]: item for item in result["scope_items"]}
        self.assertEqual(str(WALL_AREA_FACTOR), "2.5")
        self.assertEqual(by_key["paint.wall.primer"]["quantity_display"], "225")
        self.assertEqual(by_key["paint.wall.coat"]["quantity_display"], "225")
        self.assertIn("90 m² × 2,5 = 225 m²", result["reply"])
        self.assertIn("Untergründe", result["scope_question"])

    def test_ceiling_uses_floor_area_without_wall_multiplier(self):
        session = Session()
        result = plan_scope_message("Wohnung 90 m2, die Decke komplett streichen.", session, [])
        by_key = {item["key"]: item for item in result["scope_items"]}
        self.assertEqual(by_key["paint.ceiling.primer"]["quantity_display"], "90")
        self.assertEqual(by_key["paint.ceiling.coat"]["quantity_display"], "90")

    def test_bad_substrate_expands_prep_and_wallpaper_followup(self):
        session = Session()
        plan_scope_message("80 qm Wohnung, alle Wände streichen", session, [])
        result = plan_scope_message("nein", session, [])
        self.assertTrue(any(item["key"] == "paint.substrate.fill" for item in result["scope_items"]))
        self.assertIn("Tapeten", result["scope_question"])
        result = plan_scope_message("ja", session, [])
        wallpaper = next(item for item in result["scope_items"] if item["key"] == "paint.wallpaper.remove")
        self.assertEqual(wallpaper["quantity_display"], "200")

    def test_floor_covering_occupied_flow_never_invents_counts(self):
        session = Session()
        result = plan_scope_message("90 qm Wohnung, Boden abdecken", session, [])
        self.assertIn("bewohnt", result["scope_question"])
        result = plan_scope_message("bewohnt", session, [])
        by_key = {item["key"]: item for item in result["scope_items"]}
        self.assertEqual(by_key["protect.floor"]["quantity_display"], "90")
        self.assertEqual(by_key["protect.furniture"]["quantity_display"], "offen")
        self.assertEqual(by_key["protect.moving"]["quantity_display"], "offen")
        self.assertEqual(by_key["protect.difficulty"]["quantity_display"], "1")
        self.assertIn("Stückzahl", result["scope_question"])

    def test_door_window_and_damage_questions_are_sequential(self):
        session = Session()
        plan_scope_message("60 qm Wohnung, Wände streichen, Untergrund geeignet", session, [])
        result = plan_scope_message("3 Türen", session, [])
        self.assertEqual(session["ab_bau_scope_planner_v1"]["facts"]["door_count"], 3)
        result = plan_scope_message("4 Fenster", session, [])
        self.assertIn("Schäden", result["scope_question"])

    def test_bathroom_baseline_and_individual_technical_questions(self):
        session = Session()
        result = plan_scope_message("Wir möchten ein neues Bad komplett sanieren.", session, [])
        keys = {item["key"] for item in result["scope_items"]}
        self.assertTrue({
            "bath.walltile.demolish", "bath.floortile.demolish", "bath.substrate.fill",
            "bath.substrate.prime", "bath.walltile.install", "bath.floor.seal",
            "bath.floortile.install",
        }.issubset(keys))
        self.assertIn("Bodenfläche", result["scope_question"])
        plan_scope_message("8", session, [])
        result = plan_scope_message("24", session, [])
        self.assertIn("Wasserleitungen", result["scope_question"])
        result = plan_scope_message("Leitungen neu", session, [])
        keys = {item["key"] for item in result["scope_items"]}
        self.assertIn("bath.water.cold", keys)
        self.assertIn("bath.water.hot", keys)
        self.assertIn("laufende Meter", result["scope_question"])

    def test_bathroom_sanitary_answers_create_piece_positions(self):
        session = Session()
        plan_scope_message("Bad sanieren, Bodenfläche 8 qm, Wandfläche 24 qm, Leitungen bleiben im Bestand", session, [])
        result = plan_scope_message("ja", session, [])
        self.assertTrue(any(item["key"] == "bath.fixture.sink" and item["quantity_display"] == "1" for item in result["scope_items"]))

    def test_visible_catalog_is_matched_but_quantity_stays_trade_quantity(self):
        session = Session()
        catalog = [
            {"name": "Wände grundieren", "code": "M-01", "unit": "m²"},
            {"name": "Dispersionsfarbe Wände streichen", "code": "M-02", "unit": "m²"},
        ]
        result = plan_scope_message("100 qm Wohnung, alle Wände streichen", session, catalog)
        actions = {action["scope_key"]: action for action in result["actions"]}
        self.assertEqual(actions["paint.wall.primer"]["quantity"], 250.0)
        self.assertEqual(actions["paint.wall.coat"]["quantity"], 250.0)
        self.assertEqual(actions["paint.wall.primer"]["count"], 1)

    def test_unrelated_messages_fall_through_to_general_assistant(self):
        self.assertIsNone(plan_scope_message("Finde den Kunden Müller", Session(), []))
'''
    write(rel, test)


def patch_cache() -> None:
    rel = "templates/rebuild/base.html"
    text = read(rel)
    updated = re.sub(r"(kayi-next\.(?:css|js)'\s*%\}\?v=)[^\"'\s<]+", rf"\g<1>{VERSION}", text)
    if updated == text and VERSION not in text:
        raise RuntimeError("Could not bump AI scope asset cache")
    write(rel, updated)


def patch_production_smoke_brand_contract() -> None:
    rel = "scripts/production_browser_smoke.py"
    text = read(rel)
    text = text.replace('"KAYI Support"', '"A+Bau Support"')
    text = text.replace('"Von ToolTime zu KAYI"', '"Von ToolTime zu A+Bau"')
    text = text.replace("'KAYI Support'", "'A+Bau Support'")
    text = text.replace("'Von ToolTime zu KAYI'", "'Von ToolTime zu A+Bau'")
    write(rel, text)


def guard() -> None:
    checks = {
        "erp/ai_scope_planner.py": ["WALL_AREA_FACTOR", "plan_scope_message", "Grundierung Wände", "Wandfliesen abbrechen"],
        "erp/assistant_views.py": [MARKER, "plan_scope_message", "scope_plan"],
        "static/js/kayi-next.js": [MARKER, "addScopeItems", "setScopeQuantityNearCatalog", "scope_items"],
        "static/css/kayi-next.css": [".nx-ai-scope-card", ".nx-ai-scope-row"],
        "tests/test_ai_scope_planner.py": ["test_wall_painting_uses_floor_area_factor", "test_bathroom_baseline"],
        "templates/rebuild/base.html": [VERSION],
    }
    missing = []
    for rel, markers in checks.items():
        text = read(rel)
        for marker in markers:
            if marker not in text:
                missing.append(f"{rel}: {marker}")
    if missing:
        raise RuntimeError("A+Bau AI scope planner guard failed: " + "; ".join(missing))


def main() -> None:
    patch_backend()
    patch_frontend()
    patch_styles()
    install_tests()
    patch_cache()
    patch_production_smoke_brand_contract()
    guard()
    print("A+Bau AI trade scope planner installed: deterministic quantity rules, dependency positions, one-question follow-ups and catalog matching.")


if __name__ == "__main__":
    main()
