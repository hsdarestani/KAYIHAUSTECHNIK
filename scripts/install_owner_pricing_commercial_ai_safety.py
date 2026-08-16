from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "overlays" / "owner_business_workflow"
MARKER = "A+Bau owner pricing + commercial workflow + non-destructive KI 2026-08-16"
VERSION = "20260816-owner-commercial-ai-safe-1"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Missing owner workflow target: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def copy_overlay(rel: str) -> None:
    source = OVERLAY / rel
    if not source.exists():
        raise RuntimeError(f"Missing owner workflow overlay: {rel}")
    target = ROOT / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def install_commercial_models() -> None:
    rel = "erp/models.py"
    text = read(rel)
    if "class ProjectCommercialSettings(" not in text:
        text += r'''

# A+Bau commercial defaults: kept separate from the legacy Project/Event schema so
# existing tenant data remains backward compatible while new ToolTime-like flows can
# persist project and appointment kalkulation settings.
from django.db import models as _ab_commercial_models


class ProjectCommercialSettings(_ab_commercial_models.Model):
    project = _ab_commercial_models.OneToOneField("Project", on_delete=_ab_commercial_models.CASCADE, related_name="commercial_settings")
    default_markup_percent = _ab_commercial_models.DecimalField(max_digits=7, decimal_places=2, default=20)
    hourly_rate = _ab_commercial_models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    pricing_mode = _ab_commercial_models.CharField(max_length=20, default="fixed")
    created_at = _ab_commercial_models.DateTimeField(auto_now_add=True)
    updated_at = _ab_commercial_models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Projektkalkulation"
        verbose_name_plural = "Projektkalkulationen"


class AppointmentCommercialSettings(_ab_commercial_models.Model):
    event = _ab_commercial_models.OneToOneField("CalendarEvent", on_delete=_ab_commercial_models.CASCADE, related_name="commercial_settings")
    markup_percent = _ab_commercial_models.DecimalField(max_digits=7, decimal_places=2, default=20)
    hourly_rate = _ab_commercial_models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    pricing_mode = _ab_commercial_models.CharField(max_length=20, default="fixed")
    created_at = _ab_commercial_models.DateTimeField(auto_now_add=True)
    updated_at = _ab_commercial_models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Terminkalkulation"
        verbose_name_plural = "Terminkalkulationen"
'''
        write(rel, text)

    migrations_dir = ROOT / "erp" / "migrations"
    migrations_dir.mkdir(parents=True, exist_ok=True)
    migration_name = "0999_ab_bau_commercial_workflow"
    migration_path = migrations_dir / f"{migration_name}.py"
    if not migration_path.exists():
        candidates = []
        for path in migrations_dir.glob("[0-9][0-9][0-9][0-9]_*.py"):
            if path.stem == migration_name:
                continue
            candidates.append(path.stem)
        dependency = sorted(candidates)[-1] if candidates else "0001_initial"
        migration_path.write_text(f'''from django.db import migrations, models\nimport django.db.models.deletion\n\n\nclass Migration(migrations.Migration):\n    dependencies = [("erp", "{dependency}")]\n    operations = [\n        migrations.CreateModel(\n            name="ProjectCommercialSettings",\n            fields=[\n                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),\n                ("default_markup_percent", models.DecimalField(decimal_places=2, default=20, max_digits=7)),\n                ("hourly_rate", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),\n                ("pricing_mode", models.CharField(default="fixed", max_length=20)),\n                ("created_at", models.DateTimeField(auto_now_add=True)),\n                ("updated_at", models.DateTimeField(auto_now=True)),\n                ("project", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="commercial_settings", to="erp.project")),\n            ],\n        ),\n        migrations.CreateModel(\n            name="AppointmentCommercialSettings",\n            fields=[\n                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),\n                ("markup_percent", models.DecimalField(decimal_places=2, default=20, max_digits=7)),\n                ("hourly_rate", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),\n                ("pricing_mode", models.CharField(default="fixed", max_length=20)),\n                ("created_at", models.DateTimeField(auto_now_add=True)),\n                ("updated_at", models.DateTimeField(auto_now=True)),\n                ("event", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="commercial_settings", to="erp.calendarevent")),\n            ],\n        ),\n    ]\n''', encoding="utf-8")


