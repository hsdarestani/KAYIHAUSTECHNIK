from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "templates/rebuild/document_editor.html"
text = path.read_text(encoding="utf-8")
marker = "KAYI document position runtime fallback 20260810"
if marker not in text:
    addition = r'''
{% block scripts %}
<script>
// KAYI document position runtime fallback 20260810
(() => {
  const bind = () => {
    const button = document.querySelector('[data-add-item]');
    const table = document.querySelector('[data-document-items]');
    if (!button || !table || button.dataset.nxAddBound === '1' || button.dataset.nxInlineBound === '1') return;
    button.dataset.nxInlineBound = '1';
    const escapeHtml = (value) => String(value ?? '').replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    const recalc = () => {
      let net = 0;
      let tax = 0;
      table.querySelectorAll('tbody tr').forEach((row) => {
        const qty = Number(row.querySelector('[name="item_quantity"]')?.value || 0);
        const price = Number(row.querySelector('[name="item_price"]')?.value || 0);
        const rate = Number(row.querySelector('[name="item_tax"]')?.value || 0);
        const line = qty * price;
        net += line;
        tax += line * rate / 100;
      });
      const discount = Number(document.querySelector('[name="discount_percent"]')?.value || 0);
      const factor = 1 - Math.max(0, Math.min(100, discount)) / 100;
      net *= factor;
      tax *= factor;
      [['net',net],['tax',tax],['gross',net+tax]].forEach(([key,value]) => {
        const target = document.querySelector(`[data-total="${key}"]`);
        if (target) target.textContent = value.toLocaleString('de-DE',{style:'currency',currency:'EUR'});
      });
    };
    const wire = (row) => {
      row.querySelector('.nx-item-remove')?.addEventListener('click', () => { row.remove(); recalc(); });
      row.querySelectorAll('input').forEach((input) => input.addEventListener('input', recalc));
    };
    button.addEventListener('click', () => {
      const tbody = table.querySelector('tbody');
      if (!tbody) {
        window.alert('Die Positionsliste konnte nicht geladen werden. Bitte Seite neu laden.');
        return;
      }
      const row = document.createElement('tr');
      row.innerHTML = `<td><input class="nx-control desc" name="item_description" placeholder="Leistung oder Material"></td><td><input class="nx-control" name="item_quantity" type="number" min="0" step="0.001" value="1"></td><td><input class="nx-control" name="item_unit" value="Stk."></td><td><input class="nx-control" name="item_price" type="number" min="0" step="0.01" value="0"></td><td><input class="nx-control" name="item_tax" type="number" min="0" step="0.01" value="19"></td><td><button type="button" class="nx-item-remove" aria-label="Position entfernen">×</button></td>`;
      wire(row);
      tbody.append(row);
      recalc();
      row.querySelector('.desc')?.focus();
    });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bind, {once:true});
  else bind();
})();
</script>
{% endblock %}
'''
    text += addition
    path.write_text(text, encoding="utf-8")
print("KAYI document editor has a self-contained runtime fallback for +Position.")
