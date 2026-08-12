from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU MOBILE NAV POLISH 2026-08-12"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"A+Bau mobile navigation target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_base() -> None:
    rel = "templates/rebuild/base.html"
    text = read(rel)

    if 'id="nx-mobile-sidebar"' not in text:
        if '<aside class="nx-sidebar">' not in text:
            raise RuntimeError("Mobile sidebar base anchor changed")
        text = text.replace('<aside class="nx-sidebar">', '<aside class="nx-sidebar" id="nx-mobile-sidebar">', 1)

    menu_old = '<button class="nx-menu-btn" type="button" data-nx-menu aria-label="Menü">☰</button>'
    menu_new = '<button class="nx-menu-btn" type="button" data-nx-menu aria-label="Menü" aria-expanded="false" aria-controls="nx-mobile-sidebar">☰</button>'
    if menu_new not in text:
        if menu_old not in text:
            raise RuntimeError("Mobile menu button anchor changed")
        text = text.replace(menu_old, menu_new, 1)

    if 'data-nx-menu-overlay' not in text:
        anchor = '</aside>\n  <main class="nx-main">'
        if anchor not in text:
            raise RuntimeError("Mobile menu overlay insertion anchor changed")
        overlay = '</aside>\n  <button class="nx-menu-overlay" type="button" data-nx-menu-overlay aria-label="Menü schließen" tabindex="-1"></button>\n  <main class="nx-main">'
        text = text.replace(anchor, overlay, 1)

    if 'data-ab-brand-image' not in text:
        brand_pattern = re.compile(r'<img\s+src="\{% static \'brand/ab-bau-logo\.webp\' %\}"\s+alt="A\+Bau"[^>]*>')
        replacement = '''<span class="ab-brand-logo"><span class="ab-brand-fallback" aria-hidden="true">A+</span><img src="{% static 'brand/ab-bau-logo.webp' %}" alt="A+Bau" data-ab-brand-image></span>'''
        text, count = brand_pattern.subn(replacement, text, count=1)
        if count != 1:
            raise RuntimeError("A+Bau brand image anchor changed")

    text = re.sub(r"(kayi-next\.css' %\}\?v=)[^\"']+", r"\g<1>20260812-mobile-1", text)
    text = re.sub(r"(kayi-next\.js' %\}\?v=)[^\"']+", r"\g<1>20260812-mobile-1", text)
    write(rel, text)


def patch_javascript() -> None:
    rel = "static/js/kayi-next.js"
    text = read(rel)
    if "A+BAU_MOBILE_NAV" not in text:
        old = '''  const body = document.body;
  $('[data-nx-menu]')?.addEventListener('click', () => body.classList.toggle('nx-menu-open'));
  document.addEventListener('click', (event) => {
    if (!body.classList.contains('nx-menu-open')) return;
    if (event.target.closest('.nx-sidebar') || event.target.closest('[data-nx-menu]')) return;
    body.classList.remove('nx-menu-open');
  });
'''
        new = '''  const body = document.body;
  // A+BAU_MOBILE_NAV
  const mobileMenuButton = $('[data-nx-menu]');
  const mobileMenuOverlay = $('[data-nx-menu-overlay]');
  const mobileSidebar = $('.nx-sidebar');
  const mobileViewport = () => window.matchMedia('(max-width: 860px)').matches;
  const setMobileMenu = (open) => {
    const next = Boolean(open && mobileViewport());
    body.classList.toggle('nx-menu-open', next);
    mobileMenuButton?.setAttribute('aria-expanded', next ? 'true' : 'false');
    if (next && $('[data-assistant-drawer][aria-hidden="false"]')) $('[data-assistant-close]')?.click();
  };
  mobileMenuButton?.addEventListener('click', () => setMobileMenu(!body.classList.contains('nx-menu-open')));
  mobileMenuOverlay?.addEventListener('click', () => setMobileMenu(false));
  mobileSidebar?.querySelectorAll('a').forEach((link) => link.addEventListener('click', () => {
    if (mobileViewport()) setMobileMenu(false);
  }));
  document.addEventListener('click', (event) => {
    if (!body.classList.contains('nx-menu-open')) return;
    if (event.target.closest('.nx-sidebar') || event.target.closest('[data-nx-menu]')) return;
    setMobileMenu(false);
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && body.classList.contains('nx-menu-open')) setMobileMenu(false);
  });
  const desktopMenuQuery = window.matchMedia('(min-width: 861px)');
  const resetMobileMenu = (event) => { if (event.matches) setMobileMenu(false); };
  if (desktopMenuQuery.addEventListener) desktopMenuQuery.addEventListener('change', resetMobileMenu);
  else desktopMenuQuery.addListener?.(resetMobileMenu);

  $$('[data-ab-brand-image]').forEach((image) => {
    const frame = image.closest('.ab-brand-logo');
    const syncLogo = () => frame?.classList.toggle('is-missing', !image.complete || image.naturalWidth === 0);
    image.addEventListener('load', syncLogo);
    image.addEventListener('error', syncLogo);
    syncLogo();
  });
'''
        if old not in text:
            raise RuntimeError("Mobile menu JavaScript contract changed")
        text = text.replace(old, new, 1)
    write(rel, text)


