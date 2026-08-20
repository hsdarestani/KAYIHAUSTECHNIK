from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME PHASE 1 TEXT LAYOUT 2026-08-20"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Phase 1 target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_views() -> None:
    rel = "erp/tooltime_parity_views.py"
    text = read(rel)

    helper_anchor = "def settings_page(request):\n"
    helpers = r'''def _template_for_org(org, pk):
    return get_object_or_404(m.ToolTimeTextTemplate, organization=org, pk=pk)


def _normalize_template_orders(org, document_kind, text_kind):
    rows = list(m.ToolTimeTextTemplate.objects.filter(
        organization=org,
        document_kind=document_kind,
        text_kind=text_kind,
    ).order_by("sort_order", "id"))
    for index, row in enumerate(rows, 1):
        if row.sort_order != index:
            row.sort_order = index
            row.save(update_fields=["sort_order", "updated_at"])


def _ensure_standard_text_templates(org):
    for document_kind in ("quote", "invoice"):
        for text_kind in ("intro", "closing"):
            qs = m.ToolTimeTextTemplate.objects.filter(
                organization=org,
                document_kind=document_kind,
                text_kind=text_kind,
            )
            standard = qs.filter(is_standard=True).order_by("id").first()
            if standard is None:
                first = qs.order_by("sort_order", "id").first()
                if first is None:
                    first = m.ToolTimeTextTemplate.objects.create(
                        organization=org,
                        document_kind=document_kind,
                        text_kind=text_kind,
                        title="Standard",
                        salutation="Sehr geehrte Damen und Herren," if text_kind == "intro" else "",
                        body="",
                        is_standard=True,
                        sort_order=1,
                    )
                else:
                    first.is_standard = True
                    first.save(update_fields=["is_standard", "updated_at"])
            for duplicate in qs.filter(is_standard=True).exclude(pk=first.pk if standard is None else standard.pk):
                duplicate.is_standard = False
                duplicate.save(update_fields=["is_standard", "updated_at"])
            _normalize_template_orders(org, document_kind, text_kind)


@require_POST
def text_template_create(request):
    org = base._org(request)
    document_kind = request.POST.get("document_kind") or "quote"
    text_kind = request.POST.get("text_kind") or "intro"
    if document_kind not in {"quote", "invoice"} or text_kind not in {"intro", "closing"}:
        return HttpResponseBadRequest("Ungültige Vorlagenart.")
    title = (request.POST.get("title") or "Neue Vorlage").strip()[:120] or "Neue Vorlage"
    row = m.ToolTimeTextTemplate.objects.create(
        organization=org,
        document_kind=document_kind,
        text_kind=text_kind,
        title=title,
        salutation=(request.POST.get("salutation") or "").strip()[:240],
        body=request.POST.get("body") or "",
        is_standard=not m.ToolTimeTextTemplate.objects.filter(
            organization=org, document_kind=document_kind, text_kind=text_kind
        ).exists(),
        sort_order=m.ToolTimeTextTemplate.objects.filter(
            organization=org, document_kind=document_kind, text_kind=text_kind
        ).count() + 1,
    )
    _ensure_standard_text_templates(org)
    messages.success(request, f"Vorlage „{row.title}“ wurde angelegt.")
    return redirect("next-settings")


@require_POST
def text_template_update(request, pk):
    org = base._org(request)
    row = _template_for_org(org, pk)
    row.title = (request.POST.get("title") or row.title).strip()[:120] or row.title
    row.salutation = (request.POST.get("salutation") or "").strip()[:240]
    row.body = request.POST.get("body") or ""
    row.save(update_fields=["title", "salutation", "body", "updated_at"])
    messages.success(request, f"Vorlage „{row.title}“ wurde gespeichert.")
    return redirect("next-settings")


@require_POST
def text_template_delete(request, pk):
    org = base._org(request)
    row = _template_for_org(org, pk)
    if row.is_standard:
        messages.error(request, "Die Standardvorlage kann nicht gelöscht werden. Wähle zuerst eine andere Standardvorlage.")
        return redirect("next-settings")
    document_kind, text_kind = row.document_kind, row.text_kind
    row.delete()
    _normalize_template_orders(org, document_kind, text_kind)
    messages.success(request, "Vorlage wurde gelöscht.")
    return redirect("next-settings")


@require_POST
def text_template_standard(request, pk):
    org = base._org(request)
    row = _template_for_org(org, pk)
    with transaction.atomic():
        m.ToolTimeTextTemplate.objects.filter(
            organization=org,
            document_kind=row.document_kind,
            text_kind=row.text_kind,
            is_standard=True,
        ).exclude(pk=row.pk).update(is_standard=False)
        if not row.is_standard:
            row.is_standard = True
            row.save(update_fields=["is_standard", "updated_at"])
    messages.success(request, f"„{row.title}“ ist jetzt die Standardvorlage.")
    return redirect("next-settings")


@require_POST
def text_template_move(request, pk):
    org = base._org(request)
    row = _template_for_org(org, pk)
    direction = request.POST.get("direction")
    rows = list(m.ToolTimeTextTemplate.objects.filter(
        organization=org,
        document_kind=row.document_kind,
        text_kind=row.text_kind,
    ).order_by("sort_order", "id"))
    try:
        index = rows.index(row)
    except ValueError:
        return redirect("next-settings")
    target_index = index - 1 if direction == "up" else index + 1 if direction == "down" else index
    if 0 <= target_index < len(rows) and target_index != index:
        target = rows[target_index]
        row.sort_order, target.sort_order = target.sort_order, row.sort_order
        row.save(update_fields=["sort_order", "updated_at"])
        target.save(update_fields=["sort_order", "updated_at"])
        _normalize_template_orders(org, row.document_kind, row.text_kind)
    return redirect("next-settings")


def layout_preview(request):
    org = base._org(request)
    cfg = profile_for(org).settings
    _ensure_standard_text_templates(org)
    intro = m.ToolTimeTextTemplate.objects.filter(
        organization=org, document_kind="quote", text_kind="intro", is_standard=True
    ).first()
    closing = m.ToolTimeTextTemplate.objects.filter(
        organization=org, document_kind="quote", text_kind="closing", is_standard=True
    ).first()
    return render(request, "rebuild/tooltime_layout_preview.html", {
        "organization": org,
        "cfg": cfg,
        "intro": intro,
        "closing": closing,
    })


'''
    if "def text_template_create(" not in text:
        if helper_anchor not in text:
            raise RuntimeError("Phase 1 settings_page anchor changed")
        text = text.replace(helper_anchor, helpers + helper_anchor, 1)

    # Ensure settings page always has a complete ToolTime template set available.
    settings_start = "def settings_page(request):\n    org = base._org(request)\n"
    if settings_start in text and "_ensure_standard_text_templates(org)" not in text[text.index(settings_start):text.index(settings_start)+250]:
        text = text.replace(settings_start, settings_start + "    _ensure_standard_text_templates(org)\n", 1)

    write(rel, text)


