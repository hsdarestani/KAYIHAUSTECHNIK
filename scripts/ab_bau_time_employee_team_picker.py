from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TIME EMPLOYEE + TEAM PICKER 2026-08-12"
ASSET_VERSION = "20260811-101"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"A+Bau team/time target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_time_employee_resolution() -> None:
    rel = "erp/field_authorization_views.py"
    text = read(rel)

    helper = r'''

def _employee_identity_matches(user, employee):
    if getattr(employee, "user_id", None) == getattr(user, "id", None):
        return True
    user_email = (getattr(user, "email", "") or "").strip().lower()
    employee_email = (getattr(employee, "email", "") or "").strip().lower()
    if user_email and employee_email and user_email == employee_email:
        return True
    user_name = " ".join(part for part in [getattr(user, "first_name", ""), getattr(user, "last_name", "")] if part).strip().casefold()
    employee_name = " ".join(part for part in [getattr(employee, "first_name", ""), getattr(employee, "last_name", "")] if part).strip().casefold()
    return bool(user_name and employee_name and user_name == employee_name)


def _next_user_employee_number(org, user):
    base = f"USR-{getattr(user, 'pk', 0):05d}"
    number = base
    suffix = 1
    while m.Employee.objects.filter(organization=org, employee_number=number).exists():
        suffix += 1
        number = f"{base}-{suffix}"
    return number


def _resolve_time_employee(request, org, event=None):
    """Resolve the authenticated person to an Employee without guessing another person's time.

    Existing explicit user/email links win. For a project appointment we may also
    accept an attendee/manager/member whose identity exactly matches the current
    user's name or email. Office/admin users are finally auto-provisioned as their
    own Employee record so owners can track their own work even when the account
    was created before Employee profiles existed.
    """
    employee = _employee(request, org)
    if employee is not None:
        return employee

    employee = m.Employee.objects.filter(organization=org, user=request.user, active=True).first()
    if employee is not None:
        return employee

    email = (getattr(request.user, "email", "") or "").strip()
    if email:
        employee = m.Employee.objects.filter(organization=org, email__iexact=email, active=True).first()
        if employee is not None:
            if getattr(employee, "user_id", None) is None:
                employee.user = request.user
                employee.save(update_fields=["user", "updated_at"])
            return employee

    if event is not None and event.project_id:
        candidates = list(event.attendees.filter(active=True))
        if event.project.manager_id:
            candidates.append(event.project.manager)
        candidates.extend(list(event.project.members.filter(active=True)))
        seen = set()
        for candidate in candidates:
            if candidate is None or candidate.pk in seen:
                continue
            seen.add(candidate.pk)
            if _employee_identity_matches(request.user, candidate):
                if getattr(candidate, "user_id", None) is None:
                    candidate.user = request.user
                    candidate.save(update_fields=["user", "updated_at"])
                return candidate

    if _is_field_user(request):
        return None

    # Owners/office/admin users may legitimately work on-site themselves. Give
    # them their own auditable employee identity rather than attributing time to
    # some arbitrary project member.
    defaults = {
        "employee_number": _next_user_employee_number(org, request.user),
        "first_name": (getattr(request.user, "first_name", "") or getattr(request.user, "username", "") or "Benutzer")[:120],
        "last_name": (getattr(request.user, "last_name", "") or "")[:120],
        "email": email[:200],
        "active": True,
    }
    employee, _created = m.Employee.objects.get_or_create(
        organization=org,
        user=request.user,
        defaults=defaults,
    )
    return employee
'''
    if "def _resolve_time_employee(request, org, event=None):" not in text:
        anchor = "\n\ndef _doc_image_payload(document):\n"
        if anchor not in text:
            raise RuntimeError("Could not locate field employee helper insertion point")
        text = text.replace(anchor, helper + anchor, 1)

    text = text.replace(
        "    employee = _employee(request, org)\n    running = None\n",
        "    employee = _resolve_time_employee(request, org, event)\n    running = None\n",
        1,
    )
    old_toggle = "    employee = _employee(request, org)\n    if employee is None or event.project_id is None:\n        return JsonResponse({\"ok\": False, \"error\": \"Mitarbeiter oder Projekt fehlt.\"}, status=400)\n"
    new_toggle = "    employee = _resolve_time_employee(request, org, event)\n    if employee is None or event.project_id is None:\n        return JsonResponse({\"ok\": False, \"error\": \"Für dieses Benutzerkonto konnte kein Mitarbeiterprofil ermittelt werden. Bitte Teamzuordnung prüfen.\"}, status=400)\n"
    if new_toggle not in text:
        if old_toggle not in text:
            raise RuntimeError("Could not locate gated time employee resolution")
        text = text.replace(old_toggle, new_toggle, 1)

    write(rel, text)