def patch_css() -> None:
    rel = "static/css/kayi-next.css"
    css = read(rel)
    if MARKER not in css:
        css += r'''

/* A+BAU MOBILE NAV POLISH 2026-08-12 */
.nx-menu-overlay{display:none}
.ab-brand-logo{position:relative;display:grid;place-items:center;flex:0 0 auto;width:54px;height:44px;border-radius:10px;border:1px solid rgba(201,161,59,.38);background:#0b0d0f;overflow:hidden}
.ab-brand-logo img{position:relative;z-index:2;width:100%!important;height:100%!important;max-width:none!important;border:0!important;border-radius:inherit!important;object-fit:cover!important;object-position:center!important;background:#0b0d0f}
.ab-brand-fallback{position:absolute;inset:0;z-index:1;display:grid;place-items:center;font-size:18px;font-weight:900;letter-spacing:-.06em;color:#d7b454;background:linear-gradient(145deg,#0d0f11,#191b1e)}
.ab-brand-logo:not(.is-missing) .ab-brand-fallback{visibility:hidden}
.ab-brand-logo.is-missing img{display:none!important}

@media(max-width:860px){
  html,body{max-width:100%;overflow-x:hidden}
  body.nx-body.nx-menu-open{overflow:hidden;overscroll-behavior:none}
  .nx-shell,.nx-main,.nx-content{min-width:0;max-width:100%}
  .nx-sidebar{left:0!important;right:auto!important;top:0!important;width:min(86vw,340px)!important;max-width:calc(100vw - 48px)!important;height:100vh!important;height:100dvh!important;padding:calc(12px + env(safe-area-inset-top)) 12px calc(18px + env(safe-area-inset-bottom))!important;overflow-y:auto!important;overflow-x:hidden!important;overscroll-behavior:contain;-webkit-overflow-scrolling:touch;touch-action:pan-y;transform:translate3d(-105%,0,0)!important;transition:transform .22s cubic-bezier(.2,.8,.2,1)!important;pointer-events:none;z-index:70!important}
  .nx-body.nx-menu-open .nx-sidebar{transform:translate3d(0,0,0)!important;pointer-events:auto;box-shadow:22px 0 60px rgba(0,0,0,.36)!important}
  .nx-menu-overlay{display:block;position:fixed;inset:0;z-index:65;border:0;margin:0;padding:0;width:100%;height:100%;background:rgba(5,7,9,.56);-webkit-backdrop-filter:blur(2px);backdrop-filter:blur(2px);opacity:0;visibility:hidden;pointer-events:none;transition:opacity .2s ease,visibility .2s ease}
  .nx-body.nx-menu-open .nx-menu-overlay{opacity:1;visibility:visible;pointer-events:auto}
  .nx-brand.ab-brand{padding:4px 5px 12px!important;gap:10px!important;align-items:center!important}
  .ab-brand-logo{width:52px;height:52px;border-radius:12px}.ab-brand strong{font-size:18px!important;line-height:1.05}.ab-brand small{font-size:11px!important;line-height:1.3!important;max-width:180px!important;margin-top:5px!important}
  .nx-nav{gap:2px!important}.nx-nav-label{padding:13px 10px 5px!important;font-size:9px!important}.nx-nav a{padding:10px!important;min-height:42px;border-radius:12px!important;gap:9px!important;font-size:13px!important}.nx-nav .nx-ico{width:21px!important;font-size:15px!important}.nx-sidebar-foot{margin-top:16px!important;padding:12px 10px!important}
  .nx-topbar{height:62px!important;padding:0 12px!important;gap:8px!important;max-width:100vw;overflow:hidden}.nx-menu-btn{display:grid!important;place-items:center;width:42px;height:42px;min-width:42px;border:1px solid var(--nx-line)!important;border-radius:12px;background:var(--nx-surface)!important;color:var(--nx-ink)!important;line-height:1;cursor:pointer}.nx-topbar .nx-search{display:none!important}.nx-top-actions{margin-left:auto!important;gap:6px!important;min-width:0}.nx-top-actions>.nx-btn{display:none!important}.nx-avatar{width:38px!important;height:38px!important;min-width:38px}
  .nx-content{padding:18px 12px 80px!important;overflow-x:hidden!important}.nx-pagehead,.nx-card,.nx-toolbar,.nx-form,.nx-form-grid,.nx-project-hero{min-width:0!important;max-width:100%!important}.nx-table-wrap,.ab-item-table-wrap{width:100%;max-width:100%;overflow-x:auto!important;overflow-y:hidden;-webkit-overflow-scrolling:touch;overscroll-behavior-x:contain}.nx-table,.ab-item-table{max-width:none}
  .nx-body.nx-menu-open .nx-assistant-fab{opacity:0!important;visibility:hidden!important;pointer-events:none!important;transform:scale(.86)!important}
}
@media(max-width:560px){.nx-sidebar{width:min(88vw,330px)!important;max-width:calc(100vw - 40px)!important}.nx-content{padding-left:12px!important;padding-right:12px!important}.nx-table-wrap{border-radius:inherit}}
'''
    write(rel, css)


