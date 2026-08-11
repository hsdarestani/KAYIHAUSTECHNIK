from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "KAYI AI CONTROL + SEARCH FIX 2026-08-11"
VERSION = "20260811-2"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Missing KAYI target: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def replace_once(rel: str, old: str, new: str, label: str) -> None:
    text = read(rel)
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"Could not patch {label}: anchor missing in {rel}")
    write(rel, text.replace(old, new, 1))


def patch_form_widget_classes() -> None:
    old = '''        for field in self.fields.values():
            css = "next-control"
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing} {css}".strip()
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs.setdefault("rows", 4)
'''
    new = '''        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "")
            if isinstance(field.widget, forms.CheckboxInput):
                # Never apply the full-width text-control contract to a checkbox.
                field.widget.attrs["class"] = f"{existing} nx-check-input".strip()
                continue
            if isinstance(field.widget, (forms.RadioSelect, forms.CheckboxSelectMultiple)):
                field.widget.attrs["class"] = f"{existing} nx-choice-group".strip()
                continue
            field.widget.attrs["class"] = f"{existing} next-control".strip()
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs.setdefault("rows", 4)
'''
    replace_once("erp/rebuild_views.py", old, new, "checkbox widget class contract")


def patch_checkbox_layout() -> None:
    for rel in ("templates/rebuild/appointment_form.html", "templates/rebuild/ops_form.html"):
        text = read(rel)
        old = '<div class="nx-field {% if field.name == '
        if "nx-field-check" not in text:
            # Both rebuilt generic forms use the same nx-field wrapper, with a
            # different full-width condition after it. Add a widget-aware class.
            text, count = re.subn(
                r'<div class="nx-field (\{% if field\.name == )',
                r'<div class="nx-field {% if field.field.widget.input_type == \'checkbox\' %}nx-field-check{% endif %} \1',
                text,
                count=1,
            )
            if count != 1:
                raise RuntimeError(f"Could not patch checkbox field wrapper in {rel}")
            write(rel, text)

    css_rel = "static/css/kayi-next.css"
    css = read(css_rel)
    if MARKER not in css:
        css += r'''

/* KAYI AI CONTROL + SEARCH FIX 2026-08-11 */
/* Checkboxes are compact controls, not full-width text inputs. */
.nx-check-input {
  appearance: auto;
  -webkit-appearance: checkbox;
  width: 20px !important;
  min-width: 20px !important;
  max-width: 20px !important;
  height: 20px !important;
  min-height: 20px !important;
  max-height: 20px !important;
  padding: 0 !important;
  margin: 0 !important;
  flex: 0 0 20px;
  cursor: pointer;
  accent-color: var(--nx-accent);
}
.nx-field-check {
  display: flex !important;
  align-items: center;
  align-content: center;
  gap: 10px !important;
  min-height: 66px;
  padding-top: 24px;
}
.nx-field-check > label {
  order: 2;
  margin: 0 !important;
  cursor: pointer;
}
.nx-field-check > .nx-check-input { order: 1; }
.nx-field-check > .errorlist { order: 3; flex-basis: 100%; }
.nx-choice-group { width: auto !important; min-height: 0 !important; }
@media (max-width: 900px) {
  .nx-check-input { width: 22px !important; min-width: 22px !important; height: 22px !important; min-height: 22px !important; }
}
'''
        write(css_rel, css)