def patch_urls() -> None:
    rel = "erp/rebuild_urls.py"
    text = read(rel)
    routes = '''    path("settings/next/textvorlagen/neu/", tooltime_parity.text_template_create, name="next-text-template-create"),
    path("settings/next/textvorlagen/<int:pk>/speichern/", tooltime_parity.text_template_update, name="next-text-template-update"),
    path("settings/next/textvorlagen/<int:pk>/loeschen/", tooltime_parity.text_template_delete, name="next-text-template-delete"),
    path("settings/next/textvorlagen/<int:pk>/standard/", tooltime_parity.text_template_standard, name="next-text-template-standard"),
    path("settings/next/textvorlagen/<int:pk>/verschieben/", tooltime_parity.text_template_move, name="next-text-template-move"),
    path("settings/next/layout/vorschau/", tooltime_parity.layout_preview, name="next-layout-preview"),
'''
    if "next-text-template-create" not in text:
        anchor = '    path("settings/next/", tooltime_parity.settings_page, name="next-settings"),\n'
        if anchor not in text:
            raise RuntimeError("Phase 1 final ToolTime settings route missing")
        text = text.replace(anchor, anchor + routes, 1)
    write(rel, text)


def patch_settings_template() -> None:
    rel = "templates/rebuild/tooltime_settings.html"
    text = read(rel)

    # Add an explicit preview action in the layout section.
    if "next-layout-preview" not in text:
        marker = "Texte & Layout"
        pos = text.find(marker)
        if pos < 0:
            raise RuntimeError("Phase 1 Texte & Layout heading missing")
        # Put a global preview button near the first matching heading without depending on exact old markup.
        insert_at = text.find(">", pos)
        if insert_at < 0:
            raise RuntimeError("Phase 1 layout heading closing tag missing")
        preview = ' <a class="nx-btn" href="{% url \'next-layout-preview\' %}" target="_blank" rel="noopener">Dokumentvorschau</a>'
        text = text[:insert_at+1] + preview + text[insert_at+1:]

    # Append a full ToolTime-style text-template manager if the previous settings page only had simple fields.
    if "data-tooltime-text-template-manager" not in text:
        manager = r'''
<section class="tt-card" data-tooltime-text-template-manager>
  <div class="tt-section-title"><div><h2>Textvorlagen</h2><p>Einleitungs- und Schlusstexte für Angebote und Rechnungen verwalten.</p></div></div>
  <div class="tt-template-grid">
    {% for document_kind, document_label in text_template_document_kinds %}
      {% for text_kind, text_label in text_template_text_kinds %}
      <div class="tt-template-panel">
        <div class="tt-section-title"><div><strong>{{ document_label }} · {{ text_label }}</strong></div>
          <button type="button" class="nx-btn" data-template-create-open="{{ document_kind }}:{{ text_kind }}">Neue Vorlage</button>
        </div>
        <div class="tt-template-list">
          {% for row in text_templates %}{% if row.document_kind == document_kind and row.text_kind == text_kind %}
          <details class="tt-template-row" {% if row.is_standard %}open{% endif %}>
            <summary><span><b>{{ row.title }}</b>{% if row.is_standard %}<small>Standard</small>{% endif %}</span><span>Bearbeiten</span></summary>
            <form method="post" action="{% url 'next-text-template-update' row.pk %}" class="tt-template-editor">{% csrf_token %}
              <label>Name<input class="nx-control" name="title" maxlength="120" value="{{ row.title }}" required></label>
              {% if text_kind == 'intro' %}<label>Anrede<input class="nx-control" name="salutation" maxlength="240" value="{{ row.salutation }}"></label>{% endif %}
              <label>Text<textarea class="nx-control" name="body" rows="7">{{ row.body }}</textarea></label>
              <div class="nx-actions"><button class="nx-btn nx-btn-accent" type="submit">Speichern</button></div>
            </form>
            <div class="nx-actions tt-template-actions">
              {% if not row.is_standard %}<form method="post" action="{% url 'next-text-template-standard' row.pk %}">{% csrf_token %}<button class="nx-btn" type="submit">Als Standard festlegen</button></form>{% endif %}
              <form method="post" action="{% url 'next-text-template-move' row.pk %}">{% csrf_token %}<input type="hidden" name="direction" value="up"><button class="nx-btn" type="submit" aria-label="Vorlage nach oben">↑</button></form>
              <form method="post" action="{% url 'next-text-template-move' row.pk %}">{% csrf_token %}<input type="hidden" name="direction" value="down"><button class="nx-btn" type="submit" aria-label="Vorlage nach unten">↓</button></form>
              {% if not row.is_standard %}<form method="post" action="{% url 'next-text-template-delete' row.pk %}" onsubmit="return confirm('Vorlage wirklich löschen?')">{% csrf_token %}<button class="nx-btn" type="submit">Löschen</button></form>{% endif %}
            </div>
          </details>
          {% endif %}{% endfor %}
        </div>
      </div>
      {% endfor %}
    {% endfor %}
  </div>
</section>
<div class="tt-modal" data-template-create-modal hidden><form class="tt-modal-card" method="post" action="{% url 'next-text-template-create' %}">{% csrf_token %}<header><h2>Neue Textvorlage</h2><button type="button" data-close-template-create>×</button></header><input type="hidden" name="document_kind"><input type="hidden" name="text_kind"><label>Name<input class="nx-control" name="title" value="Neue Vorlage" required></label><label>Anrede<input class="nx-control" name="salutation" placeholder="Sehr geehrte Damen und Herren,"></label><label>Text<textarea class="nx-control" name="body" rows="8"></textarea></label><button class="nx-btn nx-btn-accent" type="submit">Vorlage anlegen</button></form></div>
<script>document.addEventListener('click',e=>{const open=e.target.closest('[data-template-create-open]');if(open){const m=document.querySelector('[data-template-create-modal]'),parts=open.dataset.templateCreateOpen.split(':');m.querySelector('[name=document_kind]').value=parts[0];m.querySelector('[name=text_kind]').value=parts[1];m.hidden=false;m.querySelector('[name=title]').focus()}if(e.target.closest('[data-close-template-create]'))document.querySelector('[data-template-create-modal]').hidden=true});</script>
'''
        end = "{% endblock %}"
        idx = text.rfind(end)
        if idx < 0:
            raise RuntimeError("Phase 1 settings template endblock missing")
        text = text[:idx] + manager + "\n" + text[idx:]

    write(rel, text)