def install_tests() -> None:
    test = r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]

class ABBauMobileNavigationTests(SimpleTestCase):
    def test_mobile_drawer_overlay_and_accessibility_contract(self):
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        self.assertIn('id="nx-mobile-sidebar"', base)
        self.assertIn('data-nx-menu-overlay', base)
        self.assertIn('aria-expanded="false"', base)
        self.assertIn('aria-controls="nx-mobile-sidebar"', base)

    def test_mobile_drawer_is_narrower_scrollable_and_locks_background(self):
        css = (ROOT / "static/css/kayi-next.css").read_text(encoding="utf-8")
        self.assertIn("width:min(86vw,340px)", css)
        self.assertIn("height:100dvh", css)
        self.assertIn("overflow-y:auto", css)
        self.assertIn("body.nx-body.nx-menu-open{overflow:hidden", css)
        self.assertIn(".nx-body.nx-menu-open .nx-menu-overlay", css)
        self.assertIn(".nx-body.nx-menu-open .nx-assistant-fab", css)

    def test_mobile_menu_closes_outside_escape_and_navigation(self):
        js = (ROOT / "static/js/kayi-next.js").read_text(encoding="utf-8")
        self.assertIn("A+BAU_MOBILE_NAV", js)
        self.assertIn("mobileMenuOverlay?.addEventListener('click'", js)
        self.assertIn("event.key === 'Escape'", js)
        self.assertIn("mobileSidebar?.querySelectorAll('a')", js)
        self.assertIn("aria-expanded", js)

    def test_brand_has_real_image_with_failure_fallback(self):
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        js = (ROOT / "static/js/kayi-next.js").read_text(encoding="utf-8")
        css = (ROOT / "static/css/kayi-next.css").read_text(encoding="utf-8")
        self.assertIn("ab-brand-logo", base)
        self.assertIn("ab-brand-fallback", base)
        self.assertIn("data-ab-brand-image", base)
        self.assertIn("image.naturalWidth", js)
        self.assertIn(".ab-brand-logo.is-missing img", css)

    def test_mobile_main_content_cannot_push_document_width(self):
        css = (ROOT / "static/css/kayi-next.css").read_text(encoding="utf-8")
        self.assertIn("html,body{max-width:100%;overflow-x:hidden}", css)
        self.assertIn(".nx-table-wrap,.ab-item-table-wrap", css)
        self.assertIn("overflow-x:auto!important", css)
'''
    write("tests/test_ab_bau_mobile_navigation.py", test)


def guard() -> None:
    base = read("templates/rebuild/base.html")
    js = read("static/js/kayi-next.js")
    css = read("static/css/kayi-next.css")
    for needle in ('data-nx-menu-overlay', 'id="nx-mobile-sidebar"', 'data-ab-brand-image', 'ab-brand-fallback'):
        if needle not in base:
            raise RuntimeError(f"A+Bau mobile base contract missing: {needle}")
    for needle in ("A+BAU_MOBILE_NAV", "mobileMenuOverlay", "event.key === 'Escape'", "image.naturalWidth"):
        if needle not in js:
            raise RuntimeError(f"A+Bau mobile JavaScript contract missing: {needle}")
    for needle in (MARKER, "width:min(86vw,340px)", ".nx-body.nx-menu-open .nx-menu-overlay", ".nx-body.nx-menu-open .nx-assistant-fab"):
        if needle not in css:
            raise RuntimeError(f"A+Bau mobile CSS contract missing: {needle}")


patch_base()
patch_javascript()
patch_css()
install_tests()
guard()
print("A+Bau mobile navigation polished: compact drawer, overlay, scroll lock, logo fallback and overflow protection installed.")
