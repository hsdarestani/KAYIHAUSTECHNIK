from pathlib import Path
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
