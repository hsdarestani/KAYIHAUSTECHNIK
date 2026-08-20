from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME PHASE 9 REGRESSION FIX 2026-08-20"


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Phase 9 regression anchor missing: {label}")
    return text.replace(old, new, 1)


def patch_views(module) -> None:
    rel = "erp/rebuild_views.py"
    text = module.read(rel)
    text = _replace_once(
        text,
        'self.fields["object_location"].empty_label = "Kundenadresse verwenden"',
        'self.fields["object_location"].empty_label = "Kundenadresse verwenden (Standard)"',
        "project object-location default label",
    )
    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def patch_customer_template(module) -> None:
    rel = "templates/rebuild/customer_form.html"
    text = module.read(rel)
    text = _replace_once(
        text,
        '<form method="post" class="tt-create-form" data-customer-form>{% csrf_token %}',
        '<form method="post" class="tt-create-form" data-customer-form novalidate>{% csrf_token %}',
        "customer form novalidate",
    )
    text = _replace_once(
        text,
        '    {% if form.non_field_errors %}<div class="tt-form-alert">{{ form.non_field_errors }}</div>{% endif %}',
        '    {% if form.errors or location_form.errors %}<div class="tt-form-alert">Kunde konnte nicht gespeichert werden.</div>{% endif %}\n    {% if form.non_field_errors %}<div class="tt-form-alert">{{ form.non_field_errors }}</div>{% endif %}',
        "customer visible error summary",
    )
    text = _replace_once(
        text,
        '<summary><span>Details einblenden</span><span class="tt-chevron">⌄</span></summary>',
        '<summary><span>Weitere Angaben <small>· Details einblenden</small></span><span class="tt-chevron">⌄</span></summary>',
        "customer progressive details label",
    )
    module.write(rel, text)


def patch_project_template(module) -> None:
    rel = "templates/rebuild/project_form.html"
    text = module.read(rel)
    anchor = '<form method="post" class="tt-create-form" data-project-object-ux>{% csrf_token %}'
    replacement = (
        anchor
        + '\n    <p class="tt-create-hint"><strong>Kein Assistent:</strong> Alle wichtigen Projektdaten werden direkt auf einer Seite erfasst.</p>'
    )
    text = _replace_once(text, anchor, replacement, "project no-wizard hint")
    text = text.replace(
        '<option value="">Kundenadresse verwenden</option>',
        '<option value="">Kundenadresse verwenden (Standard)</option>',
    )
    module.write(rel, text)


def patch_phase9_tests(module) -> None:
    rel = "tests/test_tooltime_phase9_core_crud.py"
    text = module.read(rel)
    old = 'UserProfile.objects.create(user=self.user, organization=self.org, role="office", is_mobile_worker=False)'
    new = 'UserProfile.objects.update_or_create(user=self.user, defaults={"organization": self.org, "role": "office", "is_mobile_worker": False})'
    text = _replace_once(text, old, new, "phase 9 test profile setup")
    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def run(module) -> None:
    patch_views(module)
    patch_customer_template(module)
    patch_project_template(module)
    patch_phase9_tests(module)
    print(f"{MARKER}: deterministic regressions restored after Phase 9 assembly.")