def install_price_management() -> None:
    for rel in (
        "erp/services/org_price_search.py",
        "erp/owner_business_views.py",
        "erp/owner_price_page.py",
        "templates/rebuild/owner_price_lists.html",
    ):
        copy_overlay(rel)

    rel = "erp/rebuild_urls.py"
    text = read(rel)
    import_block = "from . import owner_business_views as owner_business\nfrom . import owner_price_page as owner_price\n"
    if "owner_business_views as owner_business" not in text:
        anchor = "from . import rebuild_views as views\n"
        if anchor not in text:
            raise RuntimeError("Owner pricing URL import anchor changed")
        text = text.replace(anchor, anchor + import_block, 1)
    routes = [
        '    path("settings/next/preislisten/", owner_price.price_list_page, name="next-price-lists"),',
        '    path("settings/next/preislisten/upload/", owner_business.price_list_upload, name="next-price-list-upload"),',
        '    path("settings/next/preislisten/<int:pk>/toggle/", owner_business.price_list_toggle, name="next-price-list-toggle"),',
        '    path("pricing/search/", owner_business.organization_price_search, name="next-org-price-search"),',
    ]
    anchor = '    path("settings/next/", views.settings_page, name="next-settings"),\n'
    if anchor not in text:
        raise RuntimeError("Owner pricing settings route anchor changed")
    for route in routes:
        if route not in text:
            text = text.replace(anchor, route + "\n" + anchor, 1)
    write(rel, text)

    rel = "templates/rebuild/settings.html"
    text = read(rel)
    if "next-price-lists" not in text:
        card = '''\n<section class="nx-card nx-card-pad" style="margin-top:16px"><div class="nx-card-head" style="padding:0"><div><div class="nx-kicker">Kalkulation</div><h2>Eigene Preislisten</h2><p>CSV/XLSX pro Unternehmen importieren. Die Daten bleiben mandantenspezifisch und werden von Kalkulation und KI verwendet.</p></div><a class="nx-btn nx-btn-primary" href="{% url 'next-price-lists' %}">Preislisten verwalten →</a></div></section>\n'''
        text = text.replace("{% endblock %}", card + "{% endblock %}", 1)
        write(rel, text)

    rel = "templates/rebuild/document_editor.html"
    text = read(rel)
    text = text.replace("{% url 'next-bo-price-search' %}", "{% url 'next-org-price-search' %}")
    replacements = {
        "B&O ORIGINALPREISE": "EIGENE PREISLISTEN",
        "B&O-Position suchen": "Preislisten-Position suchen",
        "Direkt in der importierten VA04-Preisliste suchen. Nur Positionen mit echtem hinterlegtem Preis werden angezeigt.": "Direkt in den aktiven Preislisten dieses Unternehmens suchen. Nur Positionen mit hinterlegtem Preis werden angezeigt.",
        "A+Bau-Vorlagen mit Preis": "Schnellpositionen mit Preis",
        "Für B&O oben direkt in der Originalpreisliste suchen.": "Für weitere Positionen oben direkt in den aktiven Preislisten suchen.",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    write(rel, text)

    rel = "static/js/bo-direct-search.js"
    text = read(rel)
    for old, new in {
        "B&O-Preisliste wird durchsucht …": "Preislisten werden durchsucht …",
        "bepreiste B&O-Positionen gefunden": "bepreiste Preislisten-Positionen gefunden",
        "Keine bepreiste B&O-Position gefunden.": "Keine bepreiste Preislisten-Position gefunden.",
        "B&O-Suche hat keine gültige Serverantwort erhalten.": "Preislisten-Suche hat keine gültige Serverantwort erhalten.",
        "B&O-Suche fehlgeschlagen": "Preislisten-Suche fehlgeschlagen",
    }.items():
        text = text.replace(old, new)
    write(rel, text)

    # The deterministic scope planner must use the current tenant's active price
    # lists, not a hard-wired B&O subset. B&O remains just one possible source.
    rel = "erp/ai_scope_catalog.py"
    text = read(rel)
    text = text.replace("from erp.services.bo_direct_search import search_bo_prices, serialize_bo_price", "from erp.services.org_price_search import search_org_prices, serialize_org_price")
    text = text.replace("search_bo_prices(organization, query, limit=8)", "search_org_prices(organization, query, limit=8)")
    text = text.replace("serialize_bo_price(row)", "serialize_org_price(row)")
    text = text.replace("_best_bo_row", "_best_org_price_row")
    write(rel, text)


def patch_commercial_views() -> None:
    rel = "erp/rebuild_views.py"
    text = read(rel)
    if "def _commercial_decimal(" not in text:
        anchor = "\ndef _project_total(project):\n"
        helper = r'''

def _commercial_decimal(value, default=None):
    try:
        raw = str(value if value not in {None, ""} else (default if default is not None else "")).strip().replace(",", ".")
        return Decimal(raw) if raw else None
    except Exception:
        return Decimal(str(default)) if default is not None else None


def _project_commercial(project):
    if project is None:
        return None
    return m.ProjectCommercialSettings.objects.filter(project=project).first()

'''
        if anchor not in text:
            raise RuntimeError("Commercial helper anchor changed")
        text = text.replace(anchor, helper + anchor, 1)

    # Project creation: save the owner's commercial defaults and optionally continue
    # directly into the ToolTime-like appointment planning step.
    save_anchor = "        form.save_m2m()\n"
    project_at = text.find("def project_create(request):")
    save_at = text.find(save_anchor, project_at)
    if project_at < 0 or save_at < 0:
        raise RuntimeError("Project commercial save anchor changed")
    commercial_save = '''        form.save_m2m()\n        m.ProjectCommercialSettings.objects.update_or_create(\n            project=project,\n            defaults={\n                "default_markup_percent": _commercial_decimal(request.POST.get("commercial_markup_percent"), 20),\n                "hourly_rate": _commercial_decimal(request.POST.get("commercial_hourly_rate")),\n                "pricing_mode": (request.POST.get("commercial_pricing_mode") or "fixed")[:20],\n            },\n        )\n'''
    segment = text[project_at:text.find("\n\n@login_required", project_at + 20)]
    if "ProjectCommercialSettings.objects.update_or_create" not in segment:
        text = text[:save_at] + text[save_at:].replace(save_anchor, commercial_save, 1)
    old_redirect = '        return redirect("next-project-detail", pk=project.pk)\n'
    new_redirect = '        if request.POST.get("create_and_schedule") == "1":\n            return redirect(f"/appointments/new/?project={project.pk}")\n        return redirect("next-project-detail", pk=project.pk)\n'
    project_at = text.find("def project_create(request):")
    next_at = text.find("\n\n@login_required", project_at + 20)
    segment = text[project_at:next_at]
    if "create_and_schedule" not in segment and old_redirect in segment:
        text = text[:project_at] + segment.replace(old_redirect, new_redirect, 1) + text[next_at:]

    # Appointment planning inherits the project defaults but lets the owner adjust
    # the margin/pricing mode before the event is created.
    appointment_at = text.find("def appointment_create(request):")
    appointment_end = text.find("\n\n@login_required", appointment_at + 20)
    if appointment_at < 0 or appointment_end < 0:
        raise RuntimeError("Appointment commercial function anchor changed")
    segment = text[appointment_at:appointment_end]
    if "commercial_default_markup" not in segment:
        form_anchor = "    form = AppointmentForm(request.POST or None, organization=org, initial=initial)\n"
        if form_anchor not in segment:
            raise RuntimeError("Appointment form anchor changed")
        prefill = '''    project_for_commercial = None\n    project_id_for_commercial = request.POST.get("project") or request.GET.get("project")\n    if project_id_for_commercial:\n        project_for_commercial = m.Project.objects.filter(organization=org, pk=project_id_for_commercial).first()\n    project_commercial = _project_commercial(project_for_commercial)\n    commercial_default_markup = getattr(project_commercial, "default_markup_percent", Decimal("20"))\n    commercial_default_hourly = getattr(project_commercial, "hourly_rate", None)\n    commercial_default_mode = getattr(project_commercial, "pricing_mode", "fixed") or "fixed"\n'''
        segment = segment.replace(form_anchor, prefill + form_anchor, 1)
        save_anchor = "        form.save_m2m()\n"
        if save_anchor not in segment:
            raise RuntimeError("Appointment save anchor changed")
        save = '''        form.save_m2m()\n        m.AppointmentCommercialSettings.objects.update_or_create(\n            event=event,\n            defaults={\n                "markup_percent": _commercial_decimal(request.POST.get("commercial_markup_percent"), commercial_default_markup),\n                "hourly_rate": _commercial_decimal(request.POST.get("commercial_hourly_rate"), commercial_default_hourly),\n                "pricing_mode": (request.POST.get("commercial_pricing_mode") or commercial_default_mode or "fixed")[:20],\n            },\n        )\n'''
        segment = segment.replace(save_anchor, save, 1)
        render_old = '    return render(request, "rebuild/appointment_form.html", {"form": form})\n'
        render_new = '    return render(request, "rebuild/appointment_form.html", {"form": form, "commercial_markup": commercial_default_markup, "commercial_hourly_rate": commercial_default_hourly, "commercial_pricing_mode": commercial_default_mode})\n'
        if render_old not in segment:
            raise RuntimeError("Appointment render anchor changed")
        segment = segment.replace(render_old, render_new, 1)
        text = text[:appointment_at] + segment + text[appointment_end:]
    write(rel, text)

    rel = "erp/rebuild_projects.py"
    text = read(rel)
    if '"commercial_settings": commercial_settings' not in text:
        anchor = "    invoice_gross = sum((_invoice_total(invoice)[\"gross\"] for invoice in invoices), Decimal(\"0\"))\n"
        if anchor not in text:
            raise RuntimeError("Project detail commercial anchor changed")
        text = text.replace(anchor, anchor + "    commercial_settings = m.ProjectCommercialSettings.objects.filter(project=project).first()\n", 1)
        context_anchor = '        "invoice_gross": invoice_gross,\n'
        if context_anchor not in text:
            raise RuntimeError("Project detail context anchor changed")
        text = text.replace(context_anchor, context_anchor + '        "commercial_settings": commercial_settings,\n', 1)
        write(rel, text)


def patch_commercial_templates() -> None:
    rel = "templates/rebuild/project_form.html"
    text = read(rel)
    if "commercial_markup_percent" not in text:
        block = '''\n  <section class="nx-card nx-card-pad" data-commercial-project><div class="nx-card-head" style="padding:0 0 14px"><div><div class="nx-kicker">Kalkulation</div><h2>Wirtschaftliche Vorgaben</h2><p>Diese Werte werden beim nächsten Termin übernommen und können dort angepasst werden.</p></div></div><div class="nx-form-grid"><div class="nx-field"><label>Standard-Aufschlag %</label><input class="nx-control" type="number" min="-100" max="1000" step="0.01" name="commercial_markup_percent" value="20"><small class="nx-muted">Aufschlag auf den hinterlegten Einkaufs-/Leistungspreis.</small></div><div class="nx-field"><label>Preisart</label><select class="nx-control" name="commercial_pricing_mode"><option value="fixed">Festpreis</option><option value="estimate">Kostenschätzung / Budget</option><option value="hourly">Nach Aufwand</option></select></div><div class="nx-field"><label>Stundensatz € (optional)</label><input class="nx-control" type="number" min="0" step="0.01" name="commercial_hourly_rate" placeholder="z. B. 68,00"></div></div></section>\n'''
        anchor = "  <div class=\"nx-form-actions\">"
        if anchor not in text:
            raise RuntimeError("Project commercial template action anchor changed")
        text = text.replace(anchor, block + anchor, 1)
        old_button = '<button class="nx-btn nx-btn-accent" type="submit">Projekt anlegen →</button>'
        if old_button in text:
            text = text.replace(old_button, '<button class="nx-btn" type="submit">Nur Projekt anlegen</button><button class="nx-btn nx-btn-accent" type="submit" name="create_and_schedule" value="1">Projekt anlegen & Termin planen →</button>', 1)
        write(rel, text)

    rel = "templates/rebuild/appointment_form.html"
    text = read(rel)
    if "commercial_markup_percent" not in text:
        block = '''\n  <section class="nx-card nx-card-pad" data-commercial-appointment><div class="nx-card-head" style="padding:0 0 14px"><div><div class="nx-kicker">Kalkulation</div><h2>Preis & Aufschlag für diesen Einsatz</h2><p>Vom Projekt übernommen. Vor Terminfreigabe bewusst prüfen – nicht erst später in der Rechnung.</p></div></div><div class="nx-form-grid"><div class="nx-field"><label>Aufschlag %</label><input class="nx-control" type="number" min="-100" max="1000" step="0.01" name="commercial_markup_percent" value="{{ commercial_markup|default:'20' }}"></div><div class="nx-field"><label>Preisart</label><select class="nx-control" name="commercial_pricing_mode"><option value="fixed" {% if commercial_pricing_mode == 'fixed' %}selected{% endif %}>Festpreis</option><option value="estimate" {% if commercial_pricing_mode == 'estimate' %}selected{% endif %}>Kostenschätzung / Budget</option><option value="hourly" {% if commercial_pricing_mode == 'hourly' %}selected{% endif %}>Nach Aufwand</option></select></div><div class="nx-field"><label>Stundensatz € (optional)</label><input class="nx-control" type="number" min="0" step="0.01" name="commercial_hourly_rate" value="{{ commercial_hourly_rate|default_if_none:'' }}"></div></div></section>\n'''
        anchor = "  <div class=\"nx-form-actions\">"
        if anchor not in text:
            raise RuntimeError("Appointment commercial template action anchor changed")
        text = text.replace(anchor, block + anchor, 1)
        write(rel, text)

    rel = "templates/rebuild/project_detail.html"
    text = read(rel)
    if "data-project-commercial-summary" not in text:
        card = '''\n{% if not field_user %}<section class="nx-card nx-card-pad" data-project-commercial-summary style="margin-top:16px"><div class="nx-card-head" style="padding:0"><div><div class="nx-kicker">Kalkulation</div><h2>{% if commercial_settings %}{{ commercial_settings.default_markup_percent|floatformat:2 }} % Aufschlag{% else %}20,00 % Standard-Aufschlag{% endif %}</h2><p>{% if commercial_settings and commercial_settings.pricing_mode == 'hourly' %}Nach Aufwand{% elif commercial_settings and commercial_settings.pricing_mode == 'estimate' %}Kostenschätzung / Budget{% else %}Festpreis{% endif %}{% if commercial_settings.hourly_rate %} · {{ commercial_settings.hourly_rate|floatformat:2 }} € / h{% endif %}. Der nächste Termin übernimmt diese Werte.</p></div><a class="nx-btn nx-btn-primary" href="{% url 'next-appointment-create' %}?project={{ project.pk }}">Termin mit Kalkulation planen →</a></div></section>{% endif %}\n'''
        anchor = '<section class="nx-card nx-card-pad" style="margin-top:16px">'
        pos = text.find(anchor)
        if pos < 0:
            raise RuntimeError("Project detail commercial card anchor changed")
        text = text[:pos] + card + text[pos:]
        write(rel, text)


def patch_paint_dimensions() -> None:
    rel = "erp/ai_scope_planner.py"
    text = read(rel)
    if "def _extract_room_height(" not in text:
        anchor = "\ndef _extract_count(text: str, nouns: tuple[str, ...]) -> int | None:\n"
        helper = r'''

def _extract_room_height(text: str) -> Decimal | None:
    n = _norm(text)
    patterns = (
        r"(?:raumhohe|raumhoehe|deckenhohe|deckenhoehe|wandhohe|wandhoehe|hohe|hoehe)[^0-9]{0,25}(\d+(?:[.,]\d+)?)\s*(?:m|meter)\b",
        r"(\d+(?:[.,]\d+)?)\s*(?:m|meter)\b[^.;,\n]{0,25}(?:raumhohe|raumhoehe|deckenhohe|deckenhoehe|wandhohe|wandhoehe|hohe|hoehe)",
    )
    for pattern in patterns:
        match = re.search(pattern, n)
        if match:
            value = _number(match.group(1))
            if value is not None and Decimal("1.5") <= value <= Decimal("6"):
                return value
    return None


def _extract_room_lwh(text: str) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    n = _norm(text)
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*(?:m|meter)\b", n)
    if match:
        values = tuple(_number(match.group(i)) for i in (1, 2, 3))
        return values  # type: ignore[return-value]
    def named(names):
        name = "(?:" + "|".join(names) + ")"
        found = re.search(rf"{name}[^0-9]{{0,20}}(\d+(?:[.,]\d+)?)\s*(?:m|meter)\b", n)
        return _number(found.group(1)) if found else None
    return named(("lange", "laenge")), named(("breite",)), _extract_room_height(text)

'''
        if anchor not in text:
            raise RuntimeError("Painting dimension helper anchor changed")
        text = text.replace(anchor, helper + anchor, 1)

    fact_anchor = '    if floor is not None:\n        facts["floor_area"] = str(floor)\n'
    fact_new = fact_anchor + '''    room_height = _extract_room_height(message)\n    room_length, room_width, lwh_height = _extract_room_lwh(message)\n    if room_height is None:\n        room_height = lwh_height\n    if room_height is not None:\n        facts["room_height"] = str(room_height)\n    if room_length is not None:\n        facts["room_length"] = str(room_length)\n    if room_width is not None:\n        facts["room_width"] = str(room_width)\n'''
    if 'facts["room_height"]' not in text:
        if fact_anchor not in text:
            raise RuntimeError("Painting explicit fact anchor changed")
        text = text.replace(fact_anchor, fact_new, 1)

    old = '''    if wall_area is None and floor_area is not None and flags.get("paint_walls"):\n        wall_area = floor_area * WALL_AREA_FACTOR\n        wall_basis = f"{_fmt(floor_area)} m² Wohn-/Grundfläche × {_fmt(WALL_AREA_FACTOR)}"\n    elif wall_area is not None:\n'''
    new = '''    room_height = _area(facts, "room_height")\n    room_length = _area(facts, "room_length")\n    room_width = _area(facts, "room_width")\n    if wall_area is None and room_length is not None and room_width is not None and room_height is not None and flags.get("paint_walls"):\n        wall_area = Decimal("2") * (room_length + room_width) * room_height\n        wall_basis = f"2 × ({_fmt(room_length)} m + {_fmt(room_width)} m) × {_fmt(room_height)} m Raumhöhe"\n    elif wall_area is None and floor_area is not None and room_height is not None and flags.get("paint_walls"):\n        # Business heuristic requested for cases where only floor area + room height\n        # are known. If perimeter/L×B is available the geometrically stronger rule\n        # above takes precedence.\n        wall_area = floor_area * room_height\n        wall_basis = f"{_fmt(floor_area)} m² Grundfläche × {_fmt(room_height)} m Raumhöhe (Kalkulationsfaktor)"\n    elif wall_area is None and floor_area is not None and flags.get("paint_walls"):\n        wall_area = floor_area * WALL_AREA_FACTOR\n        wall_basis = f"{_fmt(floor_area)} m² Wohn-/Grundfläche × {_fmt(WALL_AREA_FACTOR)} Standardfaktor"\n    elif wall_area is not None:\n'''
    if "Kalkulationsfaktor" not in text:
        if old not in text:
            raise RuntimeError("Painting wall calculation anchor changed")
        text = text.replace(old, new, 1)

    # Make the derivation visible in the response, not just in hidden state.
    old_reply = '            parts.append(f"Wandfläche automatisch: {_fmt(floor)} m² × {_fmt(WALL_AREA_FACTOR)} = {_fmt(floor * WALL_AREA_FACTOR)} m².")\n'
    new_reply = '''            height = _area(facts, "room_height")\n            length = _area(facts, "room_length")\n            width = _area(facts, "room_width")\n            if length is not None and width is not None and height is not None:\n                calculated = Decimal("2") * (length + width) * height\n                parts.append(f"Wandfläche automatisch: 2 × ({_fmt(length)} m + {_fmt(width)} m) × {_fmt(height)} m = {_fmt(calculated)} m².")\n            elif height is not None:\n                parts.append(f"Wandfläche automatisch: {_fmt(floor)} m² Grundfläche × {_fmt(height)} m Raumhöhe = {_fmt(floor * height)} m².")\n            else:\n                parts.append(f"Wandfläche automatisch: {_fmt(floor)} m² × {_fmt(WALL_AREA_FACTOR)} Standardfaktor = {_fmt(floor * WALL_AREA_FACTOR)} m².")\n'''
    if "Standardfaktor =" not in text:
        if old_reply not in text:
            raise RuntimeError("Painting calculation reply anchor changed")
        text = text.replace(old_reply, new_reply, 1)
    write(rel, text)


def patch_non_destructive_ai_forms() -> None:
    rel = "static/js/kayi-next.js"
    text = read(rel)
    if "window.ABBauPreserveTypedText" not in text:
        helper = r'''

// A+Bau NON-DESTRUCTIVE KI FORM CONTRACT 2026-08-16
(() => {
  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (ch) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const isText = (field) => field && (field.tagName === 'TEXTAREA' || (field.tagName === 'INPUT' && !['checkbox','radio','file','hidden','date','datetime-local','time','number','range','color'].includes((field.type || 'text').toLowerCase())));
  const showSuggestion = (field, proposal) => {
    const host = field.closest('.nx-field') || field.parentElement;
    if (!host) return;
    let box = host.querySelector(':scope > .nx-ai-text-suggestion');
    if (!box) {
      box = document.createElement('div');
      box.className = 'nx-ai-text-suggestion';
      host.append(box);
    }
    const original = field.dataset.abOriginalTyped || field.value || '';
    if (!field.dataset.abOriginalTyped) field.dataset.abOriginalTyped = original;
    box.innerHTML = `<div class="nx-ai-text-label">KI-Vorschlag · deine Eingabe bleibt erhalten</div><div class="nx-ai-text-original"><b>Deine Eingabe</b><span>${esc(original)}</span></div><div class="nx-ai-text-proposal"><b>KI-Vorschlag</b><span>${esc(proposal)}</span></div><div class="nx-actions"><button type="button" class="nx-btn nx-btn-ghost" data-ai-append>Anhängen</button><button type="button" class="nx-btn" data-ai-accept>Vorschlag übernehmen</button></div>`;
    box.querySelector('[data-ai-append]')?.addEventListener('click', () => {
      const current = field.value || '';
      field.value = current ? `${current}\n${proposal}` : proposal;
      field.dispatchEvent(new Event('input',{bubbles:true}));
      field.dispatchEvent(new Event('change',{bubbles:true}));
      field.dataset.abUserOwned = '1';
    });
    box.querySelector('[data-ai-accept]')?.addEventListener('click', () => {
      field.value = proposal;
      field.dispatchEvent(new Event('input',{bubbles:true}));
      field.dispatchEvent(new Event('change',{bubbles:true}));
      field.dataset.abUserOwned = '1';
      box.classList.add('is-accepted');
    });
  };
  document.addEventListener('input', (event) => {
    const field = event.target;
    if (!event.isTrusted || !isText(field)) return;
    field.dataset.abUserOwned = '1';
    if (!field.dataset.abOriginalTyped && String(field.value || '').trim()) field.dataset.abOriginalTyped = field.value;
  }, true);
  window.ABBauPreserveTypedText = (field, proposal) => {
    if (!isText(field)) return false;
    const current = String(field.value || '');
    if (!current.trim() && field.dataset.abUserOwned !== '1') return false;
    if (current === String(proposal ?? '')) return true;
    showSuggestion(field, String(proposal ?? ''));
    return true;
  };
})();
'''
        text += helper

    old = "        if (field.type === 'checkbox') field.checked = /^(1|true|ja|yes)$/i.test(action.value || '');\n        else field.value = action.value ?? '';\n"
    new = "        if (field.type === 'checkbox') field.checked = /^(1|true|ja|yes)$/i.test(action.value || '');\n        else { const proposed = action.value ?? ''; if (window.ABBauPreserveTypedText?.(field, proposed)) continue; field.value = proposed; }\n"
    if "ABBAuPreserveTypedText?.(field, proposed)" not in text:
        if old not in text:
            raise RuntimeError("Non-destructive AI set_field anchor changed")
        text = text.replace(old, new, 1)
    write(rel, text)

    rel = "static/css/kayi-next.css"
    text = read(rel)
    if ".nx-ai-text-suggestion" not in text:
        text += r'''

/* Non-destructive KI suggestions: typed user text is never silently replaced. */
.nx-ai-text-suggestion{margin-top:8px;padding:10px;border:1px solid var(--nx-line,#ddd8ce);border-radius:12px;background:rgba(173,137,43,.06);display:grid;gap:8px}
.nx-ai-text-label{font-size:11px;font-weight:800;color:var(--nx-muted,#6f747a);text-transform:uppercase;letter-spacing:.04em}
.nx-ai-text-original,.nx-ai-text-proposal{display:grid;gap:3px;font-size:12px;line-height:1.45;white-space:pre-wrap}
.nx-ai-text-original{padding:7px 9px;border-radius:9px;background:rgba(0,0,0,.035)}
.nx-ai-text-original b,.nx-ai-text-proposal b{font-size:11px}
.nx-ai-text-suggestion.is-accepted .nx-ai-text-original{border-left:3px solid #ad892b}
'''
        write(rel, text)


def install_tests() -> None:
    rel = "tests/test_owner_pricing_commercial_ai_safety.py"
    write(rel, r'''from pathlib import Path
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from erp import models as m
from erp.ai_scope_planner import plan_scope_message
from erp.services.org_price_search import search_org_prices


class Session(dict):
    modified = False


class OwnerWorkflowContractTests(SimpleTestCase):
    def test_owner_price_upload_is_org_scoped_and_wired(self):
        view = Path("erp/owner_business_views.py").read_text(encoding="utf-8")
        urls = Path("erp/rebuild_urls.py").read_text(encoding="utf-8")
        settings = Path("templates/rebuild/settings.html").read_text(encoding="utf-8")
        self.assertIn("organization=org", view)
        self.assertIn("next-price-list-upload", urls)
        self.assertIn("next-org-price-search", urls)
        self.assertIn("next-price-lists", settings)

    def test_project_to_appointment_has_commercial_step(self):
        project = Path("templates/rebuild/project_form.html").read_text(encoding="utf-8")
        appointment = Path("templates/rebuild/appointment_form.html").read_text(encoding="utf-8")
        views = Path("erp/rebuild_views.py").read_text(encoding="utf-8")
        self.assertIn("commercial_markup_percent", project)
        self.assertIn("Projekt anlegen & Termin planen", project)
        self.assertIn("commercial_markup_percent", appointment)
        self.assertIn("AppointmentCommercialSettings.objects.update_or_create", views)

    def test_ai_never_silently_replaces_non_empty_typed_text(self):
        js = Path("static/js/kayi-next.js").read_text(encoding="utf-8")
        css = Path("static/css/kayi-next.css").read_text(encoding="utf-8")
        self.assertIn("window.ABBauPreserveTypedText", js)
        self.assertIn("deine Eingabe bleibt erhalten", js)
        self.assertIn("ABBAuPreserveTypedText?.(field, proposed)", js)
        self.assertIn(".nx-ai-text-original", css)

    def test_painting_uses_explicit_height_and_geometric_dimensions(self):
        result = plan_scope_message("Wohnung 90 qm, alle Wände streichen, Raumhöhe 2,5 m", Session(), [])
        by_key = {item["key"]: item for item in result["scope_items"]}
        self.assertEqual(by_key["paint.wall.primer"]["quantity_display"], "225")
        self.assertIn("Raumhöhe", by_key["paint.wall.primer"]["basis"])
        geometric = plan_scope_message("Raum 4 x 5 x 2,5 m, alle Wände streichen", Session(), [])
        by_key = {item["key"]: item for item in geometric["scope_items"]}
        self.assertEqual(by_key["paint.wall.coat"]["quantity_display"], "45")


class OrganizationPriceIsolationTests(TestCase):
    def test_search_never_crosses_tenants(self):
        org_a = m.Organization.objects.create(name="Firma A")
        org_b = m.Organization.objects.create(name="Firma B")
        source_a = m.PriceSource.objects.create(organization=org_a, name="Liste A", active=True)
        source_b = m.PriceSource.objects.create(organization=org_b, name="Liste B", active=True)
        m.PriceItem.objects.create(organization=org_a, source=source_a, code="A-1", description="Wände grundieren", unit="m²", sales_price=Decimal("2.50"))
        m.PriceItem.objects.create(organization=org_b, source=source_b, code="B-1", description="Wände grundieren", unit="m²", sales_price=Decimal("99.00"))
        rows = search_org_prices(org_a, "Wände grundieren")
        self.assertEqual([row.organization_id for row in rows], [org_a.pk])
        self.assertEqual(rows[0].code, "A-1")
''')


def bump_cache() -> None:
    rel = "templates/rebuild/base.html"
    text = read(rel)
    text = re.sub(r"(kayi-next\.(?:css|js)'\s*%\}\?v=)[^\"'\s<]+", rf"\g<1>{VERSION}", text)
    write(rel, text)
    rel = "templates/rebuild/document_editor.html"
    text = read(rel)
    text = re.sub(r"(bo-direct-search\.js'\s*%\}\?v=)[^\"'\s<]+", rf"\g<1>{VERSION}", text)
    write(rel, text)


def guard() -> None:
    checks = {
        "erp/models.py": ["ProjectCommercialSettings", "AppointmentCommercialSettings"],
        "erp/owner_business_views.py": ["price_list_upload", "organization_price_search", "organization=org"],
        "erp/services/org_price_search.py": ["search_org_prices", "source__active=True"],
        "erp/rebuild_urls.py": ["next-price-lists", "next-price-list-upload", "next-org-price-search"],
        "templates/rebuild/owner_price_lists.html": ["Preisliste hochladen", "mandantenspezifisch"],
        "templates/rebuild/project_form.html": ["commercial_markup_percent", "Projekt anlegen & Termin planen"],
        "templates/rebuild/appointment_form.html": ["commercial_markup_percent", "Preis & Aufschlag"],
        "erp/rebuild_views.py": ["ProjectCommercialSettings.objects.update_or_create", "AppointmentCommercialSettings.objects.update_or_create"],
        "erp/ai_scope_planner.py": ["_extract_room_height", "Kalkulationsfaktor", "Standardfaktor"],
        "static/js/kayi-next.js": ["window.ABBauPreserveTypedText", "deine Eingabe bleibt erhalten"],
        "tests/test_owner_pricing_commercial_ai_safety.py": ["test_search_never_crosses_tenants", "test_painting_uses_explicit_height"],
        "templates/rebuild/base.html": [VERSION],
    }
    missing = []
    for rel, needles in checks.items():
        text = read(rel)
        for needle in needles:
            if needle not in text:
                missing.append(f"{rel}: {needle}")
    migration = ROOT / "erp" / "migrations" / "0999_ab_bau_commercial_workflow.py"
    if not migration.exists():
        missing.append("commercial migration")
    if missing:
        raise RuntimeError("Owner/commercial/AI safety guard failed: " + "; ".join(missing))


def main() -> None:
    install_commercial_models()
    install_price_management()
    patch_commercial_views()
    patch_commercial_templates()
    patch_paint_dimensions()
    patch_non_destructive_ai_forms()
    install_tests()
    bump_cache()
    guard()
    print("A+Bau owner pricing, tenant-safe price search, ToolTime-like project/Termin commercial defaults, dimension-aware painting math and non-destructive KI forms installed.")


if __name__ == "__main__":
    main()