def patch_employee_search() -> None:
    old = '''@login_required
def employee_list(request):
    org = _org(request)
    employees = m.Employee.objects.filter(organization=org).select_related("user").order_by("-active", "last_name", "first_name")
    return render(request, "rebuild/employees.html", {"employees": employees})
'''
    new = '''@login_required
def employee_list(request):
    org = _org(request)
    query = request.GET.get("q", "").strip()
    employees = m.Employee.objects.filter(organization=org).select_related("user")
    if query:
        employees = employees.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
            | Q(phone__icontains=query)
            | Q(employee_number__icontains=query)
            | Q(trade__icontains=query)
        )
    employees = employees.order_by("-active", "last_name", "first_name")
    return render(request, "rebuild/employees.html", {"employees": employees, "query": query})
'''
    replace_once("erp/rebuild_ops.py", old, new, "employee q filtering")

    rel = "templates/rebuild/employees.html"
    text = read(rel)
    pagehead = '<div class="nx-pagehead"><div><div class="nx-kicker">Team</div><h1>Mitarbeiter</h1><p>Monteur, Büro und Projektleitung mit Preisen und Kontaktdaten verwalten.</p></div><div class="nx-actions"><a class="nx-btn nx-btn-primary" href="{% url \'next-employee-create\' %}">＋ Mitarbeiter</a></div></div>\n'
    search = pagehead + '''<form class="nx-toolbar nx-card" method="get" style="margin-bottom:16px">
  <div class="nx-search"><input name="q" value="{{ query }}" placeholder="Mitarbeiter nach Name, E-Mail, Gewerk oder Nummer suchen …" autocomplete="off"></div>
  <button class="nx-btn nx-btn-primary" type="submit">Suchen</button>
  {% if query %}<a class="nx-btn" href="{% url 'next-employees' %}">Zurücksetzen</a>{% endif %}
</form>
'''
    if "Mitarbeiter nach Name" not in text:
        if pagehead not in text:
            raise RuntimeError("Could not add employee search UI")
        text = text.replace(pagehead, search, 1)
    text = text.replace(
        '{% empty %}<div class="nx-card nx-card-pad nx-empty">Noch keine Mitarbeiter angelegt.</div>{% endfor %}',
        '{% empty %}<div class="nx-card nx-card-pad nx-empty">{% if query %}Kein Mitarbeiter für „{{ query }}“ gefunden.{% else %}Noch keine Mitarbeiter angelegt.{% endif %}</div>{% endfor %}',
    )
    write(rel, text)


