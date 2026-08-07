from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"Expected Leistungsnachweise source fragment not found in {path}: {old[:120]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


# Pagination keeps the cross-project archive fast even after many on-site reports.
replace_once(
    "erp/workflow_views.py",
    "from django.contrib.auth.models import User\n",
    "from django.contrib.auth.models import User\nfrom django.core.paginator import Paginator\n",
)

# Give Leistungsnachweise a stable, direct application route instead of hiding the
# feature behind individual project detail pages.
replace_once(
    "erp/urls.py",
    '    path("projects/<int:project_pk>/site-reports/new/", workflow_views.site_report_create, name="site-report-create"),\n',
    '    path("site-reports/", workflow_views.site_report_list, name="site-report-list"),\n'
    '    path("projects/<int:project_pk>/site-reports/new/", workflow_views.site_report_create, name="site-report-create"),\n',
)

# Put the archive directly below Projekte, where office users and technicians
# naturally look for project-related operational documents.
replace_once(
    "templates/erp/base.html",
    '  <a href="{% url \'resource-list\' \'projects\' %}" class="nav-item"><span>🗂</span>Projekte</a>\n',
    '  <a href="{% url \'resource-list\' \'projects\' %}" class="nav-item"><span>🗂</span>Projekte</a>\n'
    '  <a href="{% url \'site-report-list\' %}" class="nav-item"><span>✍</span>Leistungsnachweise</a>\n',
)

list_view = '''@login_required
def site_report_list(request):
    org = _org(request)
    reports = SiteReport.objects.select_related(
        "project", "project__customer", "employee"
    ).filter(organization=org)
    insurance_projects = Project.objects.select_related("customer").filter(
        organization=org,
        job_type=Project.JobType.INSURANCE,
    )

    profile = getattr(request.user, "profile", None)
    if profile and profile.role == UserProfile.Role.TECHNICIAN:
        employee = getattr(request.user, "employee", None)
        if employee is None:
            reports = reports.none()
            insurance_projects = insurance_projects.none()
        else:
            reports = reports.filter(
                Q(project__members=employee) | Q(project__manager=employee)
            ).distinct()
            insurance_projects = insurance_projects.filter(
                Q(members=employee) | Q(manager=employee)
            ).distinct()

    scoped_reports = reports
    summary = {
        "total": scoped_reports.count(),
        "signed": scoped_reports.filter(signed_at__isnull=False).count(),
        "draft": scoped_reports.filter(signed_at__isnull=True).count(),
        "bando": scoped_reports.filter(kind=SiteReport.Kind.BANDO).count(),
    }

    query = request.GET.get("q", "").strip()[:120]
    status_filter = request.GET.get("status", "").strip()
    kind_filter = request.GET.get("kind", "").strip()

    if query:
        reports = reports.filter(
            Q(project__number__icontains=query)
            | Q(project__title__icontains=query)
            | Q(project__customer__number__icontains=query)
            | Q(project__customer__company__icontains=query)
            | Q(signed_name__icontains=query)
            | Q(title__icontains=query)
        )
    if status_filter == "signed":
        reports = reports.filter(signed_at__isnull=False)
    elif status_filter == "draft":
        reports = reports.filter(signed_at__isnull=True)
    else:
        status_filter = ""
    if kind_filter in {SiteReport.Kind.BANDO, SiteReport.Kind.GENERIC}:
        reports = reports.filter(kind=kind_filter)
    else:
        kind_filter = ""

    reports = reports.order_by("-created_at", "-pk")
    page_obj = Paginator(reports, 30).get_page(request.GET.get("page"))

    pending_projects = insurance_projects.exclude(
        site_reports__kind=SiteReport.Kind.BANDO
    ).order_by("-created_at", "-pk").distinct()
    pending_count = pending_projects.count()

    return render(request, "erp/site_report_list.html", {
        "page_obj": page_obj,
        "reports": page_obj.object_list,
        "summary": summary,
        "query": query,
        "status_filter": status_filter,
        "kind_filter": kind_filter,
        "pending_projects": pending_projects[:8],
        "pending_count": pending_count,
        "can_create_reports": can_write(request.user),
    })


'''

view_marker = '''@login_required
@require_http_methods(["GET", "POST"])
def site_report_create(request, project_pk):
'''
workflow_path = Path("erp/workflow_views.py")
workflow_text = workflow_path.read_text(encoding="utf-8")
if "def site_report_list(request):" not in workflow_text:
    if view_marker not in workflow_text:
        raise RuntimeError("Could not locate site_report_create while adding Leistungsnachweise archive")
    workflow_path.write_text(workflow_text.replace(view_marker, list_view + view_marker, 1), encoding="utf-8")