def patch_project_team_picker() -> None:
    rel = "static/js/kayi-next.js"
    js = read(rel)
    if "A+BAU PROJECT TEAM PICKER" not in js:
        js += r'''

  // A+BAU PROJECT TEAM PICKER 2026-08-12
  (() => {
    const select = document.querySelector('.nx-project-form select[name="members"]');
    if (!select || select.dataset.abTeamEnhanced === '1') return;
    select.dataset.abTeamEnhanced = '1';
    select.classList.add('ab-team-native');
    const field = select.closest('.nx-field');
    if (!field) return;
    const label = field.querySelector(':scope > label');
    if (label) label.textContent = 'Projektteam';

    const picker = document.createElement('div');
    picker.className = 'ab-team-picker';
    picker.innerHTML = `
      <div class="ab-team-picker-head">
        <div><strong>Mitarbeiter auswählen</strong><small>Mehrere Personen sind möglich. Klicke auf eine Karte zum Auswählen.</small></div>
        <button type="button" class="ab-team-clear">Auswahl löschen</button>
      </div>
      <div class="ab-team-selected" aria-live="polite"></div>
      <label class="ab-team-search"><span>⌕</span><input type="search" placeholder="Mitarbeiter suchen …" autocomplete="off"></label>
      <div class="ab-team-list"></div>`;
    select.after(picker);

    const list = picker.querySelector('.ab-team-list');
    const selected = picker.querySelector('.ab-team-selected');
    const search = picker.querySelector('.ab-team-search input');
    const clear = picker.querySelector('.ab-team-clear');
    const cards = [];

    const initials = (label) => label.trim().split(/\s+/).slice(0,2).map((part)=>part[0]||'').join('').toUpperCase() || 'MA';
    const refresh = () => {
      let count = 0;
      cards.forEach(({option, card, check}) => {
        card.classList.toggle('is-selected', option.selected);
        check.textContent = option.selected ? '✓' : '';
        if (option.selected) count += 1;
      });
      selected.innerHTML = '';
      const chosen = Array.from(select.selectedOptions);
      if (!chosen.length) {
        selected.innerHTML = '<span class="ab-team-empty">Noch niemand ausgewählt</span>';
      } else {
        chosen.forEach((option) => {
          const chip = document.createElement('button');
          chip.type = 'button'; chip.className = 'ab-team-chip';
          chip.innerHTML = `<span>${initials(option.textContent)}</span>${option.textContent}<b>×</b>`;
          chip.addEventListener('click', () => { option.selected = false; select.dispatchEvent(new Event('change',{bubbles:true})); refresh(); });
          selected.appendChild(chip);
        });
      }
      picker.dataset.selectedCount = String(count);
    };

    Array.from(select.options).forEach((option) => {
      if (!option.value) return;
      const card = document.createElement('button');
      card.type = 'button'; card.className = 'ab-team-card';
      card.dataset.search = option.textContent.toLocaleLowerCase('de-DE');
      card.innerHTML = `<span class="ab-team-avatar">${initials(option.textContent)}</span><span class="ab-team-person"><strong></strong><small>Als Teammitglied hinzufügen</small></span><span class="ab-team-check"></span>`;
      card.querySelector('.ab-team-person strong').textContent = option.textContent;
      const check = card.querySelector('.ab-team-check');
      card.addEventListener('click', () => { option.selected = !option.selected; select.dispatchEvent(new Event('change',{bubbles:true})); refresh(); });
      list.appendChild(card); cards.push({option, card, check});
    });

    search.addEventListener('input', () => {
      const query = search.value.trim().toLocaleLowerCase('de-DE');
      cards.forEach(({card}) => { card.hidden = !!query && !card.dataset.search.includes(query); });
    });
    clear.addEventListener('click', () => {
      Array.from(select.options).forEach((option) => { option.selected = false; });
      select.dispatchEvent(new Event('change',{bubbles:true})); refresh();
    });
    select.addEventListener('change', refresh);
    refresh();
  })();
'''
        write(rel, js)

    rel = "static/css/kayi-next.css"
    css = read(rel)
    if MARKER not in css:
        css += r'''

/* A+BAU TIME EMPLOYEE + TEAM PICKER 2026-08-12 */
.nx-project-form .ab-team-native {
  position:absolute!important;width:1px!important;height:1px!important;opacity:0!important;pointer-events:none!important;overflow:hidden!important;
}
.nx-project-form .ab-team-picker{border:1px solid #ddd8cc;border-radius:16px;background:#fbfaf7;padding:14px;display:grid;gap:12px}
.ab-team-picker-head{display:flex;align-items:center;justify-content:space-between;gap:14px}
.ab-team-picker-head>div{display:grid;gap:3px}.ab-team-picker-head strong{font-size:14px}.ab-team-picker-head small{color:#6b6f76;font-size:12px}
.ab-team-clear{border:0;background:transparent;color:#8a6820;font-weight:800;font-size:12px;cursor:pointer;padding:7px 8px;border-radius:9px}.ab-team-clear:hover{background:#f2ead7}
.ab-team-selected{display:flex;gap:7px;flex-wrap:wrap;min-height:32px;align-items:center}
.ab-team-empty{font-size:12px;color:#8a8d93;background:#f0efeb;border-radius:999px;padding:7px 10px}
.ab-team-chip{border:1px solid #d8bd76;background:#fff8e8;border-radius:999px;padding:5px 8px 5px 5px;display:flex;align-items:center;gap:6px;font-weight:750;font-size:12px;cursor:pointer;color:#2b2c2f}
.ab-team-chip>span{width:23px;height:23px;border-radius:50%;display:grid;place-items:center;background:#c9a13b;color:#111;font-size:9px;font-weight:900}.ab-team-chip b{font-size:14px;color:#8a6820}
.ab-team-search{height:42px;border:1px solid #d8d4ca;background:#fff;border-radius:12px;display:flex;align-items:center;gap:8px;padding:0 11px}.ab-team-search span{color:#8a8d93}.ab-team-search input{border:0!important;outline:0!important;background:transparent!important;box-shadow:none!important;width:100%;height:38px!important;padding:0!important}
.ab-team-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;max-height:280px;overflow:auto;padding:1px}
.ab-team-card{border:1px solid #ddd8cc;background:#fff;border-radius:13px;padding:10px;display:grid;grid-template-columns:38px 1fr 24px;gap:10px;align-items:center;text-align:left;cursor:pointer;color:#242529;min-width:0}
.ab-team-card:hover{border-color:#c9a13b;background:#fffdf7}.ab-team-card.is-selected{border-color:#c9a13b;background:#fff8e6;box-shadow:0 0 0 1px rgba(201,161,59,.12)}
.ab-team-avatar{width:38px;height:38px;border-radius:11px;background:#f0eee8;display:grid;place-items:center;font-size:11px;font-weight:900;color:#54575d}.ab-team-card.is-selected .ab-team-avatar{background:#c9a13b;color:#111}
.ab-team-person{display:grid;gap:3px;min-width:0}.ab-team-person strong{font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ab-team-person small{font-size:10px;color:#85888e}
.ab-team-check{width:21px;height:21px;border:1.5px solid #c9c6bd;border-radius:7px;display:grid;place-items:center;font-weight:900;color:#111}.ab-team-card.is-selected .ab-team-check{background:#c9a13b;border-color:#c9a13b}
@media(max-width:700px){.ab-team-picker-head{align-items:flex-start;flex-direction:column}.ab-team-list{grid-template-columns:1fr;max-height:320px}.ab-team-clear{padding-left:0}.nx-project-form .ab-team-picker{padding:12px}}
'''
        write(rel, css)

    base_rel = "templates/rebuild/base.html"
    base = read(base_rel)
    base = re.sub(r"(kayi-next\.css' %\}\?v=)[^\"']+", rf"\g<1>{ASSET_VERSION}", base)
    base = re.sub(r"(kayi-next\.js' %\}\?v=)[^\"']+", rf"\g<1>{ASSET_VERSION}", base)
    write(base_rel, base)


