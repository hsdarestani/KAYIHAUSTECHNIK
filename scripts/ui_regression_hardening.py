from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "KAYI UI regression hardening 20260810"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Missing UI hardening target: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    (ROOT / rel).write_text(text, encoding="utf-8")


def replace_once(rel: str, old: str, new: str) -> None:
    text = read(rel)
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one UI hardening fragment in {rel}, found {count}")
    write(rel, text.replace(old, new, 1))


# 1) Every KAYI Next model form gets German labels. Checkboxes are deliberately
# excluded from the generic full-width input class so they stay compact.
views_path = "erp/rebuild_views.py"
views = read(views_path)
labels_block = '''\nGERMAN_FIELD_LABELS = {\n    "type": "Typ", "company": "Firma", "salutation": "Anrede", "first_name": "Vorname",\n    "last_name": "Nachname", "email": "E-Mail", "phone": "Telefon", "mobile": "Mobil",\n    "street": "Straße", "postal_code": "PLZ", "city": "Ort", "country": "Land",\n    "vat_id": "USt-IdNr.", "notes": "Notizen", "title": "Titel", "customer": "Kunde",\n    "object_location": "Objekt / Einsatzort", "description": "Beschreibung", "priority": "Priorität",\n    "manager": "Projektleitung", "members": "Team", "starts_at": "Beginn", "ends_at": "Ende",\n    "all_day": "Ganztägig", "location": "Einsatzort", "project": "Projekt", "attendees": "Mitarbeiter",\n    "issue_date": "Ausstellungsdatum", "valid_until": "Gültig bis", "intro_text": "Einleitungstext",\n    "outro_text": "Schlusstext", "discount_percent": "Rabatt (%)", "quote": "Angebot",\n    "due_date": "Fällig am", "service_date": "Leistungsdatum", "status": "Status",\n    "assigned_to": "Zugewiesen an", "due_at": "Fällig am", "supplier": "Lieferant",\n    "amount_net": "Netto-Betrag", "tax_rate": "MwSt. (%)", "expense_date": "Belegdatum",\n    "category": "Kategorie", "paid": "Bezahlt", "document": "Beleg / Dokument",\n    "trade": "Gewerk", "hourly_cost": "Interner Stundensatz", "hourly_rate": "Verrechnungssatz",\n    "active": "Aktiv", "color": "Farbe", "name": "Name",\n}\n'''
if "GERMAN_FIELD_LABELS = {" not in views:
    anchor = "\n\nclass StyledModelForm(forms.ModelForm):\n"
    if anchor not in views:
        raise RuntimeError("StyledModelForm anchor missing")
    views = views.replace(anchor, labels_block + anchor, 1)
old_init = '''    def __init__(self, *args, **kwargs):\n        super().__init__(*args, **kwargs)\n        for field in self.fields.values():\n            css = "next-control"\n            existing = field.widget.attrs.get("class", "")\n            field.widget.attrs["class"] = f"{existing} {css}".strip()\n            if isinstance(field.widget, forms.Textarea):\n                field.widget.attrs.setdefault("rows", 4)\n'''
new_init = '''    def __init__(self, *args, **kwargs):\n        super().__init__(*args, **kwargs)\n        for name, field in self.fields.items():\n            if name in GERMAN_FIELD_LABELS:\n                field.label = GERMAN_FIELD_LABELS[name]\n            field.widget.attrs.setdefault("lang", "de")\n            existing = field.widget.attrs.get("class", "")\n            if isinstance(field.widget, forms.CheckboxInput):\n                classes = [part for part in existing.split() if part not in {"next-control", "nx-control"}]\n                classes.append("nx-checkbox-input")\n                field.widget.attrs["class"] = " ".join(dict.fromkeys(classes))\n            else:\n                field.widget.attrs["class"] = f"{existing} next-control".strip()\n            if isinstance(field.widget, forms.Textarea):\n                field.widget.attrs.setdefault("rows", 4)\n'''
if new_init not in views:
    if old_init not in views:
        raise RuntimeError("StyledModelForm implementation changed unexpectedly")
    views = views.replace(old_init, new_init, 1)
write(views_path, views)

