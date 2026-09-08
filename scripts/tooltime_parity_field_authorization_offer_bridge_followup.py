from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU ANGEBOT/FREIGABE BRIDGE FOLLOWUP 2026-09-08"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Angebot/Freigabe followup target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    (ROOT / rel).write_text(text, encoding="utf-8")


# Resolve the ToolTime context from the actual appointment/event instead of a
# synthetic document value. The shared tag already supports any object carrying
# the organization, so Termin and Angebot stay in the same organization scope.
template_rel = "templates/rebuild/appointment_detail.html"
template = read(template_rel)
template = template.replace(
    "{% tooltime_context request None 'authorization' as tt %}",
    "{% tooltime_context request event 'authorization' as tt %}",
    1,
)

# Merge the ToolTime form class into an existing class attribute if a later field
# layer already added one; duplicate class attributes are invalid HTML and can
# make selector behavior browser-dependent.
form_match = re.search(
    r'<form\b(?=[^>]*data-authorization-form)[^>]*>',
    template,
    flags=re.S,
)
if not form_match:
    raise RuntimeError("Final authorization form tag missing")
form_tag = form_match.group(0)
class_attrs = re.findall(r'class="([^"]*)"', form_tag)
if len(class_attrs) > 1:
    merged = []
    for value in class_attrs:
        for name in value.split():
            if name not in merged:
                merged.append(name)
    without_classes = re.sub(r'\s+class="[^"]*"', "", form_tag)
    form_tag = without_classes[:-1] + f' class="{" ".join(merged)}">'
elif len(class_attrs) == 1 and "tt-document-form" not in class_attrs[0].split():
    merged = (class_attrs[0] + " tt-document-form").strip()
    form_tag = form_tag.replace(f'class="{class_attrs[0]}"', f'class="{merged}"', 1)
elif not class_attrs:
    form_tag = form_tag[:-1] + ' class="tt-document-form">'
if "data-article-search-url=" not in form_tag:
    form_tag = form_tag[:-1] + ' data-article-search-url="{% url \'next-article-search\' %}">'
template = template[: form_match.start()] + form_tag + template[form_match.end() :]
if MARKER not in template:
    template = template.replace(
        "{% tooltime_context request event 'authorization' as tt %}",
        "{% tooltime_context request event 'authorization' as tt %}\n{# " + MARKER + " #}",
        1,
    )
write(template_rel, template)


# The old field-only pricing widget owned the Festpreis/Schätzung/Aufwand toggle.
# Once that widget is removed, keep only this Termin-specific visibility behavior;
# all price rows, markups, discount, tax and totals continue to be owned by the
# exact Angebot runtime loaded on the page.
js_rel = "static/js/field-authorization.js"
js = read(js_rel)
cap_marker = "A+BAU ANGEBOT PRICING MODE CAP 2026-09-08"
if cap_marker not in js:
    anchor = "    // A+BAU ANGEBOT ROW ADAPTER 2026-09-08\n"
    if anchor not in js:
        raise RuntimeError("Shared Angebot row adapter missing from field runtime")
    snippet = r'''    // A+BAU ANGEBOT PRICING MODE CAP 2026-09-08
    const capWrap = form.querySelector('[data-cap-wrap]');
    const syncCap = () => {
      const mode = form.querySelector('input[name=pricing_mode]:checked')?.value || 'fixed';
      if (capWrap) capWrap.hidden = mode === 'fixed';
    };
    form.querySelectorAll('input[name=pricing_mode]').forEach((radio) => radio.addEventListener('change', syncCap));
    syncCap();
'''
    js = js.replace(anchor, snippet + anchor, 1)
write(js_rel, js)


final_template = read(template_rel)
final_js = read(js_rel)
for needle in (
    "{% tooltime_context request event 'authorization' as tt %}",
    'class="tt-document-form',
    "data-article-search-url",
    "rebuild/_tooltime_services_editor.html",
    "rebuild/_tooltime_calculation_summary.html",
    "rebuild/_tooltime_article_modal.html",
):
    if needle not in final_template:
        raise RuntimeError(f"Shared Angebot Termin form missing: {needle}")
if final_template.count('class="tt-document-form') != 1:
    raise RuntimeError("Authorization form must expose exactly one ToolTime document-form class")
if "A+BAU ANGEBOT PRICING MODE CAP 2026-09-08" not in final_js:
    raise RuntimeError("Termin pricing-mode cap behavior missing after Angebot integration")

print("Angebot/Freigabe bridge followup verified: shared editor remains canonical and Termin-only cap behavior is preserved.")
