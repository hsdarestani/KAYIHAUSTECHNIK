from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "KAYI STATEFUL ENTITY CHAT 2026-08-11"
VERSION = "20260811-3"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Missing stateful KI target: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_backend() -> None:
    rel = "erp/assistant_views.py"
    text = read(rel)

    # "client" must be treated as an entity type, not as a literal search term.
    text = text.replace(
        '    "mitarbeiter", "employee", "employees", "kunde", "kunden", "customer", "customers",\n',
        '    "mitarbeiter", "employee", "employees", "kunde", "kunden", "customer", "customers", "client", "clients",\n',
        1,
    )

    if "def _requested_entity_route(message: str) -> str:" not in text:
        anchor = "\n\n@login_required\n@require_POST\ndef assistant_command(request):\n"
        if anchor not in text:
            raise RuntimeError("Stateful KI assistant command anchor changed")
        helpers = r'''

# KAYI STATEFUL ENTITY CHAT 2026-08-11
_ENTITY_ROUTE_ALIASES = {
    "customers": {"kunde", "kunden", "customer", "customers", "client", "clients", "auftraggeber"},
    "projects": {"projekt", "projekte", "project", "projects", "auftrag", "aufträge", "auftrage"},
    "employees": {"mitarbeiter", "employee", "employees", "monteur", "monteure", "techniker", "technician"},
    "appointments": {"termin", "termine", "appointment", "appointments", "einsatz", "einsätze", "einsatze"},
}
_ENTITY_LOOKUP_VERBS = {
    "find", "search", "show", "open", "locate", "lookup",
    "finde", "finden", "suche", "suchen", "zeig", "zeige", "öffne", "offne", "such",
}
_ENTITY_OPEN_VERBS = {"open", "öffne", "offne", "go", "geh", "gehe", "navigate", "navigiere"}


def _assistant_tokens(message: str) -> list[str]:
    return [token.casefold().strip("._-+") for token in re.findall(r"[\w@.+-]+", message or "", flags=re.UNICODE) if token.strip("._-+")]


def _requested_entity_route(message: str) -> str:
    tokens = set(_assistant_tokens(message))
    for route, aliases in _ENTITY_ROUTE_ALIASES.items():
        if tokens.intersection(aliases):
            return route
    return ""


def _has_entity_lookup_verb(message: str) -> bool:
    return bool(set(_assistant_tokens(message)).intersection(_ENTITY_LOOKUP_VERBS))


def _has_entity_open_verb(message: str) -> bool:
    return bool(set(_assistant_tokens(message)).intersection(_ENTITY_OPEN_VERBS))


def _compact_assistant_history(payload: dict[str, Any]) -> list[dict[str, str]]:
    compact: list[dict[str, str]] = []
    for raw in (payload.get("history") or [])[-10:]:
        if not isinstance(raw, dict):
            continue
        role = str(raw.get("role") or "").strip().casefold()
        content = str(raw.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        compact.append({"role": role, "content": content[:900]})
    return compact


def _filter_entity_matches(matches: list[dict[str, Any]], route: str) -> list[dict[str, Any]]:
    if not route:
        return list(matches)
    return [item for item in matches if item.get("route") == route]


def _resolve_entity_search(request, organization, message: str) -> dict[str, Any]:
    """Resolve explicit searches and short follow-ups against real records only.

    The latest broad result set is stored in the Django session so a reply such as
    "client" can select the customer from the immediately preceding "find ashkan"
    request even after a page navigation/reload.
    """
    route = _requested_entity_route(message)
    terms = _search_terms(message)
    has_lookup = _has_entity_lookup_verb(message)
    previous = request.session.get("kayi_ai_entity_state") or {}
    previous_query = str(previous.get("query") or "").strip()
    previous_matches = previous.get("matches") if isinstance(previous.get("matches"), list) else []

    followup = bool(route and not terms and not has_lookup and previous_query)
    needs_query = bool(route and has_lookup and not terms)

    if terms:
        query = " ".join(terms)
        broad_matches = _entity_search_context(organization, query)
        request.session["kayi_ai_entity_state"] = {
            "query": query[:300],
            "matches": broad_matches[:20],
            "updated_at": timezone.now().isoformat(),
        }
        request.session.modified = True
    elif followup:
        query = previous_query
        broad_matches = previous_matches or _entity_search_context(organization, previous_query)
    else:
        query = ""
        broad_matches = [] if needs_query else _entity_search_context(organization, message)

    matches = _filter_entity_matches(broad_matches, route)
    return {
        "route": route,
        "query": query,
        "matches": matches[:20],
        "broad_matches": broad_matches[:20],
        "followup": followup,
        "needs_query": needs_query,
        "lookup": has_lookup,
        "open": _has_entity_open_verb(message),
    }


def _entity_route_label(route: str, count: int = 1) -> str:
    labels = {
        "customers": ("Kunde", "Kunden"),
        "projects": ("Projekt", "Projekte"),
        "employees": ("Mitarbeiter", "Mitarbeiter"),
        "appointments": ("Termin", "Termine"),
    }
    singular, plural = labels.get(route, ("Treffer", "Treffer"))
    return singular if count == 1 else plural


def _direct_entity_response(search: dict[str, Any]) -> dict[str, Any] | None:
    """Handle simple find/select flows deterministically instead of asking the LLM.

    This prevents contradictory replies such as finding a customer in one turn and
    claiming that same customer does not exist in the next turn.
    """
    route = str(search.get("route") or "")
    matches = list(search.get("matches") or [])
    broad_matches = list(search.get("broad_matches") or [])
    query = str(search.get("query") or "").strip()
    followup = bool(search.get("followup"))
    lookup = bool(search.get("lookup"))
    needs_query = bool(search.get("needs_query"))
    explicit_open = bool(search.get("open"))

    if not (lookup or followup):
        return None

    if needs_query:
        label = _entity_route_label(route, 1).lower()
        return {"ok": True, "reply": f"Welchen {label} soll ich suchen? Nenne mir bitte einen Namen, eine Nummer oder einen eindeutigen Suchbegriff.", "actions": [], "results": []}

    if not matches:
        if route:
            label = _entity_route_label(route, 1)
            suffix = f" zu „{query}“" if query else ""
            return {"ok": True, "reply": f"Ich habe keinen passenden {label}{suffix} gefunden.", "actions": [], "results": []}
        suffix = f" zu „{query}“" if query else ""
        return {"ok": True, "reply": f"Ich habe keine passenden Einträge{suffix} gefunden.", "actions": [], "results": []}

    # A short type-only follow-up ("client", "project") means the user selected
    # that category from the previous result. If it resolves to one record, open it.
    if (followup or explicit_open) and len(matches) == 1:
        match = matches[0]
        return {
            "ok": True,
            "reply": f"Ich öffne {match.get('label') or _entity_route_label(str(match.get('route') or ''), 1)}.",
            "actions": [{"type": "navigate_record", "target": str(match.get("route") or ""), "value": str(match.get("id") or ""), "count": 0}],
            "results": matches,
        }

    if len(matches) == 1:
        match = matches[0]
        return {
            "ok": True,
            "reply": f"Gefunden: {match.get('label')}. Du kannst den Eintrag direkt öffnen.",
            "actions": [],
            "results": matches,
        }

    if route:
        label = _entity_route_label(route, len(matches))
        return {
            "ok": True,
            "reply": f"Ich habe {len(matches)} passende {label} gefunden. Wähle den richtigen Eintrag aus.",
            "actions": [],
            "results": matches,
        }

    route_counts: dict[str, int] = {}
    for item in broad_matches:
        item_route = str(item.get("route") or "")
        route_counts[item_route] = route_counts.get(item_route, 0) + 1
    summary = ", ".join(f"{count} {_entity_route_label(item_route, count)}" for item_route, count in route_counts.items())
    return {
        "ok": True,
        "reply": f"Ich habe {len(matches)} echte Treffer zu „{query}“ gefunden" + (f": {summary}." if summary else ".") + " Wähle einen Eintrag oder sage z. B. „client“ bzw. „project“.",
        "actions": [],
        "results": matches,
    }
'''
        text = text.replace(anchor, helpers + anchor, 1)

    current_context = '''    organization = _org(request)
    context = _compact_ui_context(payload)
    context["now_local"] = timezone.localtime().isoformat(timespec="minutes")
    context["entity_matches"] = _entity_search_context(organization, message)
    schema = {
'''
    stateful_context = '''    organization = _org(request)
    context = _compact_ui_context(payload)
    context["now_local"] = timezone.localtime().isoformat(timespec="minutes")
    conversation_history = _compact_assistant_history(payload)
    entity_search = _resolve_entity_search(request, organization, message)
    context["conversation_history"] = conversation_history
    context["entity_matches"] = entity_search["matches"]
    context["entity_focus"] = {
        "route": entity_search["route"],
        "query": entity_search["query"],
        "followup": entity_search["followup"],
    }
    direct_entity = _direct_entity_response(entity_search)
    if direct_entity is not None:
        return JsonResponse(direct_entity)
    schema = {
'''
    if stateful_context not in text:
        if current_context not in text:
            raise RuntimeError("Stateful KI context anchor changed")
        text = text.replace(current_context, stateful_context, 1)

    history_prompt_anchor = (
        '        "Niemals allein aufgrund eines Personennamens zu Mitarbeiter/Kunden navigieren, wenn entity_matches keinen solchen Treffer enthält. "\n'
        '        "Wenn etwas nicht sicher möglich ist, erkläre kurz warum und gib action=none zurück. Antworte auf Deutsch.\\n\\n"\n'
    )
    history_prompt_new = (
        '        "Niemals allein aufgrund eines Personennamens zu Mitarbeiter/Kunden navigieren, wenn entity_matches keinen solchen Treffer enthält. "\n'
        '        "conversation_history enthält die letzten kurzen Chat-Turns. Nutze sie für Anschlusswörter wie dieser, der Kunde, client, project, dort, ihn oder das Projekt. "\n'
        '        "Wenn entity_focus.followup=true ist, bezieht sich die aktuelle kurze Nachricht auf die unmittelbar vorherige Entitätssuche. "\n'
        '        "Behaupte niemals, ein zuvor in entity_matches vorhandener Datensatz existiere nicht, sofern der neue Kontext ihn weiterhin enthält. "\n'
        '        "Wenn etwas nicht sicher möglich ist, erkläre kurz warum und gib action=none zurück. Antworte auf Deutsch.\\n\\n"\n'
    )
    if history_prompt_new not in text:
        if history_prompt_anchor not in text:
            raise RuntimeError("Stateful KI prompt anchor changed")
        text = text.replace(history_prompt_anchor, history_prompt_new, 1)

    final_return = '    return JsonResponse({"ok": True, "reply": str(result.get("reply") or ""), "actions": result.get("actions") or []})\n'
    final_return_new = '    return JsonResponse({"ok": True, "reply": str(result.get("reply") or ""), "actions": result.get("actions") or [], "results": []})\n'
    if final_return_new not in text:
        if final_return not in text:
            raise RuntimeError("Stateful KI response anchor changed")
        text = text.replace(final_return, final_return_new, 1)

    write(rel, text)