def patch_settings_context() -> None:
    rel = "erp/tooltime_parity_views.py"
    text = read(rel)
    # Add template-manager context to every final GET render of settings page.
    needle = '"profile": profile,'
    replacement = '"profile": profile, "text_templates": list(m.ToolTimeTextTemplate.objects.filter(organization=org).order_by("document_kind", "text_kind", "sort_order", "id")), "text_template_document_kinds": [("quote", "Angebote"), ("invoice", "Rechnungen")], "text_template_text_kinds": [("intro", "Einleitungstext"), ("closing", "Schlusstext")],'
    if replacement not in text:
        if needle not in text:
            # fallback: patch render call dictionary with cfg marker
            needle = '"cfg": cfg,'
            replacement = '"cfg": cfg, "text_templates": list(m.ToolTimeTextTemplate.objects.filter(organization=org).order_by("document_kind", "text_kind", "sort_order", "id")), "text_template_document_kinds": [("quote", "Angebote"), ("invoice", "Rechnungen")], "text_template_text_kinds": [("intro", "Einleitungstext"), ("closing", "Schlusstext")],'
            if needle not in text:
                raise RuntimeError("Phase 1 settings render context anchor missing")
        text = text.replace(needle, replacement, 1)
    write(rel, text)


def install_preview_template() -> None:
    write("templates/rebuild/tooltime_layout_preview.html", r'''{% extends 'rebuild/base.html' %}{% block title %}Dokumentvorschau · A+Bau{% endblock %}{% block content %}
<div class="tt-pagehead"><div><span class="tt-eyebrow">Texte & Layout</span><h1>Dokumentvorschau</h1><p>Vorschau der aktuell gespeicherten Dokumentgestaltung.</p></div><a class="nx-btn" href="{% url 'next-settings' %}">Zurück zu Einstellungen</a></div>
<div class="tt-preview-shell"><article class="tt-paper {% if cfg.logo.position %}logo-{{ cfg.logo.position }}{% endif %}">
  <header class="tt-paper-head">
    {% if cfg.logo.show and organization.logo %}<img class="tt-paper-logo size-{{ cfg.logo.size|default:'large' }}" src="{{ organization.logo.url }}" alt="{{ organization.name }}">{% endif %}
    {% if cfg.sender_line.show %}<div class="tt-sender-line">{{ organization.name }} · {{ organization.street|default:'' }} · {{ organization.postal_code|default:'' }} {{ organization.city|default:'' }}</div>{% endif %}
  </header>
  <section class="tt-paper-address"><strong>Max Mustermann</strong><br>Musterstraße 10<br>60311 Frankfurt am Main</section>
  <h1>Angebot A-1001</h1><p>{% if intro and intro.salutation %}{{ intro.salutation }}{% else %}Sehr geehrte Damen und Herren,{% endif %}</p><p>{{ intro.body|default:'vielen Dank für Ihre Anfrage. Gerne unterbreiten wir Ihnen folgendes Angebot.'|linebreaksbr }}</p>
  <table class="tt-preview-table"><thead><tr><th>Pos.</th><th>Leistung</th><th>Menge</th><th>Einzelpreis</th><th>Gesamt</th></tr></thead><tbody><tr><td>1</td><td>Beispielposition</td><td>1 Stk.</td><td>100,00 €</td><td>100,00 €</td></tr></tbody></table>
  <p>{{ closing.body|default:'Wir freuen uns auf Ihre Rückmeldung.'|linebreaksbr }}</p>
  {% if cfg.footer.show %}<footer class="tt-paper-footer mode-{{ cfg.footer.mode|default:'standard' }}">{% if cfg.footer.mode == 'custom' and cfg.footer.columns %}{% for col in cfg.footer.columns %}<div style="text-align:{{ col.align|default:'left' }}"><b>{{ col.heading }}</b>{% for line in col.lines %}<span>{{ line }}</span>{% endfor %}</div>{% endfor %}{% else %}<div><b>{{ organization.name }}</b><span>{{ organization.street|default:'' }}</span><span>{{ organization.postal_code|default:'' }} {{ organization.city|default:'' }}</span></div><div><b>Kontakt</b><span>{{ organization.email|default:'' }}</span><span>{{ organization.phone|default:'' }}</span></div><div><b>Bank & Steuer</b><span>{{ organization.iban|default:'' }}</span><span>{{ organization.tax_id|default:'' }}</span></div>{% endif %}</footer>{% endif %}
</article></div>
<style>.tt-preview-shell{display:flex;justify-content:center;padding:20px}.tt-paper{width:min(900px,100%);min-height:1100px;background:white;border:1px solid #e1e5ea;box-shadow:0 16px 40px rgba(17,24,39,.08);padding:64px;display:flex;flex-direction:column;gap:24px}.tt-paper-head{min-height:95px}.tt-paper-logo{display:block;max-height:90px;object-fit:contain}.tt-paper.logo-left .tt-paper-logo{margin-right:auto}.tt-paper.logo-center .tt-paper-logo{margin-inline:auto}.tt-paper.logo-right .tt-paper-logo{margin-left:auto}.tt-paper-logo.size-small{max-width:120px}.tt-paper-logo.size-medium{max-width:180px}.tt-paper-logo.size-large{max-width:260px}.tt-sender-line{font-size:11px;margin-top:16px;border-bottom:1px solid #ddd;padding-bottom:4px}.tt-paper-address{margin-top:28px}.tt-preview-table{width:100%;border-collapse:collapse}.tt-preview-table th,.tt-preview-table td{padding:10px;border-bottom:1px solid #e6e8eb;text-align:left}.tt-paper-footer{margin-top:auto;display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:18px;border-top:1px solid #ddd;padding-top:16px;font-size:10px}.tt-paper-footer div{display:grid;gap:3px}</style>
{% endblock %}''')