def patch_assistant_backend() -> None:
    rel = "erp/assistant_views.py"
    text = read(rel)
    if "from django.db.models import Q" not in text:
        anchor = "from django.core.files.base import ContentFile\n"
        if anchor not in text:
            raise RuntimeError("Assistant import anchor changed")
        text = text.replace(anchor, anchor + "from django.db.models import Q\n", 1)

    helper_marker = "def _entity_search_context(organization, message: str)"
    if helper_marker not in text:
        anchor = "\n\n@login_required\n@require_POST\ndef assistant_command(request):\n"
        if anchor not in text:
            raise RuntimeError("Assistant command anchor changed")
        helper = r'''

_SEARCH_STOPWORDS = {
    "find", "search", "show", "open", "go", "to", "for", "the", "a", "an",
    "finde", "finden", "suche", "suchen", "zeig", "zeige", "öffne", "offne", "geh", "gehe", "nach",
    "mitarbeiter", "employee", "employees", "kunde", "kunden", "customer", "customers",
    "projekt", "projekte", "project", "projects", "termin", "termine", "appointment", "appointments",
    "aufgabe", "aufgaben", "task", "tasks",
}


def _search_terms(message: str) -> list[str]:
    raw = re.findall(r"[\w@.+-]+", message or "", flags=re.UNICODE)
    terms = []
    for token in raw:
        normalized = token.casefold().strip("._-+")
        if len(normalized) < 2 or normalized in _SEARCH_STOPWORDS:
            continue
        terms.append(token[:80])
    return terms[:6]


def _and_text_query(terms: list[str], fields: tuple[str, ...]) -> Q:
    combined = Q()
    for term in terms:
        per_term = Q()
        for field in fields:
            per_term |= Q(**{f"{field}__icontains": term})
        combined &= per_term
    return combined


def _entity_search_context(organization, message: str) -> list[dict[str, Any]]:
    """Return only real records; the KI must never invent a search result."""
    terms = _search_terms(message)
    if not terms:
        return []
    matches: list[dict[str, Any]] = []

    employees = m.Employee.objects.filter(organization=organization).filter(
        _and_text_query(terms, ("first_name", "last_name", "email", "phone", "employee_number", "trade"))
    ).order_by("-active", "last_name", "first_name")[:8]
    for item in employees:
        matches.append({
            "route": "employees", "id": item.pk,
            "label": f"{item.first_name} {item.last_name}".strip() or item.employee_number,
            "detail": " · ".join(part for part in [item.employee_number, item.email, item.trade] if part),
        })

    customers = m.Customer.objects.filter(organization=organization).filter(
        _and_text_query(terms, ("company", "first_name", "last_name", "email", "phone", "mobile", "number"))
    ).order_by("-updated_at")[:8]
    for item in customers:
        matches.append({
            "route": "customers", "id": item.pk, "label": item.display_name,
            "detail": " · ".join(part for part in [item.number, item.email, item.city] if part),
        })

    projects = m.Project.objects.filter(organization=organization, archived=False).filter(
        _and_text_query(terms, ("number", "title", "description", "customer__company", "customer__first_name", "customer__last_name"))
    ).select_related("customer").order_by("-updated_at")[:8]
    for item in projects:
        matches.append({
            "route": "projects", "id": item.pk, "label": f"{item.number} · {item.title}",
            "detail": item.customer.display_name if item.customer_id else "",
        })

    appointments = m.CalendarEvent.objects.filter(organization=organization).filter(
        _and_text_query(terms, ("title", "location", "notes", "project__title", "project__number"))
    ).order_by("-starts_at")[:6]
    for item in appointments:
        matches.append({
            "route": "appointments", "id": item.pk, "label": item.title,
            "detail": timezone.localtime(item.starts_at).strftime("%d.%m.%Y %H:%M") if item.starts_at else "",
        })

    return matches[:20]
'''
        text = text.replace(anchor, helper + anchor, 1)

    old_context = '''    context = _compact_ui_context(payload)
    schema = {
'''
    new_context = '''    organization = _org(request)
    context = _compact_ui_context(payload)
    context["now_local"] = timezone.localtime().isoformat(timespec="minutes")
    context["entity_matches"] = _entity_search_context(organization, message)
    schema = {
'''
    if new_context not in text:
        if old_context not in text:
            raise RuntimeError("Assistant context anchor changed")
        text = text.replace(old_context, new_context, 1)

    text = text.replace(
        '"enum": ["set_field", "select_option", "catalog_add", "navigate", "focus", "none"],',
        '"enum": ["set_field", "select_option", "catalog_add", "navigate", "navigate_record", "focus", "none"],',
        1,
    )

    old_prompt = '''        "Für set_field/select_option muss target exakt der Feldname aus dem Kontext sein. "
        "Bei select_option ist value der sichtbare Optionstext oder ein eindeutiger Teil davon. "
        "Bei catalog_add ist value die gesuchte Leistung bzw. das Material und count die gewünschte Anzahl passender Positionen. "
        "Bei navigate ist target einer dieser Routenschlüssel: " + ", ".join(ROUTES) + ". value ist optional der Suchtext für q=. "
        "Wenn etwas nicht sicher möglich ist, erkläre kurz warum und gib action=none zurück. Antworte auf Deutsch.\\n\\n"
'''
    new_prompt = '''        "Für set_field/select_option muss target exakt der Feldname aus dem Kontext sein. "
        "set_field darf auch Kontrollfelder bedienen: Checkboxen bekommen ausschließlich value=true oder value=false; "
        "date bekommt YYYY-MM-DD; datetime-local bekommt YYYY-MM-DDTHH:MM; time bekommt HH:MM; Zahlen bekommen eine Dezimalzahl mit Punkt. "
        "Relative Angaben wie heute, morgen oder nächsten Montag sind anhand von now_local in ein konkretes ISO-Datum umzuwandeln. "
        "Bei select_option ist value der sichtbare Optionstext oder ein eindeutiger Teil davon. "
        "Bei catalog_add ist value die gesuchte Leistung bzw. das Material und count die gewünschte Anzahl passender Positionen. "
        "Bei navigate ist target einer dieser Routenschlüssel: " + ", ".join(ROUTES) + ". value ist optional der Suchtext für q=. "
        "Bei navigate_record muss target dem route-Wert eines tatsächlich in entity_matches gelieferten Datensatzes entsprechen und value exakt dessen numerische id sein. "
        "Wenn der Nutzer einen konkreten Namen/Datensatz finden oder suchen will, verwende ausschließlich entity_matches: bei genau einem klaren Treffer navigate_record; "
        "bei mehreren plausiblen Treffern keine erfundene Auswahl; bei null Treffern action=none und klar sagen, dass nichts Passendes gefunden wurde. "
        "Niemals allein aufgrund eines Personennamens zu Mitarbeiter/Kunden navigieren, wenn entity_matches keinen solchen Treffer enthält. "
        "Wenn etwas nicht sicher möglich ist, erkläre kurz warum und gib action=none zurück. Antworte auf Deutsch.\\n\\n"
'''
    if new_prompt not in text:
        if old_prompt not in text:
            raise RuntimeError("Assistant prompt anchor changed")
        text = text.replace(old_prompt, new_prompt, 1)

    text = text.replace(
        '''            _org(request),
            input=[
''',
        '''            organization,
            input=[
''',
        1,
    )
    write(rel, text)


