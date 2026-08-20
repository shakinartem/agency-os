"""Knowledge Base ingestion helpers.

Parsing is deliberately bounded. This internal V1 supports pasted text plus common office
formats while enforcing byte/page/character limits. A public SaaS should eventually move
complex document parsing into an isolated ingestion worker.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import os
import zipfile
from pathlib import Path

from docx import Document as DocxDocument
from fastapi import HTTPException, UploadFile
from pypdf import PdfReader

MAX_UPLOAD_BYTES = int(os.getenv("KNOWLEDGE_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
MAX_TEXT_CHARS = int(os.getenv("KNOWLEDGE_MAX_TEXT_CHARS", "2000000"))
MAX_PDF_PAGES = int(os.getenv("KNOWLEDGE_MAX_PDF_PAGES", "300"))
MAX_DOCX_UNCOMPRESSED_BYTES = int(os.getenv("KNOWLEDGE_MAX_DOCX_UNCOMPRESSED_BYTES", str(64 * 1024 * 1024)))
MAX_DOCX_ENTRIES = int(os.getenv("KNOWLEDGE_MAX_DOCX_ENTRIES", "5000"))
CHUNK_SIZE = int(os.getenv("KNOWLEDGE_CHUNK_CHARS", "1400"))
CHUNK_OVERLAP = int(os.getenv("KNOWLEDGE_CHUNK_OVERLAP", "200"))

SUPPORTED_SUFFIXES = {".txt", ".md", ".markdown", ".json", ".pdf", ".docx"}


def normalize_text(text: str) -> str:
    text = text.replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    cleaned = "\n".join(lines).strip()
    if len(cleaned) > MAX_TEXT_CHARS:
        raise HTTPException(413, f"Extracted text exceeds {MAX_TEXT_CHARS} characters")
    if len(cleaned) < 20:
        raise HTTPException(422, "Document does not contain enough readable text")
    return cleaned


def checksum_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chunk_text(text: str) -> list[str]:
    """Bounded overlapping chunks with whitespace-aware boundaries."""
    if CHUNK_OVERLAP >= CHUNK_SIZE:
        raise RuntimeError("KNOWLEDGE_CHUNK_OVERLAP must be smaller than KNOWLEDGE_CHUNK_CHARS")
    chunks: list[str] = []
    start = 0
    length = len(text)
    while start < length:
        target_end = min(start + CHUNK_SIZE, length)
        end = target_end
        if target_end < length:
            # Prefer paragraph/sentence/word boundaries without shrinking excessively.
            window_start = max(start + int(CHUNK_SIZE * 0.65), start)
            boundary_slice = text[window_start:target_end]
            candidates = [
                boundary_slice.rfind("\n\n"),
                boundary_slice.rfind(". "),
                boundary_slice.rfind("\n"),
                boundary_slice.rfind(" "),
            ]
            boundary = max(candidates)
            if boundary >= 0:
                end = window_start + boundary + (2 if text[window_start + boundary:window_start + boundary + 2] in {"\n\n", ". "} else 1)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= length:
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return chunks


def _extract_text_sync(raw: bytes, suffix: str, filename: str) -> tuple[str, dict]:
    metadata: dict = {"filename": filename, "size_bytes": len(raw)}
    if suffix in {".txt", ".md", ".markdown"}:
        text = raw.decode("utf-8-sig")
    elif suffix == ".json":
        parsed = json.loads(raw.decode("utf-8-sig"))
        text = json.dumps(parsed, ensure_ascii=False, indent=2)
    elif suffix == ".pdf":
        reader = PdfReader(io.BytesIO(raw), strict=False)
        if len(reader.pages) > MAX_PDF_PAGES:
            raise HTTPException(413, f"PDF exceeds {MAX_PDF_PAGES} pages")
        pages: list[str] = []
        total = 0
        for index, page in enumerate(reader.pages):
            value = page.extract_text() or ""
            if value.strip():
                total += len(value)
                if total > MAX_TEXT_CHARS:
                    raise HTTPException(413, f"Extracted text exceeds {MAX_TEXT_CHARS} characters")
                pages.append(f"[Page {index + 1}]\n{value}")
        text = "\n\n".join(pages)
        metadata["pages"] = len(reader.pages)
    elif suffix == ".docx":
        # DOCX is a ZIP container. Bound uncompressed size/entry count before python-docx expands it.
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_DOCX_ENTRIES:
                raise HTTPException(413, f"DOCX exceeds {MAX_DOCX_ENTRIES} archive entries")
            uncompressed = sum(info.file_size for info in entries)
            if uncompressed > MAX_DOCX_UNCOMPRESSED_BYTES:
                raise HTTPException(413, f"DOCX expands beyond {MAX_DOCX_UNCOMPRESSED_BYTES} bytes")
            if any(info.flag_bits & 0x1 for info in entries):
                raise HTTPException(422, "Encrypted DOCX files are not supported")
            metadata["uncompressed_bytes"] = uncompressed
        document = DocxDocument(io.BytesIO(raw))
        parts: list[str] = []
        total = 0
        for paragraph in document.paragraphs:
            value = paragraph.text.strip()
            if not value:
                continue
            total += len(value)
            if total > MAX_TEXT_CHARS:
                raise HTTPException(413, f"Extracted text exceeds {MAX_TEXT_CHARS} characters")
            parts.append(value)
        text = "\n\n".join(parts)
    else:
        raise HTTPException(415, "Unsupported file type")
    return text, metadata


async def extract_upload(upload: UploadFile) -> tuple[str, str, dict]:
    raw = await upload.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File exceeds {MAX_UPLOAD_BYTES} bytes")

    filename = upload.filename or "knowledge.txt"
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(415, f"Unsupported file type: {suffix or 'unknown'}")

    try:
        text, metadata = await asyncio.wait_for(
            asyncio.to_thread(_extract_text_sync, raw, suffix, filename),
            timeout=float(os.getenv("KNOWLEDGE_PARSE_TIMEOUT_SECONDS", "30")),
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(422, "Document parsing timed out") from exc
    except HTTPException:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        raise HTTPException(422, f"Could not parse {filename}: {exc}") from exc
    except Exception as exc:
        raise HTTPException(422, f"Could not extract readable text from {filename}") from exc

    return normalize_text(text), upload.content_type or "application/octet-stream", metadata
