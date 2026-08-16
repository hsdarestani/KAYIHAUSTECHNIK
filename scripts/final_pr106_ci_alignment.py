from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY_INBOUND_HEADER = "X-KAYI-Inbound-Token"
BROKEN_REBRANDED_HEADER = "X-A+Bau-Inbound-Token"


def align_stateful_ai_cache_test() -> None:
    path = ROOT / "tests" / "test_ai_stateful_entity_chat.py"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    old = r'kayi-next\.js.*\?v=202608(?:11-[0-9]+|12-runtime-[0-9]+|12-owner-review-[0-9]+)'
    new = r'kayi-next\.js.*\?v=20260816-owner-commercial-ai-safe-1'
    if old in text:
        text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")


def restore_inbound_protocol_compatibility() -> None:
    """Keep the external webhook protocol stable across the visible A+Bau rebrand.

    X-KAYI-Inbound-Token is a legacy machine-to-machine API contract. It is not
    visible product copy and must not be renamed, because existing GMX bridges and
    Django tests send it as HTTP_X_KAYI_INBOUND_TOKEN.
    """
    touched: list[str] = []
    for path in (ROOT / "erp").rglob("*.py"):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        if BROKEN_REBRANDED_HEADER not in text:
            continue
        updated = text.replace(BROKEN_REBRANDED_HEADER, LEGACY_INBOUND_HEADER)
        path.write_text(updated, encoding="utf-8")
        touched.append(path.relative_to(ROOT).as_posix())

    workflow = ROOT / "erp" / "workflow_views.py"
    if not workflow.exists():
        raise RuntimeError("Inbound webhook implementation is missing from assembled source")
    source = workflow.read_text(encoding="utf-8")
    if LEGACY_INBOUND_HEADER not in source:
        raise RuntimeError("Legacy inbound webhook header was not restored")
    if BROKEN_REBRANDED_HEADER in source:
        raise RuntimeError("Broken rebranded inbound webhook header is still active")

    # The regression test deliberately sends Django's META form of the same header.
    test_path = ROOT / "tests" / "test_workflow_release.py"
    if test_path.exists():
        test_source = test_path.read_text(encoding="utf-8")
        if "HTTP_X_KAYI_INBOUND_TOKEN" not in test_source:
            raise RuntimeError("Inbound webhook regression coverage no longer exercises the legacy protocol header")

    print(
        "Inbound webhook compatibility restored with stable X-KAYI-Inbound-Token"
        + (f" in {', '.join(touched)}" if touched else "")
        + "."
    )


align_stateful_ai_cache_test()
restore_inbound_protocol_compatibility()
print("PR106 CI alignment complete: current AI asset cache version asserted and inbound webhook protocol preserved across A+Bau branding.")
