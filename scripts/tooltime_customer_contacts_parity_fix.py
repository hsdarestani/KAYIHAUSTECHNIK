from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Customer parity fix target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    (ROOT / rel).write_text(text, encoding="utf-8")


template_path = "templates/rebuild/customers.html"
template = read(template_path)
private_duplicate = '''          <div class="tt-private-only tt-two-col" data-private-only>
            <div class="tt-field"><label for="{{ create_form.first_name.id_for_label }}">Vorname</label>{{ create_form.first_name }}{{ create_form.first_name.errors }}</div>
            <div class="tt-field"><label for="{{ create_form.last_name.id_for_label }}">Nachname</label>{{ create_form.last_name }}{{ create_form.last_name.errors }}</div>
          </div>

'''
if private_duplicate in template:
    template = template.replace(private_duplicate, "", 1)
template = template.replace('class="tt-field tt-company-contact"', 'class="tt-field tt-name-contact"')
old_range = '''        <span>{{ offset|add:'1' }}–{% if has_next %}{{ offset|add:page_size }}{% else %}{{ total_count }}{% endif %}</span>'''
new_range = '''        <span>{% if total_count %}{{ offset|add:'1' }}–{% if has_next %}{{ offset|add:page_size }}{% else %}{{ total_count }}{% endif %}{% else %}0{% endif %}</span>'''
if old_range in template:
    template = template.replace(old_range, new_range, 1)
write(template_path, template)

js_path = "static/js/kayi-next.js"
js = read(js_path)
js = js.replace("    form.querySelectorAll('[data-private-only]').forEach((node) => { node.hidden = business; });\n", "")
js = js.replace("    form.querySelectorAll('.tt-company-contact').forEach((node) => { node.hidden = !business; });\n", "")
write(js_path, js)

final_template = read(template_path)
final_js = read(js_path)
if "tt-private-only tt-two-col" in final_template:
    raise RuntimeError("Duplicate private customer name inputs remain")
if 'class="tt-field tt-company-contact"' in final_template:
    raise RuntimeError("Business-only name fields remain")
if "{% if total_count %}" not in final_template:
    raise RuntimeError("Empty customer pagination is not normalized")
if "querySelectorAll('[data-private-only]')" in final_js or "querySelectorAll('.tt-company-contact')" in final_js:
    raise RuntimeError("Obsolete customer-name visibility JS remains")
print("Customer modal duplicate-name and empty-pagination polish applied.")
