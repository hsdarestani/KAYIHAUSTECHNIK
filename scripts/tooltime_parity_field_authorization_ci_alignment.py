from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU ANGEBOT/FREIGABE CI ALIGNMENT 2026-09-08"
LAYOUT_MARKER = "A+BAU TERMIN FREIGABE LAYOUT HOTFIX 2026-09-09"
LAYOUT_VERSION = "20260909-termin-layout-1"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"CI alignment target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# The final dashboard-action layer owns this global cache key. Keep its version
# prefix intact, but add a suffix so browsers fetch the finance stylesheet after
# the Termin-only document-page selector correction below.
base_rel = "templates/rebuild/base.html"
base = read(base_rel)
base, count = re.subn(
    r"ab-bau-v3-finance-mobile-pdf-hotfix\.css\?v=[^\"'\s<]+",
    "ab-bau-v3-finance-mobile-pdf-hotfix.css?v=20260908-dashboard-actions-1-fa-layout-1",
    base,
    count=1,
)
if count != 1:
    raise RuntimeError("Final finance/mobile/PDF stylesheet cache-key anchor missing")


# PR #184 deliberately reuses .tt-document-form so the canonical Angebot runtime
# owns position calculations/submission. The V3 finance visual layer also used that
# class as a *page type* detector, which made a Termin detail look like Document
# Studio. Exclude the field authorization form from those page-level selectors;
# form-local ToolTime styles remain active and the pricing logic is untouched.
finance_css_rel = "static/css/ab-bau-v3-finance-mobile-pdf-hotfix.css"
finance_css = read(finance_css_rel)
legacy_page_selector = "body.ab-apex:has(.tt-document-form)"
safe_page_selector = "body.ab-apex:has(.tt-document-form:not(.tt-field-auth-form))"
finance_css = finance_css.replace(legacy_page_selector, safe_page_selector)
if legacy_page_selector in finance_css:
    raise RuntimeError("Termin still triggers global Document Studio page selectors")
if safe_page_selector not in finance_css:
    raise RuntimeError("Document Studio selector isolation anchor missing")
write(finance_css_rel, finance_css)


