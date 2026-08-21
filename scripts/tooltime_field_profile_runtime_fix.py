from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU FIELD PROFILE TOUCH RUNTIME 2026-08-20"
ASSET = "static/js/field-profile-runtime.js"
VERSION = "20260820-touch-1"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Field profile runtime target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def install_runtime_asset() -> None:
    write(ASSET, r'''// A+BAU FIELD PROFILE TOUCH RUNTIME 2026-08-20
(() => {
  const html = document.documentElement;
  html.dataset.fieldProfileRuntime = '1';

  const setOpen = (profile, open) => {
    if (!profile) return;
    const toggle = profile.querySelector('[data-profile-toggle]');
    const menu = profile.querySelector('[data-profile-menu]');
    if (!toggle || !menu) return;
    profile.classList.toggle('is-profile-open', open);
    profile.dataset.profileRuntimeOpen = open ? '1' : '0';
    menu.hidden = !open;
    menu.setAttribute('aria-hidden', open ? 'false' : 'true');
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  };

  const closeAll = (except = null) => {
    document.querySelectorAll('[data-profile]').forEach((profile) => {
      if (profile !== except) setOpen(profile, false);
    });
  };

  // Capture phase is intentional. The historical profile handler lives inside
  // the large kayi-next.js bundle, which may be stale in a mobile browser cache.
  // This small cache-busted runtime becomes the single authoritative handler and
  // prevents the old target listener from toggling the menu a second time.
  document.addEventListener('click', (event) => {
    const target = event.target instanceof Element ? event.target : null;
    const toggle = target?.closest('[data-profile-toggle]');
    if (toggle) {
      const profile = toggle.closest('[data-profile]');
      const menu = profile?.querySelector('[data-profile-menu]');
      if (!profile || !menu) return;
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      const shouldOpen = menu.hidden || profile.dataset.profileRuntimeOpen !== '1';
      closeAll(profile);
      setOpen(profile, shouldOpen);
      return;
    }
    const insideProfile = target?.closest('[data-profile]');
    if (!insideProfile) closeAll();
  }, true);

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeAll();
  }, true);
})();
''')


def patch_base_asset() -> None:
    rel = "templates/rebuild/base.html"
    text = read(rel)
    tag = f'''<script src="{{% static 'js/field-profile-runtime.js' %}}?v={VERSION}" defer data-field-profile-runtime></script>\n'''
    if "data-field-profile-runtime" not in text:
        anchor = "{% block scripts %}"
        if anchor not in text:
            raise RuntimeError("Field profile runtime base script anchor missing")
        text = text.replace(anchor, tag + anchor, 1)
    write(rel, text)


def patch_touch_css() -> None:
    rel = "static/css/kayi-next-field.css"
    text = read(rel)
    if MARKER not in text:
        text = text.rstrip() + r'''

/* A+BAU FIELD PROFILE TOUCH RUNTIME 2026-08-20 */
@media(max-width:900px){
  .nx-field-role .nx-topbar{overflow:visible!important}
  .nx-field-role [data-profile]{position:relative!important;z-index:125!important;pointer-events:auto!important}
  .nx-field-role [data-profile-toggle]{position:relative!important;z-index:126!important;pointer-events:auto!important;touch-action:manipulation!important;min-width:42px!important;min-height:42px!important}
  .nx-field-role [data-profile-menu]{z-index:130!important;pointer-events:auto!important}
  .nx-field-role [data-profile].is-profile-open [data-profile-menu]{display:block!important;visibility:visible!important;opacity:1!important;pointer-events:auto!important}
}
'''
    write(rel, text)


