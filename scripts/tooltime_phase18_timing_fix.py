from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME PHASE 18 TIMING FIX 2026-08-21"


def run(module) -> None:
    rel = "erp/rebuild_views.py"
    text = module.read(rel)
    old = '''        original_start = event.starts_at
        original_series = event.recurrence_series
        original_index = event.recurrence_index
'''
    new = '''        # ModelForm validation mutates the bound instance before this block.
        # Reload the persisted occurrence so the series time delta is measured
        # against the real pre-edit schedule rather than the already-cleaned form value.
        persisted_event = m.CalendarEvent.objects.get(organization=org, pk=event.pk)
        original_start = persisted_event.starts_at
        original_series = persisted_event.recurrence_series
        original_index = persisted_event.recurrence_index
'''
    if new not in text:
        if old not in text:
            raise RuntimeError("Phase 18 timing-fix anchor missing")
        text = text.replace(old, new, 1)
    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")

    if "persisted_event = m.CalendarEvent.objects.get(organization=org, pk=event.pk)" not in text:
        raise RuntimeError("Phase 18 timing fix was not installed")
    print(f"{MARKER}: recurrence edit deltas now use the persisted pre-validation appointment time.")