# The Angebot editor is intentionally dense on a full commercial-document canvas.
# Inside the narrower Termin/Freigabe card, give the same fields a dedicated,
# readable layout instead of shrinking fourteen controls into one line.
layout_css = r'''/* A+BAU TERMIN FREIGABE LAYOUT HOTFIX 2026-09-09 */
body.ab-apex .tt-field-auth-form{
  width:100%;max-width:100%;min-width:0;box-sizing:border-box;
  display:grid!important;gap:18px!important;
}
body.ab-apex .tt-field-auth-form *,body.ab-apex .tt-field-auth-form *:before,body.ab-apex .tt-field-auth-form *:after{box-sizing:border-box}
body.ab-apex .tt-field-auth-form>*,body.ab-apex .tt-field-auth-form .fa-block,body.ab-apex .tt-field-auth-form .fa-angebot-pricing,
body.ab-apex .tt-field-auth-form .tt-services,body.ab-apex .tt-field-auth-form .tt-service-group,
body.ab-apex .tt-field-auth-form [data-group-body],body.ab-apex .tt-field-auth-form .tt-authorization-calculation{min-width:0;max-width:100%}

body.ab-apex .tt-field-auth-form .fa-angebot-pricing{
  margin:0!important;padding:18px!important;border:1px solid var(--apex-line,#ded8cc)!important;
  border-radius:18px!important;background:#fffefa!important;box-shadow:0 10px 28px rgba(16,18,21,.045)!important;
}
body.ab-apex .tt-field-auth-form .fa-block-head{margin-bottom:12px!important}
body.ab-apex .tt-field-auth-form .fa-block-head>div{display:grid;gap:4px}
body.ab-apex .tt-field-auth-form .fa-block-head b{font-size:14px;line-height:1.25;color:#1f2226}
body.ab-apex .tt-field-auth-form .fa-block-head small{font-size:11px;line-height:1.45;color:#777168}
body.ab-apex .tt-field-auth-form .fa-price-mode{display:grid!important;grid-template-columns:repeat(3,minmax(0,1fr))!important;gap:7px!important;margin:0 0 16px!important}
body.ab-apex .tt-field-auth-form .fa-price-mode label,body.ab-apex .tt-field-auth-form .fa-price-mode span{min-width:0}
body.ab-apex .tt-field-auth-form .fa-price-mode span{min-height:38px!important;padding:8px 10px!important;display:flex!important;align-items:center!important;justify-content:center!important;text-align:center!important;line-height:1.2!important}

body.ab-apex .tt-field-auth-form .tt-services{
  width:100%!important;margin:0!important;padding:0!important;border:0!important;border-radius:0!important;
  background:transparent!important;box-shadow:none!important;overflow:visible!important;
}
body.ab-apex .tt-field-auth-form .tt-service-group{
  width:100%!important;margin:12px 0 0!important;border:1px solid #ddd5c8!important;border-radius:15px!important;
  background:#fff!important;box-shadow:none!important;overflow:visible!important;
}
body.ab-apex .tt-field-auth-form .tt-service-group>header{
  min-height:50px!important;padding:9px 12px!important;display:flex!important;align-items:center!important;gap:9px!important;
  border-bottom:1px solid #e6dfd4!important;border-radius:15px 15px 0 0!important;background:#f7f3eb!important;
}
body.ab-apex .tt-field-auth-form .tt-service-group>header .tt-group-title{min-width:0!important;flex:1 1 auto!important}
body.ab-apex .tt-field-auth-form [data-group-body]{padding:0 10px 10px!important;overflow:visible!important}

body.ab-apex .tt-field-auth-form .tt-position{
  width:100%!important;min-width:0!important;margin:10px 0 0!important;padding:12px!important;
  display:grid!important;grid-template-columns:repeat(12,minmax(0,1fr))!important;gap:8px!important;align-items:start!important;
  border:1px solid #ebe4d9!important;border-radius:13px!important;background:#fffdfa!important;
}
body.ab-apex .tt-field-auth-form .tt-position-grip{grid-column:1;grid-row:1;align-self:center;justify-self:center}
body.ab-apex .tt-field-auth-form .tt-position-number{grid-column:2;grid-row:1;align-self:center;white-space:nowrap}
body.ab-apex .tt-field-auth-form .tt-position [data-item-type]{grid-column:3/7;grid-row:1;width:100%!important;min-width:0!important}
body.ab-apex .tt-field-auth-form .tt-position .tt-qty{grid-column:7/9;grid-row:1;width:100%!important;min-width:0!important}
body.ab-apex .tt-field-auth-form .tt-position .tt-unit{grid-column:9/11;grid-row:1;width:100%!important;min-width:0!important}
body.ab-apex .tt-field-auth-form .tt-position .tt-delete-position{grid-column:12;grid-row:1;justify-self:end;align-self:center}
body.ab-apex .tt-field-auth-form .tt-position .tt-description{
  grid-column:1/-1!important;grid-row:2!important;min-width:0!important;width:100%!important;
  display:grid!important;grid-template-columns:minmax(0,1fr) auto!important;gap:8px!important;align-items:start!important;
}
body.ab-apex .tt-field-auth-form .tt-description>[name="item_description"]{grid-column:1;grid-row:1;width:100%!important;min-width:0!important}
body.ab-apex .tt-field-auth-form .tt-description>.tt-browse{grid-column:2;grid-row:1;min-height:38px!important;white-space:nowrap!important}
body.ab-apex .tt-field-auth-form .tt-description>textarea{grid-column:1/-1;grid-row:2;width:100%!important;min-height:72px!important;resize:vertical!important}
body.ab-apex .tt-field-auth-form .tt-description>.tt-mixed-editor,
body.ab-apex .tt-field-auth-form .tt-description>.tt-position-extra{grid-column:1/-1!important;width:100%!important;min-width:0!important}
body.ab-apex .tt-field-auth-form .tt-position>[name="item_purchase_price"]{grid-column:1/4;grid-row:3;width:100%!important;min-width:0!important}
body.ab-apex .tt-field-auth-form .tt-position>.tt-percent{grid-column:4/7;grid-row:3;width:100%!important;min-width:0!important}
body.ab-apex .tt-field-auth-form .tt-position>[data-markup-value]{grid-column:7/9;grid-row:3;align-self:center;min-width:0!important;white-space:nowrap}
body.ab-apex .tt-field-auth-form .tt-position>.tt-sales-field{grid-column:9/13;grid-row:3;width:100%!important;min-width:0!important}
body.ab-apex .tt-field-auth-form .tt-position>[data-unit-price]{grid-column:1/4;grid-row:4;align-self:center;min-width:0!important;white-space:nowrap}
body.ab-apex .tt-field-auth-form .tt-position>[data-line-total]{grid-column:4/8;grid-row:4;align-self:center;min-width:0!important;white-space:nowrap;font-weight:750}
body.ab-apex .tt-field-auth-form .tt-position>.tt-service-model{grid-column:8/13;grid-row:4;width:100%!important;min-width:0!important}
body.ab-apex .tt-field-auth-form .tt-position :where(input,select,textarea){max-width:100%!important;min-width:0!important}
body.ab-apex .tt-field-auth-form .tt-position :where(input,select){min-height:38px!important}
body.ab-apex .tt-field-auth-form .tt-position output{font-size:11px;color:#615c54}
body.ab-apex .tt-field-auth-form .tt-position-extra{display:flex!important;gap:12px!important;align-items:center!important;flex-wrap:wrap!important}
body.ab-apex .tt-field-auth-form .tt-add-position{width:100%!important;min-height:42px!important;margin-top:10px!important;border-radius:10px!important}
body.ab-apex .tt-field-auth-form .tt-inline-help{margin-top:10px!important}

body.ab-apex .tt-field-auth-form .tt-authorization-calculation{width:100%!important;margin-top:16px!important}
body.ab-apex .tt-field-auth-form .tt-authorization-calculation .tt-summary{
  width:100%!important;max-width:none!important;margin:0!important;padding:16px!important;border:1px solid #e4ddd1!important;
  border-radius:14px!important;background:#fff!important;box-shadow:none!important;
}
body.ab-apex .tt-field-auth-form [data-cap-wrap]{margin-top:12px!important}
body.ab-apex .tt-field-auth-form .tt-mixed-editor{max-width:100%!important;overflow-x:auto!important}
body.ab-apex .tt-field-auth-form .tt-subitem{min-width:720px}

@media(max-width:720px){
  body.ab-apex .tt-field-auth-form{gap:14px!important}
  body.ab-apex .tt-field-auth-form .fa-angebot-pricing{padding:13px!important;border-radius:14px!important}
  body.ab-apex .tt-field-auth-form .fa-price-mode{grid-template-columns:1fr!important}
  body.ab-apex .tt-field-auth-form .tt-service-group>header{align-items:flex-start!important;flex-wrap:wrap!important}
  body.ab-apex .tt-field-auth-form [data-group-body]{padding:0 7px 8px!important}
  body.ab-apex .tt-field-auth-form .tt-position{
    padding:10px!important;grid-template-columns:28px 44px minmax(0,1fr) 38px!important;gap:7px!important;
  }
  body.ab-apex .tt-field-auth-form .tt-position-grip{grid-column:1;grid-row:1}
  body.ab-apex .tt-field-auth-form .tt-position-number{grid-column:2;grid-row:1}
  body.ab-apex .tt-field-auth-form .tt-position [data-item-type]{grid-column:3;grid-row:1}
  body.ab-apex .tt-field-auth-form .tt-position .tt-delete-position{grid-column:4;grid-row:1}
  body.ab-apex .tt-field-auth-form .tt-position .tt-qty{grid-column:1/3;grid-row:2}
  body.ab-apex .tt-field-auth-form .tt-position .tt-unit{grid-column:3/5;grid-row:2}
  body.ab-apex .tt-field-auth-form .tt-position .tt-description{grid-column:1/-1!important;grid-row:3!important;grid-template-columns:1fr!important}
  body.ab-apex .tt-field-auth-form .tt-description>[name="item_description"],
  body.ab-apex .tt-field-auth-form .tt-description>.tt-browse,
  body.ab-apex .tt-field-auth-form .tt-description>textarea{grid-column:1!important;grid-row:auto!important;width:100%!important}
  body.ab-apex .tt-field-auth-form .tt-position>[name="item_purchase_price"]{grid-column:1/3;grid-row:4}
  body.ab-apex .tt-field-auth-form .tt-position>.tt-percent{grid-column:3/5;grid-row:4}
  body.ab-apex .tt-field-auth-form .tt-position>[data-markup-value]{grid-column:1/3;grid-row:5}
  body.ab-apex .tt-field-auth-form .tt-position>.tt-sales-field{grid-column:3/5;grid-row:5}
  body.ab-apex .tt-field-auth-form .tt-position>[data-unit-price]{grid-column:1/3;grid-row:6}
  body.ab-apex .tt-field-auth-form .tt-position>[data-line-total]{grid-column:3/5;grid-row:6}
  body.ab-apex .tt-field-auth-form .tt-position>.tt-service-model{grid-column:1/5;grid-row:7}
  body.ab-apex .tt-field-auth-form .tt-authorization-calculation .tt-summary{padding:12px!important}
}
'''
write("static/css/field-authorization-layout-hotfix.css", layout_css)

