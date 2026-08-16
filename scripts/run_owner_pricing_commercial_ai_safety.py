from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPL = ROOT / "scripts" / "install_owner_pricing_commercial_ai_safety.py"

spec = importlib.util.spec_from_file_location("ab_owner_workflow_impl", IMPL)
if spec is None or spec.loader is None:
    raise RuntimeError("Could not load owner workflow installer")
impl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(impl)
_original_patch_commercial_templates = impl.patch_commercial_templates


def final_commercial_templates() -> None:
    """Keep prior ToolTime commercial UI, but guarantee the project→Termin handoff."""
    _original_patch_commercial_templates()
    rel = "templates/rebuild/project_form.html"
    text = impl.read(rel)
    if 'name="create_and_schedule"' not in text:
        pattern = re.compile(r'(<div class="nx-form-actions">.*?)(</div>)', re.S)
        match = pattern.search(text)
        if not match:
            raise RuntimeError("Project form has no final action bar for project→Termin handoff")
        button = '<button class="nx-btn nx-btn-accent" type="submit" name="create_and_schedule" value="1">Projekt anlegen & Termin planen →</button>'
        text = text[:match.start()] + match.group(1) + button + match.group(2) + text[match.end():]
        impl.write(rel, text)


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

    # Voice/report KI is also a form-writing path. Never silently overwrite text
    # already entered by a user or loaded from a saved record.
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


def final_guard() -> None:
    checks = {
        "erp/models.py": ["ProjectCommercialSettings", "AppointmentCommercialSettings"],
        "erp/owner_business_views.py": ["price_list_upload", "organization_price_search", "organization=org"],
        "erp/services/org_price_search.py": ["search_org_prices", "source__active=True"],
        "erp/rebuild_urls.py": ["next-price-lists", "next-price-list-upload", "next-org-price-search"],
        "templates/rebuild/owner_price_lists.html": ["Preisliste hochladen", "price_file", "next-price-list-upload"],
        "templates/rebuild/project_form.html": ["commercial_markup_percent", "create_and_schedule", "Termin planen"],
        "templates/rebuild/appointment_form.html": ["commercial_markup_percent"],
        "erp/rebuild_views.py": ["ProjectCommercialSettings.objects.update_or_create", "AppointmentCommercialSettings.objects.update_or_create"],
        "erp/ai_scope_planner.py": ["_extract_room_height", "Kalkulationsfaktor", "Standardfaktor"],
        "static/js/kayi-next.js": ["window.ABBauPreserveTypedText", "deine Eingabe bleibt erhalten"],
        "static/css/kayi-next.css": [".nx-ai-text-original", ".nx-ai-text-proposal"],
        "tests/test_owner_pricing_commercial_ai_safety.py": ["test_search_never_crosses_tenants", "test_painting_uses_explicit_height"],
        "templates/rebuild/base.html": [impl.VERSION],
    }
    missing = []
    for rel, needles in checks.items():
        text = impl.read(rel)
        for needle in needles:
            if needle not in text:
                missing.append(f"{rel}: {needle}")
    migration = ROOT / "erp" / "migrations" / "0999_ab_bau_commercial_workflow.py"
    if not migration.exists():
        missing.append("commercial migration")
    if missing:
        raise RuntimeError("Final owner/commercial/KI guard failed: " + "; ".join(missing))


impl.patch_commercial_templates = final_commercial_templates
impl.patch_non_destructive_ai_forms = final_non_destructive_ai_forms
impl.guard = final_guard
impl.main()
