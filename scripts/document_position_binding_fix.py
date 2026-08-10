from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "static/js/kayi-next.js"
text = path.read_text(encoding="utf-8")
old = """  $$('[data-document-items]').forEach((table) => {\n    table.querySelector('[data-add-item]')?.addEventListener('click', () => addItemRow(table));\n"""
new = """  $$('[data-document-items]').forEach((table) => {\n    const addButton = table.closest('form')?.querySelector('[data-add-item]') || document.querySelector('[data-add-item]');\n    if (addButton) {\n      addButton.dataset.nxAddBound = '1';\n      addButton.addEventListener('click', () => addItemRow(table));\n    }\n"""
if new not in text:
    if old not in text:
        raise RuntimeError("Original KAYI document-position binding contract changed")
    text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
print("KAYI quote/invoice +Position is bound from the document form instead of incorrectly searching inside the table.")
