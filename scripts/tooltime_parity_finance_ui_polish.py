from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"ToolTime-UI: Datei fehlt: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel, text):
    (ROOT / rel).write_text(text, encoding="utf-8")


def patch_template():
    rel = "templates/rebuild/document_editor.html"
    text = read(rel)
    old = '<button type="button" class="tt-menu" data-group-menu>•••</button>'
    new = '''<details class="tt-group-actions"><summary aria-label="Leistungsgruppe bearbeiten">•••</summary><div><button type="button" data-group-action="rename">Titel anpassen</button><button type="button" data-group-action="copy">Leistungsgruppe kopieren</button><button type="button" data-group-action="margin">Margen anpassen</button><button type="button" data-group-action="up">Nach oben</button><button type="button" data-group-action="down">Nach unten</button><button type="button" data-group-action="delete" class="danger">Leistungsgruppe löschen</button></div></details>'''
    if old not in text:
        raise RuntimeError("ToolTime-UI: Gruppenmenü-Anker fehlt.")
    text = text.replace(old, new)
    margin_modal = '''<div class="tt-modal" data-margin-modal hidden><form class="tt-modal-card" data-margin-form><header><h2>Margen anpassen</h2><button type="button" data-close-modal>×</button></header><p>Der neue Aufschlag überschreibt die bisherigen Aufschläge der gewählten Positionsart.</p><label>Positionsart<select class="nx-control" name="position_type"><option value="all">Alle Positionsarten</option><option value="material">Material</option><option value="labour">Lohn</option><option value="mixed">Mischposition</option><option value="other">Sonstiges</option></select></label><label>Aufschlag in %<input class="nx-control" name="markup" type="number" step="0.01" required></label><button class="nx-btn nx-btn-accent" type="submit">Aufschläge übernehmen</button></form></div>'''
    anchor = '<div class="tt-modal" data-customer-modal hidden>'
    if margin_modal not in text:
        text = text.replace(anchor, margin_modal + anchor, 1)
    write(rel, text)


def patch_js():
    rel = "static/js/tooltime-parity-finance.js"
    text = read(rel)
    old = "if(e.target.closest('[data-group-menu]')){const g=groupOf(e.target);const action=prompt('Aktion: umbenennen, kopieren, marge, hoch, runter, löschen');if(!action)return;const a=action.toLowerCase();if(a.startsWith('umb')){const title=prompt('Neuer Titel',g.querySelector('.tt-group-title').value);if(title)g.querySelector('.tt-group-title').value=title}else if(a.startsWith('kop')){g.after(g.cloneNode(true))}else if(a.startsWith('marg')){const value=prompt('Neuer Aufschlag in % für diese Leistungsgruppe','20');if(value!==null)g.querySelectorAll('[name=item_markup_percent]').forEach(i=>i.value=value)}else if(a==='hoch'&&g.previousElementSibling){g.parentNode.insertBefore(g,g.previousElementSibling)}else if(a==='runter'&&g.nextElementSibling){g.parentNode.insertBefore(g.nextElementSibling,g)}else if(a.startsWith('lö')||a.startsWith('lo')){if(confirm('Leistungsgruppe wirklich löschen?'))g.remove()}syncGroups();calc();return}"
    new = "if(e.target.closest('[data-group-action]')){const button=e.target.closest('[data-group-action]'),g=groupOf(button),a=button.dataset.groupAction;button.closest('details')?.removeAttribute('open');if(a==='rename'){const input=g.querySelector('.tt-group-title');input.focus();input.select()}else if(a==='copy'){const clone=g.cloneNode(true);g.after(clone)}else if(a==='margin'){window.ttMarginScope=g;modal('[data-margin-modal]',true)}else if(a==='up'&&g.previousElementSibling){g.parentNode.insertBefore(g,g.previousElementSibling)}else if(a==='down'&&g.nextElementSibling){g.parentNode.insertBefore(g.nextElementSibling,g)}else if(a==='delete'&&confirm('Leistungsgruppe wirklich löschen?')){g.remove()}syncGroups();calc();return}"
    if old not in text:
        raise RuntimeError("ToolTime-UI: altes Gruppenmenü-JS fehlt.")
    text = text.replace(old, new, 1)
    old_global = "if(e.target.closest('[data-adjust-markups]')){const val=prompt('Neuer Aufschlag in % für alle Positionen','20');if(val!==null){form.querySelectorAll('[name=item_markup_percent]').forEach(i=>i.value=val);calc()}return}"
    new_global = "if(e.target.closest('[data-adjust-markups]')){window.ttMarginScope=form;modal('[data-margin-modal]',true);return}"
    if old_global not in text:
        raise RuntimeError("ToolTime-UI: globaler Margen-Anker fehlt.")
    text = text.replace(old_global, new_global, 1)
    insert_anchor = "  const endpoint=form.dataset.articleSearchUrl;let searchTimer=null;"
    insert = r'''  document.querySelector('[data-margin-form]')?.addEventListener('submit',e=>{e.preventDefault();const scope=window.ttMarginScope||form,type=e.target.elements.position_type.value,markup=e.target.elements.markup.value;scope.querySelectorAll('[data-position]').forEach(row=>{if(type==='all'||row.querySelector('[name=item_type]')?.value===type){row.querySelector('[name=item_markup_percent]').value=markup}});modal('[data-margin-modal]',false);e.target.reset();calc()});
  let draggedGroup=null;
  document.addEventListener('dragstart',e=>{const grip=e.target.closest('.tt-grip');if(grip){draggedGroup=grip.closest('[data-service-group]');e.dataTransfer.effectAllowed='move'}});
  document.addEventListener('dragover',e=>{if(draggedGroup&&e.target.closest('[data-service-group]'))e.preventDefault()});
  document.addEventListener('drop',e=>{if(!draggedGroup)return;const target=e.target.closest('[data-service-group]');if(!target||target===draggedGroup)return;e.preventDefault();const rect=target.getBoundingClientRect();target.parentNode.insertBefore(draggedGroup,e.clientY>rect.top+rect.height/2?target.nextSibling:target);draggedGroup=null;syncGroups();calc()});
'''
    if insert_anchor not in text:
        raise RuntimeError("ToolTime-UI: Artikelsuche-Anker fehlt.")
    text = text.replace(insert_anchor, insert + insert_anchor, 1)
    write(rel, text)