def patch_assistant_javascript() -> None:
    rel = "static/js/global-assistant.js"
    text = read(rel)
    helper_marker = "const normalizeControlValue = (field, rawValue)"
    if helper_marker not in text:
        anchor = "  const routes = {dashboard:'/',customers:'/customers/',projects:'/projects/',appointments:'/appointments/',tasks:'/tasks/',quotes:'/quotes/',invoices:'/invoices/',expenses:'/expenses/',time:'/time/',employees:'/employees/',settings:'/settings/next/',field:'/field/'};\n"
        if anchor not in text:
            raise RuntimeError("Global assistant routes anchor changed")
        helper = r'''
  const parseBoolean = (value) => {
    const normalized = normalize(value);
    if (['1','true','ja','yes','on','an','aktiv','checked','markiert'].includes(normalized)) return true;
    if (['0','false','nein','no','off','aus','inaktiv','unchecked','nicht markiert'].includes(normalized)) return false;
    return null;
  };

  const pad2 = (value) => String(value).padStart(2,'0');
  const normalizeControlValue = (field, rawValue) => {
    const raw = String(rawValue ?? '').trim();
    if (!raw) return '';
    if (field.type === 'date') {
      const iso = raw.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
      if (iso) return `${iso[1]}-${pad2(iso[2])}-${pad2(iso[3])}`;
      const de = raw.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})/);
      if (de) return `${de[3]}-${pad2(de[2])}-${pad2(de[1])}`;
    }
    if (field.type === 'datetime-local') {
      const iso = raw.match(/^(\d{4})-(\d{1,2})-(\d{1,2})[T\s](\d{1,2}):(\d{2})/);
      if (iso) return `${iso[1]}-${pad2(iso[2])}-${pad2(iso[3])}T${pad2(iso[4])}:${iso[5]}`;
      const de = raw.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})[ ,]+(\d{1,2}):(\d{2})/);
      if (de) return `${de[3]}-${pad2(de[2])}-${pad2(de[1])}T${pad2(de[4])}:${de[5]}`;
    }
    if (field.type === 'time') {
      const time = raw.match(/^(\d{1,2}):(\d{2})/);
      if (time) return `${pad2(time[1])}:${time[2]}`;
    }
    if (field.type === 'number' || field.type === 'range') return raw.replace(',','.');
    return raw;
  };

  const setControlValue = (field, rawValue) => {
    if (field.type === 'checkbox') {
      const parsed = parseBoolean(rawValue);
      if (parsed === null) return false;
      field.checked = parsed;
      return true;
    }
    if (field.type === 'radio') {
      const group = $$(`input[type="radio"][name="${CSS.escape(field.name)}"]`);
      const ranked = group.map((item) => ({item,score:scoreText(`${item.value} ${fieldLabel(item)}`, rawValue)})).sort((a,b)=>b.score-a.score);
      if (!ranked[0]?.score) return false;
      ranked[0].item.checked = true;
      field = ranked[0].item;
      return true;
    }
    const normalized = normalizeControlValue(field, rawValue);
    field.value = normalized;
    if (normalized && ['date','datetime-local','time','number','range'].includes(field.type) && !field.value) return false;
    return true;
  };

'''
        text = text.replace(anchor, helper + anchor, 1)

    old_set = '''        if (!field || field.tagName === 'SELECT') continue;
        if (field.type === 'checkbox') field.checked = /^(1|true|ja|yes)$/i.test(action.value || '');
        else field.value = action.value ?? '';
        field.dispatchEvent(new Event('input',{bubbles:true}));
'''
    new_set = '''        if (!field || field.tagName === 'SELECT') continue;
        if (!setControlValue(field, action.value)) continue;
        field.dispatchEvent(new Event('input',{bubbles:true}));
'''
    if new_set not in text:
        if old_set not in text:
            raise RuntimeError("Global assistant set_field anchor changed")
        text = text.replace(old_set, new_set, 1)

    old_nav = '''      } else if (action.type === 'navigate' && routes[action.target]) {
        const query = String(action.value || '').trim();
        window.location.assign(routes[action.target] + (query ? `?q=${encodeURIComponent(query)}` : ''));
        navigated = true; break;
'''
    new_nav = '''      } else if (action.type === 'navigate_record' && routes[action.target]) {
        const recordId = String(action.value || '').trim();
        if (!/^\\d+$/.test(recordId)) continue;
        window.location.assign(`${routes[action.target]}${recordId}/`);
        navigated = true; break;
      } else if (action.type === 'navigate' && routes[action.target]) {
        const query = String(action.value || '').trim();
        window.location.assign(routes[action.target] + (query ? `?q=${encodeURIComponent(query)}` : ''));
        navigated = true; break;
'''
    if new_nav not in text:
        if old_nav not in text:
            raise RuntimeError("Global assistant navigation anchor changed")
        text = text.replace(old_nav, new_nav, 1)

    if MARKER not in text:
        text = text.replace("// KAYI global KI + field handoff 20260810", "// KAYI global KI + field handoff 20260810\n// " + MARKER, 1)
    write(rel, text)