# 2) Searchable customer selection on project creation. Enter filters/selects
# instead of unexpectedly submitting/navigating away.
project_form_path = "templates/rebuild/project_form.html"
project_form = read(project_form_path)
old_field = '''      <div class="nx-field {% if field.name == 'description' or field.name == 'members' %}nx-field-full{% endif %}"><label for="{{ field.id_for_label }}">{{ field.label }}</label>{{ field }}{{ field.errors }}{% if field.help_text %}<small class="nx-muted">{{ field.help_text }}</small>{% endif %}</div>\n'''
new_field = '''      <div class="nx-field {% if field.name == 'description' or field.name == 'members' %}nx-field-full{% endif %}"><label for="{{ field.id_for_label }}">{{ field.label }}</label>{% if field.name == 'customer' %}<input type="search" class="nx-control nx-select-search" data-select-search="{{ field.id_for_label }}" placeholder="Kunde suchen …" autocomplete="off"><small class="nx-select-search-status" data-select-search-status>Tippen, um die Kundenliste zu filtern.</small>{% endif %}{{ field }}{{ field.errors }}{% if field.help_text %}<small class="nx-muted">{{ field.help_text }}</small>{% endif %}</div>\n'''
if new_field not in project_form:
    if old_field not in project_form:
        raise RuntimeError("Project form field loop changed unexpectedly")
    project_form = project_form.replace(old_field, new_field, 1)
write(project_form_path, project_form)

# 3) Project documents: whole row opens the file, while explicit Open and Download
# actions remain available and do not interfere with row navigation.
project_detail_path = "templates/rebuild/project_detail.html"
project_detail = read(project_detail_path)
old_docs = '''{% for document in documents %}<tr><td><strong>{{ document.title }}</strong></td><td><span class="nx-badge">{{ document.get_category_display }}</span></td><td>{{ document.created_at|date:'d.m.Y H:i' }}</td><td>{% if document.file %}<a class="nx-btn nx-btn-ghost" href="{{ document.file.url }}" target="_blank">Öffnen →</a>{% endif %}</td></tr>{% empty %}'''
new_docs = '''{% for document in documents %}<tr{% if document.file %} data-row-href="{{ document.file.url }}"{% endif %}><td><strong>{{ document.title }}</strong></td><td><span class="nx-badge">{{ document.get_category_display }}</span></td><td>{{ document.created_at|date:'d.m.Y H:i' }}</td><td>{% if document.file %}<div class="nx-actions"><a class="nx-btn nx-btn-ghost" href="{{ document.file.url }}" target="_blank" rel="noopener">Öffnen →</a><a class="nx-btn nx-btn-ghost" href="{{ document.file.url }}" download>Herunterladen ↓</a></div>{% endif %}</td></tr>{% empty %}'''
if new_docs not in project_detail:
    if old_docs not in project_detail:
        raise RuntimeError("Project document table changed unexpectedly")
    project_detail = project_detail.replace(old_docs, new_docs, 1)
write(project_detail_path, project_detail)

# 4) Visual contract. This intentionally applies to every KAYI Next checkbox,
# including paid/active/all-day fields in operational forms.
css_path = "static/css/kayi-next.css"
css = read(css_path)
css_patch = r'''\n/* KAYI UI regression hardening 20260810 */\n.nx-field:has(.nx-checkbox-input){grid-template-columns:minmax(0,1fr) auto;align-items:center;column-gap:14px;padding:11px 13px;border:1px solid var(--nx-line);border-radius:13px;background:#fffefa;min-height:48px}\n.nx-field:has(.nx-checkbox-input)>label{margin:0;font-size:12px}\n.nx-checkbox-input{appearance:auto!important;-webkit-appearance:checkbox!important;width:20px!important;height:20px!important;min-width:20px!important;min-height:20px!important;max-width:20px!important;margin:0!important;padding:0!important;border:0!important;border-radius:5px;accent-color:var(--nx-accent);cursor:pointer;box-shadow:none!important;justify-self:end}\n.nx-select-search{margin-bottom:2px}.nx-select-search-status{color:var(--nx-muted);font-size:10px;margin-top:-3px}.nx-selected-chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}.nx-selected-chip{display:inline-flex;align-items:center;padding:5px 8px;border-radius:999px;background:#e8fff8;color:#175548;font-size:10px;font-weight:800;border:1px solid rgba(47,214,181,.28)}\n.nx-table tbody tr[data-row-href]{cursor:pointer}.nx-table tbody tr[data-row-href]:hover{background:#f5fffB}.nx-table tbody tr[data-row-href]:focus-within{outline:2px solid rgba(47,214,181,.32);outline-offset:-2px}\n.nx-toast-stack{position:fixed;right:22px;bottom:22px;z-index:1000;display:grid;gap:8px;max-width:min(420px,calc(100vw - 32px))}.nx-toast{background:#111418;color:#fff;border-radius:14px;padding:12px 14px;box-shadow:0 16px 44px rgba(17,20,24,.2);font-size:12px;line-height:1.45}.nx-toast b{display:block;margin-bottom:2px}\n'''
if MARKER not in css:
    css += css_patch