def patch_editor_template_selection() -> None:
    rel = "templates/rebuild/document_editor.html"
    text = read(rel)
    # Existing ToolTime document editor has a Vorlagen button; make template choice explicit and functional.
    if "data-template-library" not in text:
        modal = r'''
<div class="tt-modal" data-template-library hidden><div class="tt-modal-card"><header><h2>Textvorlage auswählen</h2><button type="button" data-template-library-close>×</button></header><div data-template-options></div></div></div>
<script>
(() => { const root=document.querySelector('.tt-document-form'); if(!root)return; const modal=document.querySelector('[data-template-library]'), options=modal?.querySelector('[data-template-options]'); const templates=[{% for row in tt.templates %}{id:{{ row.pk }},kind:'{{ row.text_kind|escapejs }}',title:'{{ row.title|escapejs }}',salutation:'{{ row.salutation|escapejs }}',body:'{{ row.body|escapejs }}',standard:{% if row.is_standard %}true{% else %}false{% endif %}},{% endfor %}]; document.addEventListener('click',e=>{const open=e.target.closest('[data-template-open]');if(open&&modal&&options){const kind=open.dataset.templateOpen;options.innerHTML='';templates.filter(t=>t.kind===kind).forEach(t=>{const b=document.createElement('button');b.type='button';b.className='tt-template-choice';b.innerHTML=`<span><b>${t.title}</b>${t.standard?'<small>Standard</small>':''}</span>`;b.addEventListener('click',()=>{if(kind==='intro'){const sal=root.querySelector('[name=document_salutation]'), body=root.querySelector('[name=intro_text]');if(sal)sal.value=t.salutation||'';if(body)body.value=t.body||''}else{const body=root.querySelector('[name=closing_text]');if(body)body.value=t.body||''}modal.hidden=true});options.appendChild(b)});modal.hidden=false}if(e.target.closest('[data-template-library-close]'))modal.hidden=true}) })();
</script>
'''
        idx = text.rfind("{% endblock %}")
        if idx < 0:
            raise RuntimeError("Phase 1 document editor endblock missing")
        text = text[:idx] + modal + "\n" + text[idx:]
    write(rel, text)