def install_regression_tests() -> None:
    test = r'''from pathlib import Path

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from erp import assistant_views
from erp.models import Employee, Organization, UserProfile


class AIControlAndSearchRegressionTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="KAYI AI control regression")
        self.user = User.objects.create_user("ai-control-admin", password="safe-test-password")
        self.user.profile.organization = self.org
        self.user.profile.role = UserProfile.Role.ADMIN
        self.user.profile.save()
        self.ashkan = Employee.objects.create(
            organization=self.org,
            employee_number="M-2026-9001",
            first_name="Ashkan",
            last_name="Test",
            email="ashkan@example.test",
            active=True,
        )
        Employee.objects.create(
            organization=self.org,
            employee_number="M-2026-9002",
            first_name="Hossein",
            last_name="Farahani",
            email="hossein@example.test",
            active=True,
        )
        self.client = Client()
        self.assertTrue(self.client.login(username="ai-control-admin", password="safe-test-password"))

    def test_employee_query_really_filters_records(self):
        response = self.client.get(reverse("next-employees"), {"q": "ashkan"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ashkan Test")
        self.assertNotContains(response, "Hossein Farahani")
        self.assertContains(response, 'value="ashkan"')

    def test_real_entity_context_finds_ashkan_and_not_unrelated_employee(self):
        matches = assistant_views._entity_search_context(self.org, "find ashkan")
        self.assertEqual([m["id"] for m in matches if m["route"] == "employees"], [self.ashkan.pk])

    def test_checkbox_and_date_controls_are_part_of_final_ai_contract(self):
        root = Path(__file__).resolve().parents[1]
        js = (root / "static/js/global-assistant.js").read_text(encoding="utf-8")
        backend = (root / "erp/assistant_views.py").read_text(encoding="utf-8")
        form = (root / "erp/rebuild_views.py").read_text(encoding="utf-8")
        css = (root / "static/css/kayi-next.css").read_text(encoding="utf-8")
        for marker in ("normalizeControlValue", "datetime-local", "parseBoolean", "navigate_record"):
            self.assertIn(marker, js)
        for marker in ("now_local", "entity_matches", "value=true", "YYYY-MM-DDTHH:MM", "navigate_record"):
            self.assertIn(marker, backend)
        self.assertIn("nx-check-input", form)
        self.assertIn("KAYI AI CONTROL + SEARCH FIX 2026-08-11", css)
'''
    write("tests/test_ai_controls_search_checkbox_fix.py", test)


def bump_cache() -> None:
    rel = "templates/rebuild/base.html"
    text = read(rel)
    text = re.sub(r"(global-assistant\.js' %\}\?v=)[^\"']+", rf"\g<1>{VERSION}", text)
    text = re.sub(r"(global-assistant\.css' %\}\?v=)[^\"']+", rf"\g<1>{VERSION}", text)
    write(rel, text)


def guard() -> None:
    checks = {
        "erp/rebuild_views.py": ["nx-check-input", "forms.CheckboxInput"],
        "templates/rebuild/appointment_form.html": ["nx-field-check"],
        "erp/rebuild_ops.py": ["query = request.GET.get(\"q\"", "first_name__icontains=query"],
        "templates/rebuild/employees.html": ["Mitarbeiter nach Name", "Kein Mitarbeiter für"],
        "erp/assistant_views.py": ["_entity_search_context", "now_local", "navigate_record", "YYYY-MM-DDTHH:MM"],
        "static/js/global-assistant.js": [MARKER, "normalizeControlValue", "setControlValue", "navigate_record"],
        "static/css/kayi-next.css": [MARKER, ".nx-check-input", ".nx-field-check"],
        "tests/test_ai_controls_search_checkbox_fix.py": ["test_employee_query_really_filters_records"],
    }
    missing = []
    for rel, markers in checks.items():
        text = read(rel)
        for marker in markers:
            if marker not in text:
                missing.append(f"{rel}: {marker}")
    if missing:
        raise RuntimeError("AI control/search final guard failed: " + "; ".join(missing))


def main() -> None:
    patch_form_widget_classes()
    patch_checkbox_layout()
    patch_employee_search()
    patch_assistant_backend()
    patch_assistant_javascript()
    install_regression_tests()
    bump_cache()
    guard()
    print("KAYI checkbox controls, typed KI field filling and real entity search installed and verified.")


if __name__ == "__main__":
    main()