write(css_path, css)

# 5) Interaction contract. Bind +Position from outside its table, searchable selects,
# selected-value chips, clickable rows, and informative fallback for truly unbound
# plain buttons. Buttons with any data-* action are left to their feature modules.
js_path = "static/js/kayi-next.js"
js = read(js_path)
js_patch = r'''\n\n// KAYI UI regression hardening 20260810\n(() => {\n  const $ = (s, r=document) => r.querySelector(s);\n  const $$ = (s, r=document) => Array.from(r.querySelectorAll(s));\n  const money = (v) => Number(v || 0).toLocaleString('de-DE',{style:'currency',currency:'EUR'});\n  const esc = (v) => String(v ?? '').replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');\n  const toast = (title, text='') => {\n    let stack = $('.nx-toast-stack');\n    if (!stack) { stack=document.createElement('div'); stack.className='nx-toast-stack'; document.body.append(stack); }\n    const node=document.createElement('div'); node.className='nx-toast'; node.innerHTML=`<b>${esc(title)}</b>${text ? `<span>${esc(text)}</span>` : ''}`; stack.append(node);\n    window.setTimeout(()=>node.remove(),4800);\n  };\n\n  const recalc = (table) => {\n    let net=0, tax=0;\n    $$('tbody tr',table).forEach((row)=>{\n      const qty=parseFloat($('[name="item_quantity"]',row)?.value||0);\n      const price=parseFloat($('[name="item_price"]',row)?.value||0);\n      const rate=parseFloat($('[name="item_tax"]',row)?.value||0);\n      const line=qty*price; net+=line; tax+=line*rate/100;\n    });\n    const discount=parseFloat(document.querySelector('[name="discount_percent"]')?.value||0);\n    const factor=1-Math.max(0,Math.min(100,discount))/100; net*=factor; tax*=factor;\n    [['net',net],['tax',tax],['gross',net+tax]].forEach(([key,value])=>{const out=document.querySelector(`[data-total="${key}"]`); if(out) out.textContent=money(value);});\n  };\n  const wireRow = (row,table) => {\n    $('.nx-item-remove',row)?.addEventListener('click',()=>{row.remove();recalc(table);});\n    $$('input',row).forEach((input)=>input.addEventListener('input',()=>recalc(table)));\n  };\n  const addRow = (table, values={}) => {\n    const tbody=$('tbody',table); if(!tbody) return;\n    const row=document.createElement('tr');\n    row.innerHTML=`<td><input class="nx-control desc" name="item_description" value="${esc(values.description||'')}" placeholder="Leistung oder Material"></td><td><input class="nx-control" name="item_quantity" type="number" min="0" step="0.001" value="${esc(values.quantity ?? 1)}"></td><td><input class="nx-control" name="item_unit" value="${esc(values.unit||'Stk.')}"></td><td><input class="nx-control" name="item_price" type="number" min="0" step="0.01" value="${esc(values.price ?? 0)}"></td><td><input class="nx-control" name="item_tax" type="number" min="0" step="0.01" value="${esc(values.tax ?? 19)}"></td><td><button type="button" class="nx-item-remove" aria-label="Position entfernen">×</button></td>`;\n    wireRow(row,table); tbody.append(row); recalc(table); row.querySelector('.desc')?.focus();\n  };\n  $$('[data-add-item]').forEach((button)=>{\n    if(button.dataset.nxAddBound==='1') return;\n    const form=button.closest('form')||document; const table=$('[data-document-items]',form);\n    if(!table){ button.addEventListener('click',()=>toast('Position kann hier nicht hinzugefügt werden','Die Positionsliste wurde nicht gefunden. Bitte Seite neu laden.')); return; }\n    button.dataset.nxAddBound='1'; button.addEventListener('click',()=>addRow(table));\n  });\n\n  $$('[data-select-search]').forEach((input)=>{\n    const select=document.getElementById(input.dataset.selectSearch); if(!select) return;\n    const status=input.parentElement?.querySelector('[data-select-search-status]');\n    const options=Array.from(select.options).map(o=>({o,text:o.textContent.trim().toLocaleLowerCase('de-DE'),placeholder:!o.value}));\n    const apply=()=>{\n      const q=input.value.trim().toLocaleLowerCase('de-DE'); let matches=0, sole=null;\n      options.forEach(({o,text,placeholder})=>{ const show=placeholder||!q||text.includes(q); o.hidden=!show; if(show&&!placeholder){matches+=1;sole=o;} });\n      if(status) status.textContent=q ? `${matches} Kunde${matches===1?'':'n'} gefunden.` : 'Tippen, um die Kundenliste zu filtern.';\n      return {matches,sole};\n    };\n    input.addEventListener('input',apply);\n    input.addEventListener('keydown',(event)=>{\n      if(event.key!=='Enter') return; event.preventDefault(); const {matches,sole}=apply();\n      if(matches===1&&sole){select.value=sole.value;select.dispatchEvent(new Event('change',{bubbles:true}));toast('Kunde ausgewählt',sole.textContent.trim());}\n      else if(matches===0) toast('Kein Kunde gefunden','Suchbegriff ändern oder einen neuen Kunden anlegen.');\n      else toast('Mehrere Treffer',`${matches} Kunden passen zur Suche. Bitte einen auswählen.`);\n    });\n  });\n\n  const updateChips=(select)=>{\n    let box=select.parentElement?.querySelector('.nx-selected-chips');\n    if(!box){box=document.createElement('div');box.className='nx-selected-chips';select.insertAdjacentElement('afterend',box);}\n    const selected=Array.from(select.selectedOptions).filter(o=>o.value);\n    box.innerHTML=selected.length ? selected.map(o=>`<span class="nx-selected-chip">${esc(o.textContent.trim())}</span>`).join('') : '<span class="nx-muted" style="font-size:10px">Noch nichts ausgewählt.</span>';\n  };\n  $$('select[multiple]').forEach((select)=>{updateChips(select);select.addEventListener('change',()=>updateChips(select));});\n\n  $$('[data-row-href]').forEach((row)=>row.addEventListener('click',(event)=>{\n    if(event.target.closest('a,button,input,select,textarea,label')) return; const href=row.dataset.rowHref; if(href) window.location.href=href;\n  }));\n\n  // Never leave an unmarked visible KAYI Next button silently inert. Feature\n  // buttons carrying data-* attributes are owned by their own modules.\n  $$('.nx-content button[type="button"]:not([disabled])').forEach((button)=>{\n    if(button.classList.contains('nx-item-remove')||button.onclick) return;\n    if(Array.from(button.attributes).some(a=>a.name.startsWith('data-'))) return;\n    button.addEventListener('click',()=>toast('Aktion noch nicht verfügbar','Für diese Aktion ist hier noch keine Funktion hinterlegt. Nutze die verknüpfte Projektfunktion oder melde den konkreten Schritt an den Support.'));\n  });\n})();\n'''
if MARKER not in js:
    js += js_patch