def install_tests() -> None:
    write("tests/test_ab_bau_time_employee_team_picker.py", r'''from pathlib import Path

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from erp.models import CalendarEvent, Customer, Document, Employee, Organization, Project, UserProfile
from erp.services.numbering import next_number

ROOT = Path(__file__).resolve().parents[1]


class ABBauTimeEmployeeResolutionTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="A+Bau time fallback")
        self.user = User.objects.create_user("owner-without-employee", password="pass123", email="owner@example.com", first_name="Olaf", last_name="Owner")
        self.user.profile.organization = self.org
        self.user.profile.role = UserProfile.Role.ADMIN
        self.user.profile.save()
        self.customer = Customer.objects.create(organization=self.org, number=next_number(self.org, "customer"), company="Zeitkunde")
        self.project = Project.objects.create(organization=self.org, number=next_number(self.org, "project"), title="Zeitprojekt", customer=self.customer, status="confirmed")
        self.event = CalendarEvent.objects.create(organization=self.org, project=self.project, title="Einsatz", type="site", starts_at="2026-08-12T10:00:00+00:00", ends_at="2026-08-12T11:00:00+00:00", created_by=self.user)
        # A signed authorization is enough for the gated timer. The timer must not
        # fail merely because this older owner account has no Employee row yet.
        Document.objects.create(organization=self.org, project=self.project, customer=self.customer, title="Freigabe", category="contract", mime_type="application/pdf", metadata={"kind":"field_authorization","event_id":self.event.pk,"status":"signed"})
        self.client = Client(); self.client.login(username="owner-without-employee", password="pass123")

    def test_owner_without_employee_is_provisioned_for_time_tracking(self):
        response = self.client.post(reverse("next-time-toggle", args=[self.event.pk]))
        self.assertEqual(response.status_code, 200, response.content)
        employee = Employee.objects.get(organization=self.org, user=self.user)
        self.assertTrue(employee.active)
        self.assertEqual(response.json()["state"], "running")


class ABBauProjectTeamPickerContractTests(TestCase):
    def test_project_team_uses_clear_card_picker(self):
        js = (ROOT / "static/js/kayi-next.js").read_text(encoding="utf-8")
        css = (ROOT / "static/css/kayi-next.css").read_text(encoding="utf-8")
        for marker in ("A+BAU PROJECT TEAM PICKER", "Mitarbeiter auswählen", "Noch niemand ausgewählt", "ab-team-card"):
            self.assertIn(marker, js)
        self.assertIn("A+BAU TIME EMPLOYEE + TEAM PICKER", css)
        self.assertIn(".ab-team-list", css)
''')


def guard() -> None:
    views = read("erp/field_authorization_views.py")
    js = read("static/js/kayi-next.js")
    css = read("static/css/kayi-next.css")
    for marker in ("_resolve_time_employee", "_next_user_employee_number", "Für dieses Benutzerkonto konnte kein Mitarbeiterprofil"):
        if marker not in views:
            raise RuntimeError(f"Time employee resolution contract missing: {marker}")
    for marker in ("A+BAU PROJECT TEAM PICKER", "Mitarbeiter auswählen", "ab-team-card"):
        if marker not in js:
            raise RuntimeError(f"Project team picker JS contract missing: {marker}")
    if MARKER not in css:
        raise RuntimeError("Project team picker styles missing")


def main() -> None:
    patch_time_employee_resolution()
    patch_project_team_picker()
    install_tests()
    guard()
    print("A+Bau time employee resolution and understandable project team picker installed.")


if __name__ == "__main__":
    main()
