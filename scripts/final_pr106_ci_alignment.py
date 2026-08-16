from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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


def guard_inbound_compatibility() -> None:
    # X-KAYI-Inbound-Token is a legacy external protocol name. It intentionally
    # remains stable even though every user-visible product label is now A+Bau.
    # Django may access it via request.headers or META's HTTP_X_KAYI... form.
    needles = ("X-KAYI-Inbound-Token", "HTTP_X_KAYI_INBOUND_TOKEN")
    hits: list[str] = []
    for path in (ROOT / "erp").rglob("*.py"):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        if any(needle in text for needle in needles):
            hits.append(path.relative_to(ROOT).as_posix())
    if not hits:
        raise RuntimeError(
            "Inbound webhook compatibility contract disappeared: expected X-KAYI-Inbound-Token or HTTP_X_KAYI_INBOUND_TOKEN in assembled ERP source"
        )
    print("Inbound webhook compatibility header preserved in: " + ", ".join(hits[:5]))


align_stateful_ai_cache_test()
guard_inbound_compatibility()
print("PR106 CI alignment complete: current AI asset cache version asserted and inbound integration header kept backward-compatible.")