write(js_path, js)

# 6) Browser smoke proves the exact regressions reported by QA.
smoke_path = "scripts/production_browser_smoke.py"
smoke = read(smoke_path)
smoke_anchor = '''            visible_controls = page.locator('form input:not([type="hidden"]), form select, form textarea')\n            if visible_controls.count() < 4:\n                fail("new project flow has too few controls and appears broken")\n'''
smoke_extra = '''            visible_controls = page.locator('form input:not([type="hidden"]), form select, form textarea')\n            if visible_controls.count() < 4:\n                fail("new project flow has too few controls and appears broken")\n            if page.locator('[data-select-search]').count() != 1:\n                fail("project customer selector has no search input")\n\n            page.goto(urljoin(base_url, "appointments/new/"), wait_until="domcontentloaded", timeout=30_000)\n            checkbox = page.locator('input[name="all_day"]')\n            if checkbox.count() != 1:\n                fail("appointment all-day checkbox is missing")\n            box = checkbox.bounding_box()\n            if not box or box["width"] > 30 or box["height"] > 30:\n                fail(f"appointment checkbox is oversized: {box}")\n            label = page.locator('label[for="id_all_day"]').inner_text()\n            if "Ganztägig" not in label:\n                fail("appointment checkbox label is not German")\n\n            page.goto(urljoin(base_url, "quotes/new/"), wait_until="domcontentloaded", timeout=30_000)\n            table = page.locator('[data-document-items]')\n            add = page.locator('[data-add-item]')\n            if table.count() != 1 or add.count() != 1:\n                fail("quote position editor controls are missing")\n            before = table.locator('tbody tr').count()\n            add.click()\n            after = table.locator('tbody tr').count()\n            if after != before + 1:\n                fail(f"+ Position did not add a row: {before} -> {after}")\n'''
if smoke_extra not in smoke:
    if smoke_anchor not in smoke:
        raise RuntimeError("Production browser smoke project-form anchor changed")
    smoke = smoke.replace(smoke_anchor, smoke_extra, 1)
