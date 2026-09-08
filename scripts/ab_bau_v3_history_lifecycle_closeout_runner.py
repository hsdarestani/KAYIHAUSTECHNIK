from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "scripts" / "ab_bau_v3_history_lifecycle_closeout.py"
text = TARGET.read_text(encoding="utf-8")

# The project view evolved after the first closeout draft: inject lifecycle
# context at the render dictionary instead of depending on an older KPI line.
old = '''        context_anchor = '        "invoice_gross": invoice_gross,\\n'\n        if context_anchor not in project:\n            raise RuntimeError("V3 closeout project context anchor missing")\n        project = project.replace(\n            context_anchor,\n            context_anchor\n            + '        "history": history,\\n'\n            + '        "tooltime_status": tooltime_status,\\n'\n            + '        "has_planned_appointments": has_planned_appointments,\\n',\n            1,\n        )\n'''
new = '''        project_context_anchor = '    return render(request, "rebuild/project_detail.html", {\\n'\n        if project_context_anchor not in project:\n            raise RuntimeError("V3 closeout project render-context anchor missing")\n        project = project.replace(\n            project_context_anchor,\n            project_context_anchor\n            + '        "history": history,\\n'\n            + '        "tooltime_status": tooltime_status,\\n'\n            + '        "has_planned_appointments": has_planned_appointments,\\n',\n            1,\n        )\n'''
if old not in text and new not in text:
    raise RuntimeError("V3 closeout project-context compatibility anchor missing")
if old in text:
    text = text.replace(old, new, 1)

# User profiles are created automatically by the current account signal. Reuse
# that profile in the generated functional test instead of violating the unique
# user/profile relation.
old_profile = '        UserProfile.objects.create(user=self.user, organization=self.org, role="office", is_mobile_worker=False)\n'
new_profile = '''        profile = self.user.profile\n        profile.organization = self.org\n        profile.role = UserProfile.Role.ADMIN\n        profile.is_mobile_worker = False\n        profile.save()\n'''
if old_profile in text:
    text = text.replace(old_profile, new_profile, 1)
elif new_profile not in text:
    raise RuntimeError("V3 closeout functional-test profile anchor missing")

TARGET.write_text(text, encoding="utf-8")
runpy.run_path(str(TARGET), run_name="__main__")

# Keep expenses in the customer timeline as real customer-scoped business data.
# This also preserves the existing functional cockpit contract that suppliers
# already persisted for a customer are visible after reload.
views_path = ROOT / "erp" / "rebuild_views.py"
views = views_path.read_text(encoding="utf-8")
expense_marker = '"kind": "expense"'
if expense_marker not in views:
    anchor = '''    for invoice in invoices[:100]:\n        history.append({"kind": "invoice", "at": invoice.created_at, "object": invoice, "status": invoice.get_status_display()})\n    history.sort(key=lambda row: row["at"], reverse=True)\n'''
    replacement = '''    for invoice in invoices[:100]:\n        history.append({"kind": "invoice", "at": invoice.created_at, "object": invoice, "status": invoice.get_status_display()})\n    for expense in m.Expense.objects.filter(organization=org, project__customer=customer).order_by("-pk")[:100]:\n        history.append({"kind": "expense", "at": getattr(expense, "created_at", timezone.now()), "object": expense, "status": expense.supplier or "Ausgabe"})\n    history.sort(key=lambda row: row["at"], reverse=True)\n'''
    if anchor not in views:
        raise RuntimeError("V3 closeout customer expense-history view anchor missing")
    views = views.replace(anchor, replacement, 1)
    compile(views, str(views_path), "exec")
    views_path.write_text(views, encoding="utf-8")

customer_path = ROOT / "design" / "v3" / "phase2" / "customer_detail.html"
customer = customer_path.read_text(encoding="utf-8")
if "row.kind == 'expense'" not in customer:
    anchor = '''{% elif row.kind == 'quote' %}<a href="{% url 'next-quote-edit' row.object.pk %}">{{ row.object.number|default:'Angebotsentwurf' }}</a><span>Angebot</span>{% else %}<a href="{% url 'next-invoice-edit' row.object.pk %}">{{ row.object.number|default:'Rechnungsentwurf' }}</a><span>Rechnung</span>{% endif %}'''
    replacement = '''{% elif row.kind == 'quote' %}<a href="{% url 'next-quote-edit' row.object.pk %}">{{ row.object.number|default:'Angebotsentwurf' }}</a><span>Angebot</span>{% elif row.kind == 'expense' %}<strong>{{ row.object.supplier|default:'Ausgabe' }}</strong><span>Ausgabe{% if row.object.description %} · {{ row.object.description }}{% endif %}</span>{% else %}<a href="{% url 'next-invoice-edit' row.object.pk %}">{{ row.object.number|default:'Rechnungsentwurf' }}</a><span>Rechnung</span>{% endif %}'''
    if anchor not in customer:
        raise RuntimeError("V3 closeout customer expense-history template anchor missing")
    customer = customer.replace(anchor, replacement, 1)
    customer_path.write_text(customer, encoding="utf-8")

if '"kind": "expense"' not in views_path.read_text(encoding="utf-8"):
    raise RuntimeError("V3 closeout expense history view guard missing")
if "row.kind == 'expense'" not in customer_path.read_text(encoding="utf-8"):
    raise RuntimeError("V3 closeout expense history template guard missing")
