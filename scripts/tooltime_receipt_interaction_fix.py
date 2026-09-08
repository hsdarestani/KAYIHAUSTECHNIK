from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "templates" / "rebuild" / "expense_receipt_form.html"
text = PATH.read_text(encoding="utf-8")

text = text.replace(
    '<label id="receipt-dropzone" class="tt-receipt-dropzone" for="receipt-file" tabindex="0" data-receipt-dropzone="1">',
    '<div id="receipt-dropzone" class="tt-receipt-dropzone" tabindex="0" role="button" aria-label="Beleg hochladen" data-receipt-dropzone="1">',
    1,
)
text = text.replace(
    ' data-force-open="{% if receipt_form.errors %}1{% else %}0{% endif %}" onclick="event.preventDefault();event.stopPropagation();">',
    ' data-force-open="{% if receipt_form.errors %}1{% else %}0{% endif %}">',
    1,
)
text = text.replace(
    '        </div>\n      </label>\n    </section>',
    '        </div>\n      </div>\n    </section>',
    1,
)
text = text.replace(
    "  drop.addEventListener('keydown',e=>{if((e.key==='Enter'||e.key===' ')&&e.target===drop){e.preventDefault();input.click();}});",
    "  drop.addEventListener('click',e=>{if(!e.target.closest('.tt-receipt-details')&&e.target!==input){input.click();}});\n  drop.addEventListener('keydown',e=>{if((e.key==='Enter'||e.key===' ')&&e.target===drop){e.preventDefault();input.click();}});",
    1,
)

for marker in (
    'role="button" aria-label="Beleg hochladen"',
    "!e.target.closest('.tt-receipt-details')",
    'id="receipt-details"',
):
    if marker not in text:
        raise RuntimeError(f"Receipt interaction guard missing: {marker}")
if 'onclick="event.preventDefault();event.stopPropagation();"' in text:
    raise RuntimeError("Receipt detail controls would still cancel their native input behavior")

PATH.write_text(text, encoding="utf-8")
print("ToolTime receipt interaction hardening applied.")
