// A+BAU FIELD PROFILE TOUCH RUNTIME 2026-08-20
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