template = '''{% extends "erp/base.html" %}
{% block title %}Leistungsnachweise · KAYI{% endblock %}
{% block content %}
<div class="page-head">
  <div>
    <div class="eyebrow">BETRIEB</div>
    <h1>Leistungsnachweise</h1>
    <p>Alle B&amp;O Leistungsnachweise und Vor-Ort-Berichte projektübergreifend verwalten.</p>
  </div>
  <div class="actions">
    <a class="btn btn-secondary" href="{% url 'resource-list' 'projects' %}">Projekte öffnen</a>
  </div>
</div>

<div class="kpi-grid">
  <div class="kpi"><div class="kpi-icon">✍</div><div><small>Gesamt</small><strong>{{ summary.total }}</strong><em>Leistungsnachweise</em></div></div>
  <div class="kpi"><div class="kpi-icon">✓</div><div><small>Unterschrieben</small><strong>{{ summary.signed }}</strong><em>Kundenbestätigung vorhanden</em></div></div>
  <div class="kpi"><div class="kpi-icon">◷</div><div><small>Entwürfe</small><strong>{{ summary.draft }}</strong><em>noch ohne Unterschrift</em></div></div>
  <div class="kpi"><div class="kpi-icon">B&amp;O</div><div><small>B&amp;O</small><strong>{{ summary.bando }}</strong><em>Leistungsnachweis / Regiebericht</em></div></div>
</div>

<section class="panel table-panel">
  <form class="table-toolbar" method="get">
    <label class="search-field"><span>⌕</span><input type="search" name="q" value="{{ query }}" placeholder="Projekt, Kunde oder Unterzeichner suchen ..."></label>
    <select class="form-control" name="status" aria-label="Status">
      <option value="">Alle Status</option>
      <option value="signed" {% if status_filter == 'signed' %}selected{% endif %}>Unterschrieben</option>
      <option value="draft" {% if status_filter == 'draft' %}selected{% endif %}>Entwurf</option>
    </select>
    <select class="form-control" name="kind" aria-label="Typ">
      <option value="">Alle Typen</option>
      <option value="bando" {% if kind_filter == 'bando' %}selected{% endif %}>B&amp;O Leistungsnachweis</option>
      <option value="generic" {% if kind_filter == 'generic' %}selected{% endif %}>Vor-Ort-Bericht</option>
    </select>
    <button class="btn btn-primary" type="submit">Filtern</button>
    {% if query or status_filter or kind_filter %}<a class="btn btn-secondary" href="{% url 'site-report-list' %}">Zurücksetzen</a>{% endif %}
  </form>

  <div class="table-wrap">
    <table>
      <thead><tr><th>Projekt</th><th>Kunde</th><th>Typ</th><th>Status</th><th>Erstellt</th><th>Mitarbeiter</th><th></th></tr></thead>
      <tbody>
      {% for report in reports %}
        <tr>
          <td><b>{{ report.project.number }}</b><br><span class="muted">{{ report.project.title }}</span></td>
          <td>{{ report.project.customer.display_name }}</td>
          <td>{% if report.kind == 'bando' %}<span class="badge">B&amp;O</span> Leistungsnachweis{% else %}Vor-Ort-Bericht{% endif %}</td>
          <td>{% if report.signed_at %}<span class="badge success">✓ Unterschrieben</span><br><span class="muted">{{ report.signed_name }}</span>{% else %}<span class="badge warning">Entwurf</span>{% endif %}</td>
          <td>{{ report.created_at|date:'d.m.Y H:i' }}</td>
          <td>{% if report.employee %}{{ report.employee.first_name }} {{ report.employee.last_name }}{% else %}<span class="muted">–</span>{% endif %}</td>
          <td class="row-actions"><a href="{% url 'site-report-pdf' report.pk %}" target="_blank">PDF</a>&nbsp;&nbsp;<a href="{% url 'project-detail' report.project.pk %}">Projekt</a></td>
        </tr>
      {% empty %}
        <tr><td colspan="7"><div class="empty">Keine Leistungsnachweise für diese Auswahl gefunden.</div></td></tr>
      {% endfor %}
      </tbody>
    </table>
  </div>

  {% if page_obj.paginator.num_pages > 1 %}
  <div class="pagination">
    {% if page_obj.has_previous %}<a href="?q={{ query|urlencode }}&amp;status={{ status_filter }}&amp;kind={{ kind_filter }}&amp;page={{ page_obj.previous_page_number }}">← Zurück</a>{% endif %}
    <span>Seite {{ page_obj.number }} von {{ page_obj.paginator.num_pages }}</span>
    {% if page_obj.has_next %}<a href="?q={{ query|urlencode }}&amp;status={{ status_filter }}&amp;kind={{ kind_filter }}&amp;page={{ page_obj.next_page_number }}">Weiter →</a>{% endif %}
  </div>
  {% endif %}
</section>

{% if pending_count %}
<section class="panel" style="margin-top:17px">
  <div class="panel-head">
    <div><h2>B&amp;O-Projekte ohne Leistungsnachweis</h2><p>{{ pending_count }} Projekt{% if pending_count != 1 %}e{% endif %} wartet/warten noch auf einen Leistungsnachweis.</p></div>
    <a href="{% url 'resource-list' 'projects' %}">Alle Projekte →</a>
  </div>
  <div class="table-wrap clean">
    <table>
      <thead><tr><th>Projekt</th><th>Kunde</th><th>Status</th><th></th></tr></thead>
      <tbody>
      {% for project in pending_projects %}
        <tr>
          <td><b>{{ project.number }}</b><br><span class="muted">{{ project.title }}</span></td>
          <td>{{ project.customer.display_name }}</td>
          <td><span class="badge warning">Offen</span></td>
          <td class="row-actions">{% if can_create_reports %}<a href="{% url 'site-report-create' project.pk %}">Erstellen</a>{% else %}<a href="{% url 'project-detail' project.pk %}">Projekt</a>{% endif %}</td>
        </tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
</section>
{% endif %}
{% endblock %}
'''
Path("templates/erp/site_report_list.html").write_text(template, encoding="utf-8")


