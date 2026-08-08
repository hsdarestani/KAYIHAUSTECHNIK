from pathlib import Path

path = Path("static/js/app.js")
text = path.read_text(encoding="utf-8")
old = '      if (extraClass) box.classList.add(extraClass);'
new = '''      if (extraClass) {
        box.classList.add(...extraClass.split(/\\s+/).filter(Boolean));
      }'''

if new not in text:
    if old not in text:
        raise RuntimeError("Event form class assignment marker not found")
    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")

if new not in path.read_text(encoding="utf-8"):
    raise RuntimeError("Event form multi-class assignment fix did not apply")

print("KAYI event form class assignment fix applied and verified.")
