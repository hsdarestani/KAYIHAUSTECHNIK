from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "templates/rebuild/project_detail.html"
text = path.read_text(encoding="utf-8")
old = '''{% for task in tasks %}<div class="nx-event"><div class="nx-event-time">{% if task.due_at %}{{ task.due_at|date:'d.m.' }}{% else %}–{% endif %}</div><div><b>{{ task.title }}</b><small>{{ task.description|truncatechars:100 }}</small></div><span class="nx-badge {% if task.status == 'done' %}nx-badge-success{% endif %}">{{ task.get_status_display }}</span></div>{% empty %}'''
new = '''{% for task in tasks %}<a class="nx-event" href="{% url 'next-task-edit' task.pk %}"><div class="nx-event-time">{% if task.due_at %}{{ task.due_at|date:'d.m.' }}{% else %}–{% endif %}</div><div><b>{{ task.title }}</b><small>{{ task.description|truncatechars:100 }}</small></div><span class="nx-badge {% if task.status == 'done' %}nx-badge-success{% endif %}">{{ task.get_status_display }}</span></a>{% empty %}'''
if new not in text:
    if old not in text:
        raise RuntimeError("Project task-row navigation contract changed")
    text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
print("KAYI project task rows now open the underlying task record.")
