(() => {
  'use strict';
  const marker = 'A+BAU_APEX_RUNTIME_2026_09_08';
  if (window[marker]) return;
  window[marker] = true;
  const body = document.body;
  if (!body || !body.classList.contains('ab-apex')) return;
  const topbar = document.querySelector('.nx-topbar');
  const syncTopbar = () => topbar?.classList.toggle('is-scrolled', window.scrollY > 8);
  syncTopbar();
  window.addEventListener('scroll', syncTopbar, { passive: true });
  document.querySelectorAll('[data-ab-open-menu]').forEach((button) => {
    button.addEventListener('click', () => document.querySelector('[data-nx-menu]')?.click());
  });
  body.dataset.abApexReady = 'true';
})();
