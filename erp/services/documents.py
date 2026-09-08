from __future__ import annotations

import multiprocessing as mp
from pathlib import Path
from typing import Optional

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".docx", ".xlsx", ".csv", ".txt"}
MAX_EXTRACT_BYTES = 25 * 1024 * 1024


def validate_upload(upload) -> None:
    suffix = Path(upload.name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Dateityp {suffix or 'unbekannt'} ist nicht erlaubt.")
    if upload.size > MAX_EXTRACT_BYTES:
        raise ValueError("Datei ist größer als 25 MB.")
    head = upload.read(8)
    upload.seek(0)
    if suffix == ".pdf" and not head.startswith(b"%PDF-"):
        raise ValueError("Ungültige PDF-Signatur.")
    if suffix in {".jpg", ".jpeg"} and not head.startswith(b"\xff\xd8\xff"):
        raise ValueError("Ungültige JPEG-Signatur.")
    if suffix == ".png" and not head.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Ungültige PNG-Signatur.")


def _extract_pdf_worker(path: str, queue) -> None:
    try:
        import fitz
        doc = fitz.open(path)
        text = "\n".join(page.get_text("text") for page in doc[:100])
        queue.put((True, text[:500_000]))
    except Exception as exc:  # pragma: no cover - subprocess boundary
        queue.put((False, str(exc)))


def extract_text(path: str, timeout: int = 30) -> str:
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        ctx = mp.get_context("spawn")
        queue = ctx.Queue()
        process = ctx.Process(target=_extract_pdf_worker, args=(path, queue))
        process.start()
        process.join(timeout)
        if process.is_alive():
            process.terminate()
            process.join(2)
            raise TimeoutError("PDF-Extraktion hat das Zeitlimit überschritten.")
        if queue.empty():
            return ""
        ok, payload = queue.get()
        if not ok:
            raise RuntimeError(payload)
        return payload
    if suffix in {".txt", ".csv"}:
        return Path(path).read_text(encoding="utf-8", errors="replace")[:500_000]
    return ""