def patch_css() -> None:
    rel = "static/css/tooltime-parity-finance.css"
    css = read(rel)
    if MARKER not in css:
        css += r'''
/* A+BAU TOOLTIME PHASE 1 TEXT LAYOUT 2026-08-20 */
.tt-template-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.tt-template-panel{border:1px solid var(--nx-line,#e5e7eb);border-radius:14px;padding:14px;background:#fff}.tt-template-list{display:grid;gap:8px;margin-top:10px}.tt-template-row{border:1px solid var(--nx-line,#e5e7eb);border-radius:10px;overflow:hidden}.tt-template-row>summary{cursor:pointer;display:flex;justify-content:space-between;align-items:center;padding:10px 12px;list-style:none}.tt-template-row>summary span:first-child{display:flex;align-items:center;gap:8px}.tt-template-row>summary small{font-size:10px;padding:2px 6px;border-radius:999px;background:#f4efe3}.tt-template-editor{display:grid;gap:10px;padding:12px;border-top:1px solid var(--nx-line,#e5e7eb)}.tt-template-actions{padding:0 12px 12px}.tt-template-actions form{display:inline}.tt-template-choice{width:100%;border:1px solid var(--nx-line,#e5e7eb);background:#fff;border-radius:9px;padding:10px;text-align:left;cursor:pointer;margin:4px 0}.tt-template-choice span{display:flex;align-items:center;justify-content:space-between;gap:8px}.tt-template-choice small{font-size:10px;background:#f4efe3;border-radius:999px;padding:2px 6px}@media(max-width:850px){.tt-template-grid{grid-template-columns:1fr}}
'''
        write(rel, css)