def patch_css():
    rel = "static/css/tooltime-parity-finance.css"
    css = read(rel)
    css += r'''
.tt-group-actions{position:relative}.tt-group-actions>summary{list-style:none;cursor:pointer;padding:6px 8px;font-weight:800}.tt-group-actions>summary::-webkit-details-marker{display:none}.tt-group-actions>div{position:absolute;right:0;top:32px;z-index:50;min-width:220px;background:#fff;border:1px solid #dfe5ec;border-radius:10px;box-shadow:0 14px 32px rgba(20,35,55,.16);padding:6px;display:grid}.tt-group-actions button{border:0;background:transparent;text-align:left;padding:9px 10px;border-radius:7px;cursor:pointer}.tt-group-actions button:hover{background:#f3f6f9}.tt-group-actions button.danger{color:#b42318}.tt-service-group.tt-dragging{opacity:.6}
'''
    write(rel, css)


def patch_tests():
    rel = "tests/test_tooltime_finance_parity_batch.py"
    text = read(rel)
    anchor = "    def test_invoice_number_has_no_forced_year_segment(self):\n"
    test = '''    def test_group_actions_are_real_controls(self):
        editor = (ROOT / "templates/rebuild/document_editor.html").read_text()
        js = (ROOT / "static/js/tooltime-parity-finance.js").read_text()
        self.assertIn('data-group-action="copy"', editor)
        self.assertIn('data-group-action="margin"', editor)
        self.assertIn('data-margin-modal', editor)
        self.assertNotIn("prompt('Aktion:", js)
        self.assertIn("draggedGroup", js)

'''
    if test not in text:
        if anchor not in text:
            raise RuntimeError("ToolTime-UI: Test-Anker fehlt.")
        text = text.replace(anchor, test + anchor, 1)
    write(rel, text)


def run():
    patch_template(); patch_js(); patch_css(); patch_tests()
    print("ToolTime-Leistungsgruppen poliert: echtes Aktionsmenü, Margen-Dialog und Drag & Drop.")


if __name__ == "__main__":
    run()
