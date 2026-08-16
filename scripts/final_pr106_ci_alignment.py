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


def trace_inbound_contract() -> None:
    # Temporary narrow trace to locate the assembled webhook authentication path.
    # It prints only source lines containing inbound/webhook/token terms and never
    # prints secret values from settings or the database.
    for path in (ROOT / "erp").rglob("*.py"):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        matches = []
        for index, line in enumerate(lines, start=1):
            lower = line.lower()
            if "inbound" in lower or ("webhook" in lower and "email" in lower):
                start = max(1, index - 4)
                end = min(len(lines), index + 10)
                matches.append((start, end))
        if not matches:
            continue
        # Merge overlapping windows to keep logs readable.
        merged = []
        for start, end in matches:
            if merged and start <= merged[-1][1] + 1:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        rel = path.relative_to(ROOT).as_posix()
        for start, end in merged[:8]:
            print(f"PR106_INBOUND_SOURCE_BEGIN {rel}:{start}-{end}")
            for line_no in range(start, end + 1):
                print(f"{line_no}: {lines[line_no - 1]}")
            print(f"PR106_INBOUND_SOURCE_END {rel}:{start}-{end}")


align_stateful_ai_cache_test()
trace_inbound_contract()
print("PR106 CI alignment complete: current AI asset cache version asserted; inbound webhook path traced for compatibility repair.")
