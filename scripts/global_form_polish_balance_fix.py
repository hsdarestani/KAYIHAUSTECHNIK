from pathlib import Path

MARKER = "/* KAYI GLOBAL FORM BALANCE FIX */"
path = Path("static/css/app.css")
text = path.read_text(encoding="utf-8")

if MARKER not in text:
    text += r'''

/* KAYI GLOBAL FORM BALANCE FIX */
.kayi-form-polished .kayi-field-balance-last {
  grid-column: 1 / -1;
}
.kayi-form-polished.kayi-direct-grid > :not(.kayi-field):not(input[type="hidden"]):not(.kayi-form-actions) {
  grid-column: 1 / -1;
}
@media (max-width: 760px) {
  .kayi-form-polished .kayi-field-balance-last {
    grid-column: auto;
  }
}
'''
    path.write_text(text, encoding="utf-8")

final = path.read_text(encoding="utf-8")
if MARKER not in final or ".kayi-field-balance-last" not in final:
    raise RuntimeError("Global form balance fix did not apply")

print("KAYI global form balance fix applied and verified.")
