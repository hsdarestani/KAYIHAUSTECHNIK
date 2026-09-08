(() => {
  const modal = document.querySelector('[data-document-email-modal]');
  const open = document.querySelector('[data-document-email-open]');
  if (!modal || !open) return;
  const close = modal.querySelector('[data-document-email-close]');
  const hide = () => { modal.hidden = true; document.body.classList.remove('tt-modal-open'); };
  open.addEventListener('click', () => { modal.hidden = false; document.body.classList.add('tt-modal-open'); const input = modal.querySelector('input[name="recipient_email"]'); if (input) input.focus(); });
  if (close) close.addEventListener('click', hide);
  modal.addEventListener('click', (event) => { if (event.target === modal) hide(); });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && !modal.hidden) hide(); });
})();
