#!/usr/bin/env python3
"""Make CRUD feedback visible, typed and accessible across the rebuilt app."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Expected notification anchor missing in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


base = ROOT / "templates/rebuild/base.html"
old_messages = '''<div class="nx-content">{% if messages %}<div class="nx-messages">{% for message in messages %}<div class="nx-message">{{ message }}</div>{% endfor %}</div>{% endif %}{% block content %}{% endblock %}</div>'''
new_messages = '''<div class="nx-content">{% if messages %}<div class="nx-messages" aria-label="Systemmeldungen">{% for message %}<div class="nx-message nx-message-{{ message.tags|default:'info' }}" data-notification="{{ message.tags|default:'info' }}" {% if 'error' in message.tags %}role="alert" aria-live="assertive"{% else %}role="status" aria-live="polite"{% endif %} aria-atomic="true"><span class="nx-message-icon" aria-hidden="true"></span><span class="nx-message-text">{{ message }}</span><button class="nx-message-close" type="button" aria-label="Meldung schließen">×</button></div>{% endfor %}</div>{% endif %}{% block content %}{% endblock %}</div>'''
replace_once(base, old_messages, new_messages)


css = ROOT / "static/css/kayi-next.css"
css_marker = "/* A+Bau accessible CRUD notifications 20260910 */"
css_rules = r'''

/* A+Bau accessible CRUD notifications 20260910 */
.nx-messages{position:relative;z-index:40}.nx-message{display:grid;grid-template-columns:22px minmax(0,1fr) 30px;align-items:center;gap:9px;min-height:48px;font-size:12px;font-weight:650;box-shadow:0 12px 32px rgba(17,20,24,.08)}.nx-message-icon{width:22px;height:22px;border-radius:50%;display:grid;place-items:center;background:#eee;color:#4d5157}.nx-message-icon:before{content:"i";font-size:12px;font-weight:900}.nx-message-success{border-color:#9fd8c6!important;background:#effbf6!important;color:#185a47!important}.nx-message-success .nx-message-icon{background:#c9efe2;color:#12604a}.nx-message-success .nx-message-icon:before{content:"✓"}.nx-message-error{border-color:#e8b0ae!important;background:#fff2f1!important;color:#8d2d2a!important}.nx-message-error .nx-message-icon{background:#f6cfcd;color:#922f2b}.nx-message-error .nx-message-icon:before{content:"!"}.nx-message-warning{border-color:#e7cc8d!important;background:#fff8e7!important;color:#725314!important}.nx-message-warning .nx-message-icon{background:#f6e4b8;color:#725314}.nx-message-warning .nx-message-icon:before{content:"!"}.nx-message-close{width:30px;height:30px;padding:0;border:0;border-radius:9px;background:transparent;color:currentColor;font:700 18px/1 inherit;cursor:pointer;opacity:.72}.nx-message-close:hover,.nx-message-close:focus-visible{background:rgba(0,0,0,.07);opacity:1}.nx-message.is-dismissing{opacity:0;transform:translateY(-4px);transition:.16s ease}@media(max-width:700px){.nx-message{grid-template-columns:20px minmax(0,1fr) 30px;padding:11px 10px}.nx-messages{margin-inline:-2px}}
'''
css_text = css.read_text(encoding="utf-8")
if css_marker not in css_text:
    css.write_text(css_text.rstrip() + css_rules + "\n", encoding="utf-8")


js = ROOT / "static/js/kayi-next.js"
js_marker = "// A+Bau ACCESSIBLE CRUD NOTIFICATIONS 2026-09-10"
js_rules = r'''

// A+Bau ACCESSIBLE CRUD NOTIFICATIONS 2026-09-10
(() => {
  const dismiss = (node) => {
    if (!node || node.classList.contains('is-dismissing')) return;
    node.classList.add('is-dismissing');
    window.setTimeout(() => {
      const stack = node.parentElement;
      node.remove();
      if (stack && !stack.querySelector('.nx-message')) stack.remove();
    }, 170);
  };
  document.addEventListener('click', (event) => {
    const close = event.target.closest?.('.nx-message-close');
    if (close) dismiss(close.closest('.nx-message'));
  });
  document.querySelectorAll('.nx-message-success[role="status"]').forEach((node) => {
    window.setTimeout(() => dismiss(node), 7000);
  });
  document.addEventListener('submit', (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || !form.checkValidity()) return;
    form.setAttribute('aria-busy', 'true');
    const submitter = event.submitter;
    if (submitter && !submitter.dataset.originalLabel) {
      submitter.dataset.originalLabel = submitter.textContent;
      submitter.textContent = 'Wird gespeichert …';
    }
  });
})();
'''
js_text = js.read_text(encoding="utf-8")
if js_marker not in js_text:
    js.write_text(js_text.rstrip() + js_rules + "\n", encoding="utf-8")


tests = ROOT / "tests/test_user_flow_notifications.py"
tests.write_text('''from pathlib import Path\n\nfrom django.test import SimpleTestCase\n\n\n+class UserFlowNotificationContractTests(SimpleTestCase):\n+    def test_flash_messages_keep_severity_and_accessibility(self):\n+        template = Path("templates/rebuild/base.html").read_text(encoding="utf-8")\n+        self.assertIn("data-notification=", template)\n+        self.assertIn("message.tags", template)\n+        self.assertIn('role="alert" aria-live="assertive"', template)\n+        self.assertIn('role="status" aria-live="polite"', template)\n+        self.assertIn("nx-message-close", template)\n+\n+    def test_notification_runtime_has_busy_and_dismiss_feedback(self):\n+        script = Path("static/js/kayi-next.js").read_text(encoding="utf-8")\n+        self.assertIn("ACCESSIBLE CRUD NOTIFICATIONS", script)\n+        self.assertIn("aria-busy", script)\n+        self.assertIn("Wird gespeichert", script)\n+        self.assertIn("nx-message-close", script)\n+\n+    def test_core_create_flows_emit_result_messages(self):\n+        views = Path("erp/rebuild_views.py").read_text(encoding="utf-8")\n+        projects = Path("erp/rebuild_projects.py").read_text(encoding="utf-8")\n+        operations = Path("erp/rebuild_ops.py").read_text(encoding="utf-8")\n+        for message in (\n+            "Kunde wurde angelegt.",\n+            "Termin wurde geplant.",\n+            "Angebot gespeichert.",\n+            "Rechnungsentwurf gespeichert.",\n+        ):\n+            self.assertIn(message, views)\n+        self.assertIn("Projekt wurde angelegt.", projects)\n+        self.assertIn("Aufgabe gespeichert.", operations)\n+        self.assertIn("Beleg und Ausgabe wurden gespeichert.", operations)\n+'''.replace('\n+','\n'), encoding="utf-8")

print("Applied accessible CRUD notifications and regression coverage.")