def patch_frontend() -> None:
    rel = "static/js/kayi-next.js"
    text = read(rel)

    if "kayi-assistant-history-v3" not in text:
        anchor = "  const assistantUrl = drawer?.dataset.assistantUrl;\n"
        if anchor not in text:
            raise RuntimeError("Stateful KI frontend assistantUrl anchor changed")
        history = r'''
  const assistantHistoryKey = 'kayi-assistant-history-v3';
  let assistantHistory = [];
  try {
    const stored = JSON.parse(sessionStorage.getItem(assistantHistoryKey) || '[]');
    if (Array.isArray(stored)) assistantHistory = stored.filter((item) => item && ['user','assistant'].includes(item.role) && item.content).slice(-12);
  } catch (_) { assistantHistory = []; }
  const rememberAssistantTurn = (role, content) => {
    const value = String(content || '').trim();
    if (!value || !['user','assistant'].includes(role)) return;
    assistantHistory.push({role,content:value.slice(0,900)});
    assistantHistory = assistantHistory.slice(-12);
    try { sessionStorage.setItem(assistantHistoryKey, JSON.stringify(assistantHistory)); } catch (_) {}
  };
'''
        text = text.replace(anchor, anchor + history, 1)

    if "const addEntityResults = (results) =>" not in text:
        anchor = "  const applyActions = (actions) => {\n"
        if anchor not in text:
            raise RuntimeError("Stateful KI frontend applyActions anchor changed")
        results_helper = r'''
  const entityRouteLabels = {customers:'Kunde',projects:'Projekt',employees:'Mitarbeiter',appointments:'Termin'};
  const entityRecordUrl = (item) => {
    const route = routes[item?.route];
    const id = String(item?.id || '').trim();
    if (!route || !/^\d+$/.test(id)) return '';
    return `${route}${id}/`;
  };
  const addEntityResults = (results) => {
    if (!chat || !Array.isArray(results) || !results.length) return;
    const list = document.createElement('div');
    list.className = 'nx-assistant-results';
    results.slice(0,12).forEach((item) => {
      const href = entityRecordUrl(item);
      if (!href) return;
      const link = document.createElement('a');
      link.className = 'nx-assistant-result';
      link.href = href;
      const kind = entityRouteLabels[item.route] || 'Eintrag';
      link.innerHTML = `<span class="nx-assistant-result-kind">${escapeHtml(kind)}</span><b>${escapeHtml(item.label || kind)}</b>${item.detail ? `<small>${escapeHtml(item.detail)}</small>` : ''}`;
      list.append(link);
    });
    if (list.childElementCount) { chat.append(list); chat.scrollTop = chat.scrollHeight; }
  };

'''
        text = text.replace(anchor, results_helper + anchor, 1)

    old_start = '''    openAssistant();
    addMessage(message,'user');
    if (drawerInput) drawerInput.value = '';
'''
    new_start = '''    openAssistant();
    const priorHistory = assistantHistory.slice(-10);
    addMessage(message,'user');
    rememberAssistantTurn('user', message);
    if (drawerInput) drawerInput.value = '';
'''
    if new_start not in text:
        if old_start not in text:
            raise RuntimeError("Stateful KI frontend run start anchor changed")
        text = text.replace(old_start, new_start, 1)

    old_payload = "        body:JSON.stringify({message,path:window.location.pathname + window.location.search,title:document.title,fields:collectFields(),catalog:collectCatalog()}),\n"
    new_payload = "        body:JSON.stringify({message,path:window.location.pathname + window.location.search,title:document.title,fields:collectFields(),catalog:collectCatalog(),history:priorHistory}),\n"
    if new_payload not in text:
        if old_payload not in text:
            raise RuntimeError("Stateful KI frontend payload anchor changed")
        text = text.replace(old_payload, new_payload, 1)

    old_reply = '''      const applied = applyActions(data.actions || []);
      addMessage(data.reply || 'Erledigt.','ai', applied.changed ? `${applied.changed} Eingabe(n) im aktuellen Entwurf angepasst. Bitte prüfen und anschließend selbst speichern.` : 'Keine irreversible Aktion wurde automatisch ausgeführt.');
'''
    new_reply = '''      const applied = applyActions(data.actions || []);
      const replyText = data.reply || 'Erledigt.';
      addMessage(replyText,'ai', applied.changed ? `${applied.changed} Eingabe(n) im aktuellen Entwurf angepasst. Bitte prüfen und anschließend selbst speichern.` : '');
      rememberAssistantTurn('assistant', replyText);
      if (!applied.navigated) addEntityResults(data.results || []);
'''
    if new_reply not in text:
        if old_reply not in text:
            raise RuntimeError("Stateful KI frontend reply anchor changed")
        text = text.replace(old_reply, new_reply, 1)

    if MARKER not in text:
        marker_anchor = "// KAYI AI CONTROL + SEARCH FIX 2026-08-11"
        if marker_anchor in text:
            text = text.replace(marker_anchor, marker_anchor + "\n// " + MARKER, 1)
        else:
            text = "// " + MARKER + "\n" + text
    write(rel, text)


