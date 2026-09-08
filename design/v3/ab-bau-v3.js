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

  const empty = palette?.querySelector('[data-ab-v3-command-empty]');
  let previousFocus = null;
  let previousOverflow = '';
  let background = [];
  const visibleItems = () => items.filter(item => !item.hidden);

  const openPalette = () => {
    if (!palette) return;
    if (palette.classList.contains('is-open')) return;
    previousFocus = document.activeElement;
    previousOverflow = body.style.overflow;
    background = [...body.children].filter(node => node !== palette && !node.contains(palette));
    background = background.map(node => [node, node.inert]);
    background.forEach(([node]) => { node.inert = true; });
    palette.classList.add('is-open');
    palette.setAttribute('aria-hidden', 'false');
    body.style.overflow = 'hidden';
    if (search) {
      search.value = '';
      items.forEach(item => { item.hidden = false; });
      if (empty) empty.hidden = true;
      search.focus();
    }
  };

  const closePalette = () => {
    if (!palette || !palette.classList.contains('is-open')) return;
    palette.classList.remove('is-open');
    palette.setAttribute('aria-hidden', 'true');
    body.style.overflow = previousOverflow;
    background.forEach(([node, inert]) => { node.inert = inert; });
    background = [];
    if (previousFocus?.isConnected) previousFocus.focus();
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
      const haystack = ((item.dataset.search || '') + ' ' + (item.textContent || '')).toLocaleLowerCase('de-DE');
      item.hidden = Boolean(term && !haystack.includes(term));
    });
    if (empty) empty.hidden = visibleItems().length > 0;
  });

  document.addEventListener('keydown', event => {
    const commandKey = (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k';
    if (commandKey && palette) {
      event.preventDefault();
      palette?.classList.contains('is-open') ? closePalette() : openPalette();
      return;
    }
    if (!palette?.classList.contains('is-open')) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      closePalette();
    } else if (event.key === 'Tab') {
      const controls = [...palette.querySelectorAll('input, button, a[href]')].filter(node => !node.hidden);
      const first = controls[0], last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault(); last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault(); first?.focus();
      }
    } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      const choices = visibleItems();
      const direction = event.key === 'ArrowDown' ? 1 : -1;
      const index = choices.indexOf(document.activeElement);
      if (choices.length) choices[(index + direction + choices.length) % choices.length].focus();
    } else if (event.key === 'Enter' && document.activeElement === search) {
      event.preventDefault();
      visibleItems()[0]?.click();
    }
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