layout_link = (
    '<link rel="stylesheet" href="{% static \'css/field-authorization-layout-hotfix.css\' %}'
    f'?v={LAYOUT_VERSION}" data-field-authorization-layout>'
)
existing_layout_link = re.compile(r'<link\b[^>]*data-field-authorization-layout[^>]*>')
if existing_layout_link.search(base):
    base = existing_layout_link.sub(layout_link, base, count=1)
else:
    if "</head>" not in base:
        raise RuntimeError("Base head closing tag missing for Termin layout stylesheet")
    base = base.replace("</head>", layout_link + "\n</head>", 1)
write(base_rel, base)


# The old appointment parity contract deliberately hid internal pricing. That is no
# longer the requested product behavior: the Termin authorization editor now reuses
# the exact Angebot pricing editor for authorized staff. Keep the customer-facing
# signed snapshot rules separate; only align this obsolete office-UI assertion.
appointment_test_rel = "tests/test_tooltime_appointment_process_parity.py"
if (ROOT / appointment_test_rel).exists():
    test = read(appointment_test_rel)
    test = test.replace(
        "def test_appointment_services_store_prices_but_appointment_ui_hides_them(self):",
        "def test_appointment_authorization_reuses_angebot_pricing_fields(self):",
        1,
    )
    old = '        self.assertNotContains(detail, "Einkaufspreis")\n'
    new = '''        self.assertContains(detail, "Einkaufspreis")
        self.assertContains(detail, "Aufschlag")
'''
    if old in test:
        test = test.replace(old, new, 1)
    elif 'self.assertContains(detail, "Einkaufspreis")' not in test:
        raise RuntimeError("Appointment pricing visibility regression anchor changed")
    write(appointment_test_rel, test)


