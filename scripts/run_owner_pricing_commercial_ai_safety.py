from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPL = ROOT / "scripts" / "install_owner_pricing_commercial_ai_safety.py"

spec = importlib.util.spec_from_file_location("ab_owner_workflow_impl", IMPL)
if spec is None or spec.loader is None:
    raise RuntimeError("Could not load owner workflow installer")
impl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(impl)


def final_non_destructive_ai_forms() -> None:
    rel = "static/js/kayi-next.js"
    text = impl.read(rel)

    if "window.ABBauPreserveTypedText" not in text:
        helper = r'''

// A+Bau NON-DESTRUCTIVE KI FORM CONTRACT 2026-08-16
(() => {
  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (ch) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const isText = (field) => field && (field.tagName === 'TEXTAREA' || (field.tagName === 'INPUT' && !['checkbox','radio','file','hidden','date','datetime-local','time','number','range','color'].includes((field.type || 'text').toLowerCase())));
  const showSuggestion = (field, proposal) => {
    const host = field.closest('.nx-field') || field.parentElement;
    if (!host) return;
    let box = host.querySelector(':scope > .nx-ai-text-suggestion');
    if (!box) {
      box = document.createElement('div');
      box.className = 'nx-ai-text-suggestion';
      host.append(box);
    }
    const original = field.dataset.abOriginalTyped || field.value || '';
    if (!field.dataset.abOriginalTyped) field.dataset.abOriginalTyped = original;
    box.innerHTML = `<div class="nx-ai-text-label">KI-Vorschlag · deine Eingabe bleibt erhalten</div><div class="nx-ai-text-original"><b>Deine Eingabe</b><span>${esc(original)}</span></div><div class="nx-ai-text-proposal"><b>KI-Vorschlag</b><span>${esc(proposal)}</span></div><div class="nx-actions"><button type="button" class="nx-btn nx-btn-ghost" data-ai-append>Anhängen</button><button type="button" class="nx-btn" data-ai-accept>Vorschlag übernehmen</button></div>`;
    box.querySelector('[data-ai-append]')?.addEventListener('click', () => {
      const current = field.value || '';
      field.value = current ? `${current}\n${proposal}` : proposal;
      field.dispatchEvent(new Event('input',{bubbles:true}));
      field.dispatchEvent(new Event('change',{bubbles:true}));
      field.dataset.abUserOwned = '1';
    });
    box.querySelector('[data-ai-accept]')?.addEventListener('click', () => {
      field.value = proposal;
      field.dispatchEvent(new Event('input',{bubbles:true}));
      field.dispatchEvent(new Event('change',{bubbles:true}));
      field.dataset.abUserOwned = '1';
      box.classList.add('is-accepted');
    });
  };
  document.addEventListener('input', (event) => {
    const field = event.target;
    if (!event.isTrusted || !isText(field)) return;
    field.dataset.abUserOwned = '1';
    if (!field.dataset.abOriginalTyped && String(field.value || '').trim()) field.dataset.abOriginalTyped = field.value;
  }, true);
  window.ABBauPreserveTypedText = (field, proposal) => {
    if (!isText(field)) return false;
    const current = String(field.value || '');
    if (!current.trim() && field.dataset.abUserOwned !== '1') return false;
    if (current === String(proposal ?? '')) return true;
    showSuggestion(field, String(proposal ?? ''));
    return true;
  };
})();
'''
        text += helper

    advanced_old = "        if (!setControlValue(field, action.value)) continue;\n"
    advanced_new = "        if (window.ABBauPreserveTypedText?.(field, action.value)) continue;\n        if (!setControlValue(field, action.value)) continue;\n"
    legacy_old = "        if (field.type === 'checkbox') field.checked = /^(1|true|ja|yes)$/i.test(action.value || '');\n        else field.value = action.value ?? '';\n"
    legacy_new = "        if (field.type === 'checkbox') field.checked = /^(1|true|ja|yes)$/i.test(action.value || '');\n        else { const proposed = action.value ?? ''; if (window.ABBauPreserveTypedText?.(field, proposed)) continue; field.value = proposed; }\n"
    if "window.ABBauPreserveTypedText?.(field, action.value)" not in text and "ABBAuPreserveTypedText?.(field, proposed)" not in text:
        if advanced_old in text:
            text = text.replace(advanced_old, advanced_new, 1)
        elif legacy_old in text:
            text = text.replace(legacy_old, legacy_new, 1)
        else:
            raise RuntimeError("Final assistant set_field contract changed; refusing a destructive fallback")

    # Field voice/AI report extraction is another KI write path. Keep already typed
    # report/services/material visible and surface the new text as a suggestion.
    direct_assignments = {
        "        if (report) report.value = result.report || result.transcript || '';\n": "        if (report && !window.ABBauPreserveTypedText?.(report, result.report || result.transcript || '')) report.value = result.report || result.transcript || '';\n",
        "        if (services && result.services) services.value = result.services;\n": "        if (services && result.services && !window.ABBauPreserveTypedText?.(services, result.services)) services.value = result.services;\n",
        "        if (material && result.material) material.value = result.material;\n": "        if (material && result.material && !window.ABBauPreserveTypedText?.(material, result.material)) material.value = result.material;\n",
    }
    for old, new in direct_assignments.items():
        if old in text and new not in text:
            text = text.replace(old, new, 1)

    impl.write(rel, text)

    rel = "static/css/kayi-next.css"
    css = impl.read(rel)
    if ".nx-ai-text-suggestion" not in css:
        css += r'''

/* Non-destructive KI suggestions: user text is never silently replaced. */
.nx-ai-text-suggestion{margin-top:8px;padding:10px;border:1px solid var(--nx-line,#ddd8ce);border-radius:12px;background:rgba(173,137,43,.06);display:grid;gap:8px}
.nx-ai-text-label{font-size:11px;font-weight:800;color:var(--nx-muted,#6f747a);text-transform:uppercase;letter-spacing:.04em}
.nx-ai-text-original,.nx-ai-text-proposal{display:grid;gap:3px;font-size:12px;line-height:1.45;white-space:pre-wrap}
.nx-ai-text-original{padding:7px 9px;border-radius:9px;background:rgba(0,0,0,.035)}
.nx-ai-text-original b,.nx-ai-text-proposal b{font-size:11px}
.nx-ai-text-suggestion.is-accepted .nx-ai-text-original{border-left:3px solid #ad892b}
'''
        impl.write(rel, css)


impl.patch_non_destructive_ai_forms = final_non_destructive_ai_forms
impl.main()
