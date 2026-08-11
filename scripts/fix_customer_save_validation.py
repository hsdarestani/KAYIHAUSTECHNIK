from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "KAYI CUSTOMER SAVE VALIDATION FIX 2026-08-11"
VERSION = "20260811-4"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Missing customer-save target: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_backend() -> None:
    rel = "erp/rebuild_views.py"
    text = read(rel)
    old = '''@login_required
@require_http_methods(["GET", "POST"])
def customer_create(request):
    org = _org(request)
    form = CustomerForm(request.POST or None)
    location_form = ObjectLocationForm(request.POST or None, prefix="site")
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            customer = form.save(commit=False)
            customer.organization = org
            customer.number = _unique_number(m.Customer, org, "K")
            customer.save()
            if request.POST.get("site-street") and location_form.is_valid():
                location = location_form.save(commit=False)
                location.organization = org
                location.customer = customer
                location.save()
        messages.success(request, "Kunde wurde angelegt.")
        return redirect("next-customer-detail", pk=customer.pk)
    return render(request, "rebuild/customer_form.html", {"form": form, "location_form": location_form, "mode": "create"})
'''
    new = '''@login_required
@require_http_methods(["GET", "POST"])
def customer_create(request):
    org = _org(request)
    form = CustomerForm(request.POST or None)

    # The alternate job-site block is optional. Do not bind its ModelForm when
    # the user did not enter any site data; otherwise its required model fields
    # can create invisible validation errors inside a collapsed <details> block.
    site_field_names = tuple(ObjectLocationForm.base_fields.keys())
    location_requested = request.method == "POST" and any(
        str(request.POST.get(f"site-{name}") or "").strip() for name in site_field_names
    )
    location_form = ObjectLocationForm(request.POST if location_requested else None, prefix="site")

    if request.method == "POST":
        form_valid = form.is_valid()
        location_valid = location_form.is_valid() if location_requested else True
        if form_valid and location_valid:
            with transaction.atomic():
                customer = form.save(commit=False)
                customer.organization = org
                customer.number = _unique_number(m.Customer, org, "K")
                customer.save()
                if location_requested:
                    location = location_form.save(commit=False)
                    location.organization = org
                    location.customer = customer
                    location.save()
            messages.success(request, "Kunde wurde angelegt.")
            return redirect("next-customer-detail", pk=customer.pk)
        messages.error(request, "Kunde konnte nicht gespeichert werden. Bitte die markierten Felder prüfen.")

    return render(request, "rebuild/customer_form.html", {
        "form": form,
        "location_form": location_form,
        "location_requested": location_requested,
        "mode": "create",
    })
'''
    if new in text:
        return
    if old not in text:
        raise RuntimeError("Customer create backend anchor changed")
    write(rel, text.replace(old, new, 1))


def patch_template() -> None:
    rel = "templates/rebuild/customer_form.html"
    text = read(rel)
    old_open = '<form class="nx-form nx-customer-form" method="post" data-customer-form>{% csrf_token %}'
    new_open = '''<form class="nx-form nx-customer-form" method="post" data-customer-form novalidate>{% csrf_token %}
  {% if form.errors or location_form.errors %}
  <div class="nx-form-error-summary" data-form-error-summary role="alert" aria-live="assertive">
    <b>Kunde konnte nicht gespeichert werden.</b>
    <p>Bitte prüfe die markierten Felder. Es wurde noch kein Kunde angelegt.</p>
    <div class="nx-form-error-list">
      {% for field in form %}{% for error in field.errors %}<div><strong>{{ field.label }}:</strong> {{ error }}</div>{% endfor %}{% endfor %}
      {% for error in form.non_field_errors %}<div>{{ error }}</div>{% endfor %}
      {% for field in location_form %}{% for error in field.errors %}<div><strong>Einsatzort · {{ field.label }}:</strong> {{ error }}</div>{% endfor %}{% endfor %}
      {% for error in location_form.non_field_errors %}<div><strong>Einsatzort:</strong> {{ error }}</div>{% endfor %}
    </div>
  </div>
  {% endif %}'''
    if new_open not in text:
        if old_open not in text:
            raise RuntimeError("Customer form opening anchor changed")
        text = text.replace(old_open, new_open, 1)

    old_details = '<details class="nx-card nx-card-pad nx-progressive nx-location-progressive" data-location-details {% if location_form.errors %}open{% endif %}>'
    new_details = '<details class="nx-card nx-card-pad nx-progressive nx-location-progressive" data-location-details {% if location_requested or location_form.errors %}open{% endif %}>'
    if new_details not in text:
        if old_details not in text:
            raise RuntimeError("Customer location details anchor changed")
        text = text.replace(old_details, new_details, 1)

    js_anchor = '''  type?.addEventListener('change', syncCustomerType);
  syncCustomerType();
})();'''
    js_new = '''  type?.addEventListener('change', syncCustomerType);
  syncCustomerType();

  // Required controls inside collapsed <details> can make mobile Chromium abort
  // submission before Django receives the POST. The form uses server-side
  // validation as the source of truth and always surfaces errors visibly.
  const errorSummary = form.querySelector('[data-form-error-summary]');
  if (errorSummary) {
    requestAnimationFrame(() => errorSummary.scrollIntoView({block:'center', behavior:'smooth'}));
  }
})();'''
    if js_new not in text:
        if js_anchor not in text:
            raise RuntimeError("Customer form JavaScript anchor changed")
        text = text.replace(js_anchor, js_new, 1)
    write(rel, text)