def patch_real_hit_test_smoke() -> None:
    rel = "scripts/production_browser_smoke.py"
    text = read(rel)
    field_marker = "                # A+BAU FIELD TOPBAR LOGOUT BROWSER SMOKE\n"
    start = text.find(field_marker)
    if start < 0:
        raise RuntimeError("Field profile runtime browser-smoke anchor missing")
    end = text.find("                direct_logout = page.locator('[data-account-logout]')", start)
    if end < 0:
        raise RuntimeError("Field profile runtime browser-smoke end anchor missing")
    segment = text[start:end]
    runtime_marker = "A+BAU FIELD PROFILE REAL HIT-TEST"
    if runtime_marker not in segment:
        old = '''                profile_toggle.click()\n                profile_menu = page.locator('[data-profile-menu]')\n'''
        new = r'''                # A+BAU FIELD PROFILE REAL HIT-TEST
                if page.locator('script[data-field-profile-runtime]').count() != 1:
                    fail("Dedicated field profile runtime asset is missing")
                if page.locator('html').get_attribute("data-field-profile-runtime") != "1":
                    fail("Dedicated field profile runtime did not execute")
                profile_box = profile_toggle.bounding_box()
                if not profile_box:
                    fail("Technician profile control has no mobile hit box")
                profile_x = profile_box["x"] + profile_box["width"] / 2
                profile_y = profile_box["y"] + profile_box["height"] / 2
                profile_is_hit_target = page.evaluate(
                    "([x,y]) => { const el=document.elementFromPoint(x,y); return !!el && !!el.closest('[data-profile-toggle]'); }",
                    [profile_x, profile_y],
                )
                if not profile_is_hit_target:
                    fail("Technician profile control is covered by another mobile element")
                # Use the physical screen coordinate rather than locator.click(), so
                # overlays/pointer interception are caught like on a real phone.
                page.mouse.click(profile_x, profile_y)
                page.wait_for_timeout(100)
                profile_menu = page.locator('[data-profile-menu]')
                profile_root = page.locator('[data-profile]')
                if profile_root.get_attribute("data-profile-runtime-open") != "1":
                    fail("Dedicated field profile runtime did not receive the mobile click")
'''
        if old not in segment:
            raise RuntimeError("Field profile click smoke contract changed")
        segment = segment.replace(old, new, 1)
        text = text[:start] + segment + text[end:]
    write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def install_contract_test() -> None:
    write("tests/test_field_profile_touch_runtime_contract.py", r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class FieldProfileTouchRuntimeContractTests(SimpleTestCase):
    def test_dedicated_cache_busted_profile_runtime_is_in_final_shell(self):
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        self.assertIn("field-profile-runtime.js", base)
        self.assertIn("v=20260820-touch-1", base)
        self.assertIn("data-field-profile-runtime", base)

    def test_runtime_owns_profile_click_in_capture_phase(self):
        runtime = (ROOT / "static/js/field-profile-runtime.js").read_text(encoding="utf-8")
        self.assertIn("A+BAU FIELD PROFILE TOUCH RUNTIME 2026-08-20", runtime)
        self.assertIn("document.addEventListener('click'", runtime)
        self.assertIn("event.stopImmediatePropagation()", runtime)
        self.assertIn("profileRuntimeOpen", runtime)

    def test_mobile_profile_is_a_real_pointer_target(self):
        css = (ROOT / "static/css/kayi-next-field.css").read_text(encoding="utf-8")
        self.assertIn("A+BAU FIELD PROFILE TOUCH RUNTIME 2026-08-20", css)
        self.assertIn("touch-action:manipulation!important", css)
        self.assertIn("pointer-events:auto!important", css)
        self.assertIn("overflow:visible!important", css)

    def test_browser_smoke_uses_real_screen_hit_test(self):
        smoke = (ROOT / "scripts/production_browser_smoke.py").read_text(encoding="utf-8")
        self.assertIn("A+BAU FIELD PROFILE REAL HIT-TEST", smoke)
        self.assertIn("document.elementFromPoint", smoke)
        self.assertIn("page.mouse.click(profile_x, profile_y)", smoke)
        self.assertIn('data-profile-runtime-open', smoke)
''')


def guard() -> None:
    base = read("templates/rebuild/base.html")
    css = read("static/css/kayi-next-field.css")
    runtime = read(ASSET)
    smoke = read("scripts/production_browser_smoke.py")
    for required in ("field-profile-runtime.js", VERSION, "data-field-profile-runtime"):
        if required not in base:
            raise RuntimeError(f"Field profile runtime base contract missing: {required}")
    if MARKER not in css or "touch-action:manipulation!important" not in css:
        raise RuntimeError("Field profile touch CSS contract missing")
    if MARKER not in runtime or "stopImmediatePropagation" not in runtime:
        raise RuntimeError("Dedicated field profile runtime contract missing")
    if "A+BAU FIELD PROFILE REAL HIT-TEST" not in smoke or "document.elementFromPoint" not in smoke:
        raise RuntimeError("Real mobile profile hit-test smoke missing")
    compile(smoke, str(ROOT / "scripts/production_browser_smoke.py"), "exec")
    compile(read("tests/test_field_profile_touch_runtime_contract.py"), str(ROOT / "tests/test_field_profile_touch_runtime_contract.py"), "exec")


def run() -> None:
    install_runtime_asset()
    patch_base_asset()
    patch_touch_css()
    patch_real_hit_test_smoke()
    install_contract_test()
    guard()
    # Phase 9 is intentionally chained after the final mobile/profile shell so
    # customer/project creation remains the last owner of the core CRUD UX.
    runpy.run_path(str(ROOT / "scripts" / "tooltime_parity_phase9_core_crud_runner.py"), run_name="__main__")
    print(f"{MARKER}: cache-unabhängiger Profil-Touch-Handler, echter Hit-Test und mobile Pointer-Sicherheit installiert.")


if __name__ == "__main__":
    run()
