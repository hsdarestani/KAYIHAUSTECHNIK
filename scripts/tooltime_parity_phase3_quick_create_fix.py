from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REL = "templates/rebuild/document_editor.html"
path = ROOT / REL
text = path.read_text(encoding="utf-8")

old_section = '<section class="tt-card tt-document-top">'
new_section = '<section class="tt-card tt-document-top" data-quick-customer-url="{% url \'next-quick-customer-create\' %}" data-quick-project-url="{% url \'next-quick-project-create\' %}">'
if new_section not in text:
    if old_section not in text:
        raise RuntimeError("Phase 3 quick-create: Dokumentkopf-Anker fehlt")
    text = text.replace(old_section, new_section, 1)

old_help = '<div class="tt-inline-help"><a class="tt-link" href="{% url \'next-customer-create\' %}" target="_blank" rel="noopener">＋ Neuen Kunden anlegen</a><span>Dokumente ohne Projekt werden intern sauber dem Kunden zugeordnet und erscheinen nicht als normales Projekt.</span></div>'
new_help = '''<div class="tt-inline-help"><button class="nx-btn" type="button" data-new-customer>＋ Neuen Kunden anlegen</button><button class="nx-btn" type="button" data-new-project>＋ Neues Projekt anlegen</button><span>Ein Projekt ist optional. Kunde und Projekt können direkt im Dokument angelegt werden.</span></div>'''
if new_help not in text:
    if old_help not in text:
        raise RuntimeError("Phase 3 quick-create: Hilfsaktionen-Anker fehlt")
    text = text.replace(old_help, new_help, 1)

# The existing ToolTime completion layer already installs both real creation
# endpoints, modals and AJAX submit handlers. Phase 3 must preserve those controls
# when replacing the customer/project header instead of falling back to dead UI.
for required in (
    'data-new-customer',
    'data-new-project',
    "next-quick-customer-create",
    "next-quick-project-create",
    'data-customer-modal',
    'data-project-modal',
):
    if required not in text:
        raise RuntimeError(f"Phase 3 quick-create contract missing: {required}")

path.write_text(text, encoding="utf-8")
print("ToolTime Phase 3 Schnellanlage wiederhergestellt: Kunde und Projekt öffnen die bestehenden echten Schnellanlage-Flows.")