def patch_styles() -> None:
    rel = "static/css/kayi-next.css"
    text = read(rel)
    if ".nx-assistant-results" not in text:
        text += r'''

/* KAYI STATEFUL ENTITY CHAT 2026-08-11 */
.nx-assistant-results {
  display: grid;
  gap: 8px;
  margin: 4px 0 12px;
}
.nx-assistant-result {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 2px 9px;
  align-items: center;
  padding: 10px 12px;
  border: 1px solid var(--nx-line, #d9d7d2);
  border-radius: 12px;
  background: var(--nx-card, #fff);
  color: inherit;
  text-decoration: none;
}
.nx-assistant-result:hover { border-color: var(--nx-accent, #12bfa6); transform: translateY(-1px); }
.nx-assistant-result-kind {
  grid-row: 1 / span 2;
  align-self: center;
  padding: 4px 7px;
  border-radius: 999px;
  background: rgba(18,191,166,.12);
  font-size: 12px;
  font-weight: 800;
}
.nx-assistant-result b { font-size: 14px; line-height: 1.25; }
.nx-assistant-result small { font-size: 12.5px; color: var(--nx-muted, #6f747a); line-height: 1.35; }
'''
    write(rel, text)


def install_tests() -> None:
    rel = "tests/test_ai_stateful_entity_chat.py"
    test = r'''from pathlib import Path

from django.test import SimpleTestCase

from erp import assistant_views


class AIStatefulEntityChatRegressionTests(SimpleTestCase):
    def test_client_alias_is_a_customer_route_and_not_a_search_term(self):
        self.assertEqual(assistant_views._requested_entity_route("client"), "customers")
        self.assertEqual(assistant_views._requested_entity_route("find ashkan client"), "customers")
        self.assertEqual(assistant_views._search_terms("find ashkan client"), ["ashkan"])

    def test_project_and_employee_aliases_are_normalized(self):
        self.assertEqual(assistant_views._requested_entity_route("project"), "projects")
        self.assertEqual(assistant_views._requested_entity_route("Mitarbeiter"), "employees")
        self.assertEqual(assistant_views._requested_entity_route("Termin"), "appointments")

    def test_short_history_is_compacted_for_followup_reasoning(self):
        payload = {"history": [
            {"role": "user", "content": "find ashkan"},
            {"role": "assistant", "content": "Ich habe Ashkan Asaid als Kunden gefunden."},
            {"role": "tool", "content": "ignore"},
        ]}
        history = assistant_views._compact_assistant_history(payload)
        self.assertEqual([item["role"] for item in history], ["user", "assistant"])
        self.assertIn("Ashkan Asaid", history[-1]["content"])

    def test_frontend_persists_history_and_renders_real_result_links(self):
        root = Path(__file__).resolve().parents[1]
        js = (root / "static/js/kayi-next.js").read_text(encoding="utf-8")
        backend = (root / "erp/assistant_views.py").read_text(encoding="utf-8")
        css = (root / "static/css/kayi-next.css").read_text(encoding="utf-8")
        base = (root / "templates/rebuild/base.html").read_text(encoding="utf-8")
        for marker in ("kayi-assistant-history-v3", "addEntityResults", "history:priorHistory", "nx-assistant-result"):
            self.assertIn(marker, js)
        for marker in ("_resolve_entity_search", "_direct_entity_response", "conversation_history", "entity_focus"):
            self.assertIn(marker, backend)
        self.assertIn("KAYI STATEFUL ENTITY CHAT 2026-08-11", css)
        self.assertIn("20260811-3", base)
        self.assertNotIn("Keine irreversible Aktion wurde automatisch ausgeführt.", js)
'''
    write(rel, test)