write(smoke_path, smoke)

# 7) Fast server-side contract tests catch label/widget/template regressions before
# Chromium even starts.
test_path = ROOT / "tests" / "test_kayi_ui_regressions.py"
test_path.write_text('''from pathlib import Path\n\nfrom django.test import SimpleTestCase\n\nfrom erp.rebuild_views import AppointmentForm, QuoteForm\n\n\nclass KayiUiRegressionTests(SimpleTestCase):\n    def test_checkboxes_are_compact_and_german(self):\n        field = AppointmentForm().fields["all_day"]\n        self.assertEqual(field.label, "Ganztägig")\n        classes = field.widget.attrs.get("class", "").split()\n        self.assertIn("nx-checkbox-input", classes)\n        self.assertNotIn("next-control", classes)\n\n    def test_quote_labels_are_german(self):\n        form = QuoteForm()\n        self.assertEqual(form.fields["valid_until"].label, "Gültig bis")\n        self.assertEqual(form.fields["intro_text"].label, "Einleitungstext")\n        self.assertEqual(form.fields["discount_percent"].label, "Rabatt (%)")\n\n    def test_project_customer_search_is_rendered(self):\n        text = Path("templates/rebuild/project_form.html").read_text(encoding="utf-8")\n        self.assertIn("data-select-search", text)\n        self.assertIn("Kunde suchen", text)\n\n    def test_document_editor_and_project_download_contract(self):\n        editor = Path("templates/rebuild/document_editor.html").read_text(encoding="utf-8")\n        detail = Path("templates/rebuild/project_detail.html").read_text(encoding="utf-8")\n        self.assertIn("data-add-item", editor)\n        self.assertIn("data-row-href", detail)\n        self.assertIn("Herunterladen", detail)\n''', encoding="utf-8")

# Guard the current 3D capabilities the old QA notes called out. We do not
# reimplement them; we prove the current Room Planner still has them.
vision = read("erp/services/room_vision.py")
room_state = read("erp/services/room_planner_state.py")
planner_template = read("templates/rebuild/room_planner.html")
for needle, where in [
    ('"type": "input_image"', vision), ('"depth_m"', vision), ('"depth_m"', room_state),
    ('data-rp-drag-metrics', planner_template), ('data-rp-run-vision', planner_template),
]:
    if needle not in where:
        raise RuntimeError(f"Existing Room Planner capability regressed: {needle}")

print("KAYI UI regression hardening applied: compact checkboxes, German forms, customer search, live Position button, selection visibility, row navigation and PDF download.")
