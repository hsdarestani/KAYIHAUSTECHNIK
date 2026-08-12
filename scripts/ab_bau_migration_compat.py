from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "erp" / "migrations" / "0009_ab_bau_commercial.py"
DST = ROOT / "erp" / "migrations" / "0010_ab_bau_commercial.py"
OLD_DEPENDENCY = 'dependencies = [("erp", "0008_rename_erp_nativ_organiz_1f223e_idx_erp_nativer_organiz_1823cd_idx_and_more")]'
NEW_DEPENDENCY = 'dependencies = [("erp", "0009_site_report_bando_fields")]'

if not SRC.exists() and DST.exists():
    text = DST.read_text(encoding="utf-8")
    if NEW_DEPENDENCY not in text:
        raise RuntimeError("A+Bau commercial migration exists at 0010 but is not chained after B&O site-report migration")
    print("A+Bau migration compatibility already installed")
else:
    if not SRC.exists():
        raise RuntimeError("A+Bau commercial migration source missing before compatibility step")
    text = SRC.read_text(encoding="utf-8")
    if OLD_DEPENDENCY not in text:
        raise RuntimeError("A+Bau commercial migration dependency anchor changed")
    text = text.replace(OLD_DEPENDENCY, NEW_DEPENDENCY, 1)
    DST.write_text(text, encoding="utf-8")
    SRC.unlink()
    print("A+Bau commercial migration chained as 0010 after 0009_site_report_bando_fields")
