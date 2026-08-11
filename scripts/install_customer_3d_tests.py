from pathlib import Path
import runpy
import shutil

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "overlays/customer_3d_polish/tests/test_customer_3d_polish.py"
target = ROOT / "tests/test_customer_3d_polish.py"
if not source.exists():
    raise RuntimeError("Missing customer/3D polish regression test overlay")
target.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(source, target)
print("KAYI customer/3D polish regression tests installed.")

# The progressive customer form is installed immediately before this script.
# Harden its optional location validation after the final customer template exists
# so collapsed required controls can never silently block mobile submission.
runpy.run_path(str(ROOT / "scripts" / "fix_customer_save_validation.py"), run_name="__main__")
