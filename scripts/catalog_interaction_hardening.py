from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML_MARKER = "data-catalog-search"
CSS_MARKER = "KAYI catalog interaction hardening 20260810"
JS_MARKER = "KAYI catalog interaction hardening 20260810"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    (ROOT / rel).write_text(text, encoding="utf-8")


# Search/filter lives inside the existing document form; no nested form and no
# accidental navigation on Enter.
template_path = "templates/rebuild/document_editor.html"
template = read(template_path)
old = '''<section class="nx-card"><div class="nx-card-head"><div><h3>Katalog</h3><p>Ein Klick fügt die Position hinzu.</p></div></div><div style="max-height:420px;overflow:auto;padding:0 12px 12px">{% for item in catalog %}<button class="nx-quick" style="width:100%;margin-bottom:7px;text-align:left" type="button" data-catalog-item data-name="{{ item.name|escape }}" data-unit="{{ item.unit|escape }}" data-price="{{ item.sales_price|stringformat:'s' }}" data-tax="{{ item.tax_rate|stringformat:'s' }}"><span class="nx-quick-icon">＋</span><span><b>{{ item.name }}</b><small>{{ item.code }} · {{ item.sales_price|floatformat:2 }} € / {{ item.unit }}</small></span></button>{% empty %}<div class="nx-empty">Noch keine Katalogpositionen.</div>{% endfor %}</div></section>'''
new = '''<section class="nx-card"><div class="nx-card-head"><div><h3>Katalog</h3><p>Suchen und mit einem Klick als Position übernehmen.</p></div></div><div class="nx-catalog-tools"><div class="nx-catalog-search-row"><input class="nx-control" type="search" data-catalog-search placeholder="Leistung, Material oder Nummer suchen …" autocomplete="off"><button class="nx-btn" type="button" data-catalog-search-button>Suchen</button></div><small class="nx-catalog-search-status" data-catalog-search-status>Alle Katalogpositionen werden angezeigt.</small><div class="nx-catalog-selected" data-catalog-selected><span class="nx-muted">Noch keine Katalogposition ausgewählt.</span></div></div><div data-catalog-list style="max-height:420px;overflow:auto;padding:0 12px 12px">{% for item in catalog %}<button class="nx-quick" style="width:100%;margin-bottom:7px;text-align:left" type="button" data-catalog-item data-name="{{ item.name|escape }}" data-code="{{ item.code|escape }}" data-unit="{{ item.unit|escape }}" data-price="{{ item.sales_price|stringformat:'s' }}" data-tax="{{ item.tax_rate|stringformat:'s' }}"><span class="nx-quick-icon">＋</span><span><b>{{ item.name }}</b><small>{{ item.code }} · {{ item.sales_price|floatformat:2 }} € / {{ item.unit }}</small></span></button>{% empty %}<div class="nx-empty">Noch keine Katalogpositionen.</div>{% endfor %}</div></section>'''
if HTML_MARKER not in template:
    if old not in template:
        raise RuntimeError("Current KAYI catalog template contract changed")
    template = template.replace(old, new, 1)
write(template_path, template)

css_path = "static/css/kayi-next.css"
css = read(css_path)
if CSS_MARKER not in css:
    css += '''
/* KAYI catalog interaction hardening 20260810 */
.nx-catalog-tools{padding:0 12px 10px;display:grid;gap:7px}.nx-catalog-search-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:7px}.nx-catalog-search-status{font-size:10px;color:var(--nx-muted)}.nx-catalog-selected{display:flex;flex-wrap:wrap;gap:5px;min-height:26px;align-items:center}.nx-catalog-selected .nx-selected-chip{max-width:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.nx-quick[data-catalog-item].is-selected{border-color:rgba(47,214,181,.65);background:#edfff9;box-shadow:0 0 0 2px rgba(47,214,181,.08)}.nx-quick[data-catalog-item][hidden]{display:none!important}@media(max-width:700px){.nx-catalog-search-row{grid-template-columns:1fr}.nx-catalog-search-row .nx-btn{width:100%}}
'''
write(css_path, css)

js_path = "static/js/kayi-next.js"
js = read(js_path)
if JS_MARKER not in js:
    js += '''

// KAYI catalog interaction hardening 20260810
(() => {
  const root=document.querySelector('[data-catalog-list]');
  const input=document.querySelector('[data-catalog-search]');
  const searchButton=document.querySelector('[data-catalog-search-button]');
  const status=document.querySelector('[data-catalog-search-status]');
  const selectedBox=document.querySelector('[data-catalog-selected]');
  const table=document.querySelector('[data-document-items]');
  if(!root||!input||!table)return;
  const normalize=(value)=>String(value||'').trim().toLocaleLowerCase('de-DE');
  const items=()=>Array.from(root.querySelectorAll('[data-catalog-item]'));
  const filter=()=>{
    const q=normalize(input.value);let visible=0;
    items().forEach((button)=>{const hay=normalize(`${button.dataset.name||''} ${button.dataset.code||''} ${button.textContent||''}`);const show=!q||hay.includes(q);button.hidden=!show;if(show)visible+=1;});
    if(status)status.textContent=q?`${visible} Treffer für „${input.value.trim()}“.`:'Alle Katalogpositionen werden angezeigt.';
  };
  input.addEventListener('input',filter);
  input.addEventListener('keydown',(event)=>{if(event.key==='Enter'){event.preventDefault();filter();const visible=items().filter(b=>!b.hidden);if(visible.length===1)visible[0].focus();}});
  searchButton?.addEventListener('click',(event)=>{event.preventDefault();filter();input.focus();});

  const syncSelected=()=>{
    const descriptions=Array.from(table.querySelectorAll('[name="item_description"]')).map(i=>normalize(i.value)).filter(Boolean);
    const chosen=[];
    items().forEach((button)=>{const name=normalize(button.dataset.name);const selected=!!name&&descriptions.includes(name);button.classList.toggle('is-selected',selected);if(selected&&!chosen.includes(button.dataset.name))chosen.push(button.dataset.name);});
    if(selectedBox)selectedBox.innerHTML=chosen.length?chosen.map(name=>`<span class="nx-selected-chip">${String(name).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}</span>`).join(''):'<span class="nx-muted">Noch keine Katalogposition ausgewählt.</span>';
  };
  root.addEventListener('click',(event)=>{if(event.target.closest('[data-catalog-item]'))window.setTimeout(syncSelected,0);});
  table.addEventListener('input',syncSelected);
  table.addEventListener('click',(event)=>{if(event.target.closest('.nx-item-remove'))window.setTimeout(syncSelected,0);});
  new MutationObserver(syncSelected).observe(table.querySelector('tbody')||table,{childList:true,subtree:true});
  syncSelected();
})();
'''
write(js_path, js)

print("KAYI catalog search, Enter filtering and visible selected-position state installed.")
