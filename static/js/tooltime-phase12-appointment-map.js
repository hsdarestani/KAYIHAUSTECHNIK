// A+BAU TOOLTIME PHASE 12 APPOINTMENT MAP 2026-08-21
(() => {
  const init = () => {
    const root = document.querySelector('[data-appointment-map]');
    if (!root || root.dataset.mapReady === '1') return;
    root.dataset.mapReady = '1';

    const frame = root.querySelector('[data-map-frame]');
    const placeholder = root.querySelector('[data-map-placeholder]');
    const caption = root.querySelector('[data-map-caption]');
    const title = root.querySelector('[data-map-title]');
    const addressLabel = root.querySelector('[data-map-current-address]');
    const openLink = root.querySelector('[data-map-open]');
    const buttons = Array.from(root.querySelectorAll('[data-map-select]'));
    if (!frame || !placeholder || !caption || !openLink) return;

    const selectAddress = (button) => {
      const address = (button.dataset.mapAddress || '').trim();
      if (!address) return;
      const label = (button.dataset.mapLabel || address).trim();
      buttons.forEach((candidate) => candidate.classList.toggle('is-active', candidate === button));
      const encoded = encodeURIComponent(address);
      frame.src = `https://www.google.com/maps?q=${encoded}&output=embed`;
      frame.hidden = false;
      placeholder.hidden = true;
      caption.hidden = false;
      if (title) title.textContent = label;
      if (addressLabel) addressLabel.textContent = address;
      openLink.href = `https://www.google.com/maps/search/?api=1&query=${encoded}`;
    };

    buttons.forEach((button) => button.addEventListener('click', () => selectAddress(button)));
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once: true});
  else init();
})();