def bump_cache() -> None:
    rel = "templates/rebuild/base.html"
    text = read(rel)
    updated = re.sub(r"(kayi-next\.(?:css|js)'\s*%\}\?v=)[^\"'\s<]+", rf"\g<1>{VERSION}", text)
    if updated == text and VERSION not in text:
        raise RuntimeError("Could not bump stateful KI asset cache version")
    write(rel, updated)


def guard() -> None:
    checks = {
        "erp/assistant_views.py": [MARKER, "_requested_entity_route", "_resolve_entity_search", "_direct_entity_response", "conversation_history", "client", "clients"],
        "static/js/kayi-next.js": [MARKER, "kayi-assistant-history-v3", "addEntityResults", "history:priorHistory"],
        "static/css/kayi-next.css": [MARKER, ".nx-assistant-results", ".nx-assistant-result"],
        "templates/rebuild/base.html": [VERSION],
        "tests/test_ai_stateful_entity_chat.py": ["test_client_alias_is_a_customer_route_and_not_a_search_term"],
    }
    missing = []
    for rel, markers in checks.items():
        text = read(rel)
        for marker in markers:
            if marker not in text:
                missing.append(f"{rel}: {marker}")
    if missing:
        raise RuntimeError("Stateful KI final guard failed: " + "; ".join(missing))


def main() -> None:
    patch_backend()
    patch_frontend()
    patch_styles()
    install_tests()
    bump_cache()
    guard()
    print("KAYI KI stateful entity memory, deterministic follow-ups and clickable real results installed and verified.")


if __name__ == "__main__":
    main()
