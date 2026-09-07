(() => {
  'use strict';
  const MARKER = 'A_BAU_V3_PHASE1_2026_09_08';
  if (window[MARKER]) return;
  window[MARKER] = true;

  const body = document.body;
  if (!body || !body.classList.contains('ab-v3')) return;

  const palette = document.querySelector('[data-ab-v3-command]');
  const search = palette?.querySelector('[data-ab-v3-command-search]');
  const items = palette ? [...palette.querySelectorAll('[data-ab-v3-command-item]')] : [];

  const openPalette = () => {
    if (!palette) return;
    palette.classList.add('is-open');
    palette.setAttribute('aria-hidden', 'false');
    body.style.overflow = 'hidden';
    if (search) {
      search.value = '';
      items.forEach(item => { item.hidden = false; });
      window.setTimeout(() => search.focus(), 30);
    }
  };

  const closePalette = () => {
    if (!palette) return;
    palette.classList.remove('is-open');
    palette.setAttribute('aria-hidden', 'true');
    body.style.overflow = '';
  };

  document.querySelectorAll('[data-ab-v3-command-open]').forEach(button => {
    button.addEventListener('click', openPalette);
  });
  document.querySelectorAll('[data-ab-v3-command-close]').forEach(button => {
    button.addEventListener('click', closePalette);
  });

  palette?.addEventListener('click', event => {
    if (event.target === palette) closePalette();
  });

  search?.addEventListener('input', () => {
    const term = (search.value || '').trim().toLocaleLowerCase('de-DE');
    items.forEach(item => {
      const haystack = (item.dataset.search || item.textContent || '').toLocaleLowerCase('de-DE');
      item.hidden = Boolean(term && !haystack.includes(term));
    });
  });

  document.addEventListener('keydown', event => {
    const commandKey = (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k';
    if (commandKey) {
      event.preventDefault();
      palette?.classList.contains('is-open') ? closePalette() : openPalette();
      return;
    }
    if (event.key === 'Escape' && palette?.classList.contains('is-open')) closePalette();
  });

  const clock = document.querySelector('[data-ab-v3-clock]');
  const syncClock = () => {
    if (!clock) return;
    clock.textContent = new Intl.DateTimeFormat('de-DE', { hour: '2-digit', minute: '2-digit' }).format(new Date());
  };
  syncClock();
  window.setInterval(syncClock, 30_000);

  const greeting = document.querySelector('[data-ab-v3-greeting]');
  if (greeting) {
    const hour = new Date().getHours();
    greeting.textContent = hour < 11 ? 'Guten Morgen' : hour < 18 ? 'Guten Tag' : 'Guten Abend';
  }

  body.dataset.abV3Ready = 'true';
})();