write("tests/test_field_authorization_layout_hotfix.py", f'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class FieldAuthorizationLayoutHotfixTests(SimpleTestCase):
    def test_termin_does_not_trigger_document_studio_page_skin(self):
        css = (ROOT / "{finance_css_rel}").read_text(encoding="utf-8")
        self.assertNotIn("{legacy_page_selector}", css)
        self.assertIn("{safe_page_selector}", css)

    def test_termin_layout_asset_is_scoped_and_cache_busted(self):
        css = (ROOT / "static/css/field-authorization-layout-hotfix.css").read_text(encoding="utf-8")
        base = (ROOT / "{base_rel}").read_text(encoding="utf-8")
        template = (ROOT / "templates/rebuild/appointment_detail.html").read_text(encoding="utf-8")
        for required in (
            "{LAYOUT_MARKER}",
            ".tt-field-auth-form .tt-position",
            ".tt-field-auth-form .tt-description",
            ".tt-field-auth-form .tt-authorization-calculation",
        ):
            self.assertIn(required, css)
        self.assertEqual(base.count("data-field-authorization-layout"), 1)
        self.assertIn("field-authorization-layout-hotfix.css' %}}?v={LAYOUT_VERSION}", base)
        self.assertIn("tt-document-form", template)
        self.assertIn("tt-field-auth-form", template)
        self.assertIn("rebuild/_tooltime_services_editor.html", template)

    def test_shared_angebot_runtime_contract_is_unchanged(self):
        service = (ROOT / "erp/services/field_authorization.py").read_text(encoding="utf-8")
        self.assertIn('purchases = post.getlist("item_purchase_price")', service)
        self.assertIn('markups = post.getlist("item_markup_percent")', service)
        self.assertIn('"pricing_contract": "angebot" if angebot_contract else "legacy"', service)
''')


# Guard the original PR #184 contracts plus the visual isolation. Pricing fields and
# calculation runtime stay canonical; only their Termin presentation is specialized.
if "ab-bau-v3-finance-mobile-pdf-hotfix.css?v=20260908-dashboard-actions-1-fa-layout-1" not in read(base_rel):
    raise RuntimeError("Finance stylesheet was not cache-busted for Termin layout hotfix")
if read(base_rel).count("data-field-authorization-layout") != 1:
    raise RuntimeError("Termin layout stylesheet must be linked exactly once")
if LAYOUT_MARKER not in read("static/css/field-authorization-layout-hotfix.css"):
    raise RuntimeError("Termin layout stylesheet marker missing")
if legacy_page_selector in read(finance_css_rel):
    raise RuntimeError("Termin still matches global document-page presentation")
if (ROOT / appointment_test_rel).exists():
    final_test = read(appointment_test_rel)
    if 'self.assertNotContains(detail, "Einkaufspreis")' in final_test:
        raise RuntimeError("Obsolete hidden-EK appointment assertion survived")
    if 'self.assertContains(detail, "Einkaufspreis")' not in final_test:
        raise RuntimeError("Shared Angebot pricing visibility assertion missing")

print(f"{MARKER}: pricing contract preserved; Termin/Freigabe layout isolated from Document Studio and made responsive.")