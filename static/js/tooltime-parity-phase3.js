(() => {
  const num = value => { const n = Number(String(value ?? '').replace(',', '.')); return Number.isFinite(n) ? n : 0; };
  const money = value => `${num(value).toLocaleString('de-DE', {minimumFractionDigits:2, maximumFractionDigits:2})} €`;
  const rowHtml = () => `<div class="tt-subitem" data-subitem><select class="nx-control" data-sub-type><option value="material">Material</option><option value="labour">Lohn</option><option value="other">Sonstiges</option></select><input class="nx-control" data-sub-description placeholder="Unterposition"><input class="nx-control" data-sub-qty type="number" step="0.001" value="1"><input class="nx-control" data-sub-unit value="Stk."><input class="nx-control" data-sub-purchase type="number" min="0" step="0.01" value="0" placeholder="EK"><input class="nx-control" data-sub-sales type="number" min="0" step="0.01" value="0" placeholder="VK"><button type="button" class="tt-delete-position" data-remove-subitem>×</button></div>`;

  function syncGroup(group) {
    const title = group.querySelector('.tt-group-title')?.value || 'Leistungsgruppe';
    group.querySelectorAll('[data-group-hidden]').forEach(input => input.value = title);
  }

  function syncMixed(position) {
    const editor = position.querySelector('[data-mixed-editor]');
    if (!editor) return;
    const mixed = position.querySelector('[data-item-type]')?.value === 'mixed';
    editor.hidden = !mixed;
    const rows = [...editor.querySelectorAll('[data-subitem]')].map((row, index) => ({
      item_type: row.querySelector('[data-sub-type]')?.value || 'material',
      description: row.querySelector('[data-sub-description]')?.value || '',
      quantity: row.querySelector('[data-sub-qty]')?.value || '0',
      unit: row.querySelector('[data-sub-unit]')?.value || 'Stk.',
      purchase_price: row.querySelector('[data-sub-purchase]')?.value || '0',
      sales_price: row.querySelector('[data-sub-sales]')?.value || '0',
      sort_order: index,
    }));
    const json = editor.querySelector('[data-subitems-json]'); if (json) json.value = JSON.stringify(rows);
    const show = editor.querySelector('[data-show-subitems]');
    const hidden = editor.querySelector('[data-show-subitems-hidden]'); if (hidden) hidden.value = show?.checked === false ? '0' : '1';
    if (mixed && rows.length) {
      const sale = rows.reduce((sum, row) => sum + num(row.quantity) * num(row.sales_price), 0);
      const purchase = rows.reduce((sum, row) => sum + num(row.quantity) * num(row.purchase_price), 0);
      const saleInput = position.querySelector('[data-sales-price]'); if (saleInput) saleInput.value = sale.toFixed(2);
      const hiddenSale = position.querySelector('[data-hidden-sales-price]'); if (hiddenSale) hiddenSale.value = sale.toFixed(2);
      const purchaseInput = position.querySelector('[name="item_purchase_price"]'); if (purchaseInput) purchaseInput.value = purchase.toFixed(2);
      const markup = position.querySelector('[name="item_markup_percent"]'); if (markup) markup.value = purchase > 0 ? (((sale / purchase) - 1) * 100).toFixed(2) : '0';
      const output = position.querySelector('[data-unit-price]'); if (output) output.textContent = money(sale);
    }
  }

  document.addEventListener('change', event => {
    const project = event.target.closest('[data-project-select]');
    if (project) {
      const customerId = project.selectedOptions[0]?.dataset.customerId || '';
      const customer = document.querySelector('[data-customer-select]');
      if (customerId && customer) { customer.value = customerId; customer.dispatchEvent(new Event('change', {bubbles:true})); }
    }
    const customer = event.target.closest('[data-customer-select]');
    if (customer) {
      const projectSelect = document.querySelector('[data-project-select]');
      const selected = projectSelect?.selectedOptions[0];
      if (selected?.value && selected.dataset.customerId !== customer.value) projectSelect.value = '';
    }
    const type = event.target.closest('[data-item-type]'); if (type) syncMixed(type.closest('[data-position]'));
    if (event.target.matches('[data-show-subitems]')) syncMixed(event.target.closest('[data-position]'));
  });

  document.addEventListener('input', event => {
    const sales = event.target.closest('[data-sales-price]');
    if (sales) {
      const position = sales.closest('[data-position]');
      const hidden = position?.querySelector('[data-hidden-sales-price]'); if (hidden) hidden.value = num(sales.value).toFixed(2);
      const output = position?.querySelector('[data-unit-price]'); if (output) output.textContent = money(sales.value);
    }
    if (event.target.closest('[data-subitem]')) syncMixed(event.target.closest('[data-position]'));
  });

  document.addEventListener('click', event => {
    const menu = event.target.closest('[data-group-menu]');
    if (menu) { const panel = menu.parentElement.querySelector('[data-group-menu-panel]'); if (panel) panel.hidden = !panel.hidden; return; }
    const action = event.target.closest('[data-group-action]');
    if (action) {
      const group = action.closest('[data-service-group]'); if (!group) return;
      if (action.dataset.groupAction === 'delete') {
        if (confirm('Leistungsgruppe inklusive Positionen löschen?')) group.remove();
      } else if (action.dataset.groupAction === 'duplicate') {
        const clone = group.cloneNode(true);
        clone.querySelectorAll('input[type=file]').forEach(input => input.value = '');
        const title = clone.querySelector('.tt-group-title'); if (title) title.value = `${title.value || 'Leistungsgruppe'} – Kopie`;
        group.after(clone); syncGroup(clone); clone.querySelectorAll('[data-position]').forEach(syncMixed);
      } else if (action.dataset.groupAction === 'margin') {
        const value = prompt('Aufschlag für alle Positionen dieser Gruppe in %:', '20');
        if (value !== null && Number.isFinite(num(value))) group.querySelectorAll('[name="item_markup_percent"]').forEach(input => { input.value = num(value); input.dispatchEvent(new Event('input', {bubbles:true})); });
      }
      const panel = group.querySelector('[data-group-menu-panel]'); if (panel) panel.hidden = true;
      return;
    }
    const add = event.target.closest('[data-add-subitem]');
    if (add) { const list = add.closest('[data-mixed-editor]')?.querySelector('[data-subitem-list]'); if (list) { list.insertAdjacentHTML('beforeend', rowHtml()); syncMixed(add.closest('[data-position]')); } return; }
    const remove = event.target.closest('[data-remove-subitem]');
    if (remove) { const position = remove.closest('[data-position]'); remove.closest('[data-subitem]')?.remove(); if (position) syncMixed(position); }
  });

  document.addEventListener('submit', event => {
    const form = event.target.closest('.tt-document-form'); if (!form) return;
    form.querySelectorAll('[data-service-group]').forEach(syncGroup);
    form.querySelectorAll('[data-position]').forEach(syncMixed);
  });

  window.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-service-group]').forEach(syncGroup);
    document.querySelectorAll('[data-position]').forEach(syncMixed);
  });
})();