def patch_styles() -> None:
    rel = "static/css/kayi-next.css"
    css = read(rel)
    if MARKER in css:
        return
    css += '''

/* KAYI CUSTOMER SAVE VALIDATION FIX 2026-08-11 */
.nx-form-error-summary {
  border: 1px solid rgba(185, 28, 28, .28);
  background: rgba(254, 226, 226, .72);
  border-radius: 14px;
  padding: 14px 16px;
  margin: 0 0 16px;
  font-size: 14px;
  line-height: 1.45;
}
.nx-form-error-summary > b { display: block; font-size: 15px; margin-bottom: 4px; }
.nx-form-error-summary > p { margin: 0 0 8px; }
.nx-form-error-list { display: grid; gap: 4px; }
.nx-customer-form .errorlist { margin: 6px 0 0; padding: 0; list-style: none; font-size: 13px; }
.nx-customer-form .errorlist li { margin: 0; }
'''
    write(rel, css)


def install_tests() -> None:
    rel = "tests/test_customer_save_validation.py"
    test = r'''from pathlib import Path

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from erp import rebuild_views
from erp.models import Customer, Organization, UserProfile


class CustomerSaveValidationRegressionTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="KAYI customer save regression")
        self.user = User.objects.create_user("customer-save-admin", password="safe-test-password")
        self.user.profile.organization = self.org
        self.user.profile.role = UserProfile.Role.ADMIN
        self.user.profile.save()
        self.client = Client()
        self.assertTrue(self.client.login(username="customer-save-admin", password="safe-test-password"))

    def _valid_customer_post(self):
        form = rebuild_views.CustomerForm()
        data = {}
        for name, field in form.fields.items():
            if not field.required:
                continue
            choices = list(getattr(field, "choices", []) or [])
            if choices:
                usable = [value for value, _label in choices if str(value) != ""]
                if usable:
                    data[name] = str(usable[0])
                    continue
            if "email" in name:
                data[name] = "mobile-save@test.de"
            elif "postal" in name:
                data[name] = "60311"
            elif "country" in name:
                data[name] = "DE"
            else:
                data[name] = "Test"
        data.setdefault("first_name", "Mobile")
        data.setdefault("last_name", "Save")
        data.setdefault("email", "mobile-save@test.de")
        return data

    def test_optional_collapsed_job_site_does_not_block_customer_save(self):
        data = self._valid_customer_post()
        response = self.client.post(reverse("next-customer-create"), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Customer.objects.filter(organization=self.org).count(), 1)

    def test_invalid_customer_returns_visible_error_summary_instead_of_silent_failure(self):
        response = self.client.post(reverse("next-customer-create"), {})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Kunde konnte nicht gespeichert werden.")
        self.assertContains(response, "data-form-error-summary")
        self.assertEqual(Customer.objects.filter(organization=self.org).count(), 0)

    def test_final_template_disables_browser_native_validation_for_progressive_form(self):
        root = Path(__file__).resolve().parents[1]
        template = (root / "templates/rebuild/customer_form.html").read_text(encoding="utf-8")
        backend = (root / "erp/rebuild_views.py").read_text(encoding="utf-8")
        self.assertIn("data-customer-form novalidate", template)
        self.assertIn("location_requested", backend)
        self.assertIn("Es wurde noch kein Kunde angelegt.", template)
'''
    write(rel, test)


def bump_cache() -> None:
    rel = "templates/rebuild/base.html"
    text = read(rel)
    # KAYI Next CSS is the asset modified by this fix; use a distinct version so
    # mobile browsers cannot retain the old progressive-form styling.
    import re
    updated = re.sub(r"(kayi-next\.css'\s*%\}\?v=)[^\"'\s<]+", rf"\g<1>{VERSION}", text)
    if updated == text and VERSION not in text:
        raise RuntimeError("Could not bump customer-save CSS cache version")
    write(rel, updated)


def guard() -> None:
    checks = {
        "erp/rebuild_views.py": ["location_requested", "site_field_names", "Kunde konnte nicht gespeichert werden"],
        "templates/rebuild/customer_form.html": ["data-customer-form novalidate", "data-form-error-summary", "Es wurde noch kein Kunde angelegt"],
        "static/css/kayi-next.css": [MARKER, ".nx-form-error-summary"],
        "tests/test_customer_save_validation.py": ["test_optional_collapsed_job_site_does_not_block_customer_save"],
    }
    missing = []
    for rel, markers in checks.items():
        text = read(rel)
        for marker in markers:
            if marker not in text:
                missing.append(f"{rel}: {marker}")
    if missing:
        raise RuntimeError("Customer-save validation guard failed: " + "; ".join(missing))


def main() -> None:
    patch_backend()
    patch_template()
    patch_styles()
    install_tests()
    bump_cache()
    guard()
    print("KAYI customer save validation: optional location no longer blocks submit and errors are visible.")


if __name__ == "__main__":
    main()
