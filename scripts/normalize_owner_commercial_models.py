from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "erp" / "models.py"
text = TARGET.read_text(encoding="utf-8")

# The commercial settings are internal persistence helpers. Keep their model state
# exactly equal to the generated migration; custom verbose Meta labels would create
# a pointless follow-up AlterModelOptions migration on every deterministic assembly.
for block in (
    '''\n    class Meta:\n        verbose_name = "Projektkalkulation"\n        verbose_name_plural = "Projektkalkulationen"\n''',
    '''\n    class Meta:\n        verbose_name = "Terminkalkulation"\n        verbose_name_plural = "Terminkalkulationen"\n''',
):
    text = text.replace(block, "")

TARGET.write_text(text, encoding="utf-8")
verify = TARGET.read_text(encoding="utf-8")
if 'verbose_name = "Projektkalkulation"' in verify or 'verbose_name = "Terminkalkulation"' in verify:
    raise RuntimeError("Commercial model Meta normalization failed")
print("A+Bau commercial helper models aligned with migration state.")