# Regression coverage: office sees the organization archive, while technicians
# only see reports from projects assigned to them.
test_path = Path("tests/test_workflow_release.py")
test_text = test_path.read_text(encoding="utf-8")
test_marker = "    def test_project_wizard_step_three_uses_grouped_project_and_team_sections(self):\n"
if "def test_leistungsnachweise_overview_lists_reports_and_respects_technician_scope" not in test_text:
    test_method = '''    def test_leistungsnachweise_overview_lists_reports_and_respects_technician_scope(self):
        assigned_report = SiteReport.objects.create(
            organization=self.org,
            project=self.project,
            employee=self.technician,
            kind=SiteReport.Kind.BANDO,
            title="B&O Leistungsnachweis",
            signed_name="Max Kunde",
            signed_at=timezone.now(),
            created_by=self.admin,
        )
        foreign_report = SiteReport.objects.create(
            organization=self.org,
            project=self.other_project,
            kind=SiteReport.Kind.GENERIC,
            title="Fremder Vor-Ort-Bericht",
            created_by=self.admin,
        )

        response = self.client.get(reverse("site-report-list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Leistungsnachweise")
        self.assertContains(response, self.project.number)
        self.assertContains(response, self.other_project.number)
        self.assertContains(response, reverse("site-report-pdf", args=[assigned_report.pk]))
        self.assertContains(response, reverse("site-report-pdf", args=[foreign_report.pk]))
        self.assertContains(response, "Max Kunde")

        response = self.tech_client.get(reverse("site-report-list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.project.number)
        self.assertNotContains(response, self.other_project.number)
        self.assertContains(response, reverse("site-report-pdf", args=[assigned_report.pk]))
        self.assertNotContains(response, reverse("site-report-pdf", args=[foreign_report.pk]))

'''
    if test_marker not in test_text:
        raise RuntimeError("Could not locate workflow test insertion point")
    test_path.write_text(test_text.replace(test_marker, test_method + test_marker, 1), encoding="utf-8")


# Build-time guards catch accidental removal of the route, sidebar link or view.
checks = {
    "erp/urls.py": 'name="site-report-list"',
    "templates/erp/base.html": "Leistungsnachweise</a>",
    "erp/workflow_views.py": "def site_report_list(request):",
    "templates/erp/site_report_list.html": "B&amp;O-Projekte ohne Leistungsnachweis",
    "tests/test_workflow_release.py": "test_leistungsnachweise_overview_lists_reports_and_respects_technician_scope",
}
for filename, marker in checks.items():
    if marker not in Path(filename).read_text(encoding="utf-8"):
        raise RuntimeError(f"Leistungsnachweise integration guard failed for {filename}")

print("Leistungsnachweise overview integration guard passed.")