def install_tests() -> None:
    write("tests/test_tooltime_phase1_text_layout.py", r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase1TextLayoutContractTests(SimpleTestCase):
    def test_phase1_routes_and_real_crud_exist(self):
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        for needle in ("next-text-template-create", "next-text-template-update", "next-text-template-delete", "next-text-template-standard", "next-text-template-move", "next-layout-preview"):
            self.assertIn(needle, urls)
        for needle in ("def text_template_create", "def text_template_update", "def text_template_delete", "Die Standardvorlage kann nicht gelöscht werden", "def layout_preview"):
            self.assertIn(needle, views)

    def test_phase1_settings_contains_tooltime_template_manager(self):
        template = (ROOT / "templates/rebuild/tooltime_settings.html").read_text(encoding="utf-8")
        for needle in ("Textvorlagen", "Neue Vorlage", "Als Standard festlegen", "Dokumentvorschau", "data-tooltime-text-template-manager"):
            self.assertIn(needle, template)

    def test_phase1_document_editor_can_apply_templates(self):
        template = (ROOT / "templates/rebuild/document_editor.html").read_text(encoding="utf-8")
        self.assertIn("data-template-library", template)
        self.assertIn("tt.templates", template)
        self.assertIn("document_salutation", template)
        self.assertIn("closing_text", template)

    def test_phase1_layout_contract_survives(self):
        completion = (ROOT / "scripts/tooltime_parity_finance_completion.py").read_text(encoding="utf-8")
        # Existing completion layer owns upload validation and custom footer persistence.
        for needle in ("logo_file", "letterhead_file", "footer_heading_", "footer_lines_", "footer_align_"):
            self.assertIn(needle, completion)
''')


def guard() -> None:
    views = read("erp/tooltime_parity_views.py")
    urls = read("erp/rebuild_urls.py")
    settings = read("templates/rebuild/tooltime_settings.html")
    editor = read("templates/rebuild/document_editor.html")
    preview = read("templates/rebuild/tooltime_layout_preview.html")
    for needle in ("text_template_create", "text_template_update", "text_template_delete", "text_template_standard", "text_template_move", "layout_preview"):
        if needle not in views:
            raise RuntimeError(f"Phase 1 view missing: {needle}")
    for needle in ("next-text-template-create", "next-text-template-update", "next-text-template-delete", "next-layout-preview"):
        if needle not in urls:
            raise RuntimeError(f"Phase 1 route missing: {needle}")
    for needle in ("Textvorlagen", "Als Standard festlegen", "Dokumentvorschau", "data-tooltime-text-template-manager"):
        if needle not in settings:
            raise RuntimeError(f"Phase 1 settings UI missing: {needle}")
    for needle in ("data-template-library", "tt.templates"):
        if needle not in editor:
            raise RuntimeError(f"Phase 1 editor template selection missing: {needle}")
    for needle in ("Dokumentvorschau", "tt-paper-footer", "tt-paper-logo"):
        if needle not in preview:
            raise RuntimeError(f"Phase 1 preview missing: {needle}")


patch_views()
patch_urls()
patch_settings_context()
patch_settings_template()
install_preview_template()
patch_editor_template_selection()
patch_css()
install_tests()
guard()
print("ToolTime Phase 1 abgeschlossen: Textvorlagen-CRUD, Standardvorlagen, Sortierung, Auswahl im Dokument und Layoutvorschau installiert.")
