#!/usr/bin/env python3
"""Build markdown copies for archival browsing while preserving originals unchanged."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = [
    ROOT / "undo_uus_archive" / "_IMPERATIVE_Article",
    ROOT / "undo_uus_archive" / "_IMPERATIVE_Responses",
]
DEST_ROOT = ROOT / "markdown-mirror"
PDF_EXTS = {".pdf"}
TEXT_EXTS = {".txt", ".tex"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff"}
ALL_EXTS = PDF_EXTS | TEXT_EXTS | IMAGE_EXTS


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rel_posix(from_path: Path, to_path: Path) -> str:
    return Path(os.path.relpath(to_path, from_path.parent)).as_posix()


def repo_rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def extract_pdf_pages(path: Path) -> tuple[int, list[tuple[int, str]]]:
    reader = PdfReader(str(path))
    pages: list[tuple[int, str]] = []

    for idx, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        page_text = normalize_text(page_text).strip()
        if not page_text:
            page_text = "(No extractable text on this page. This page may be image-only.)"
        pages.append((idx, page_text))

    return len(reader.pages), pages


def header_lines(src: Path, dest: Path, kind: str, checksum: str) -> list[str]:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    src_rel = repo_rel(src)
    return [
        f"# Markdown Copy: `{src_rel}`",
        "",
        "Preservation note: this is a browsing copy generated from the original source.",
        "",
        f"- Source type: `{kind}`",
        f"- Source path: `{src_rel}`",
        f"- SHA256: `{checksum}`",
        f"- Generated: `{stamp}`",
        f"- Original file: `[{src.name}]({rel_posix(dest, src)})`",
        "",
        "---",
        "",
    ]


def write_pdf_copy(src: Path, dest: Path) -> None:
    checksum = file_sha256(src)
    page_count, pages = extract_pdf_pages(src)
    lines = header_lines(src, dest, "pdf", checksum)
    lines.extend([
        f"This copy contains extracted text from {page_count} page(s).",
        "",
    ])

    for page_num, text in pages:
        lines.extend([
            f"## Page {page_num}",
            "",
            "```text",
            text,
            "```",
            "",
        ])

    dest.write_text("\n".join(lines), encoding="utf-8")


def write_text_copy(src: Path, dest: Path) -> None:
    checksum = file_sha256(src)
    body = normalize_text(src.read_text(encoding="utf-8", errors="replace")).strip()
    lines = header_lines(src, dest, src.suffix.lower().lstrip("."), checksum)
    lines.extend([
        "```text",
        body,
        "```",
        "",
    ])
    dest.write_text("\n".join(lines), encoding="utf-8")


def image_details(src: Path) -> str:
    if Image is None:
        return "unknown"

    try:
        with Image.open(src) as img:
            width, height = img.size
            return f"{width}x{height}"
    except Exception:
        return "unknown"


def write_image_copy(src: Path, dest: Path) -> None:
    checksum = file_sha256(src)
    dims = image_details(src)
    rel_image = rel_posix(dest, src)
    lines = header_lines(src, dest, "image", checksum)
    lines.extend([
        f"Image dimensions: `{dims}`",
        "",
        f"![{src.name}]({rel_image})",
        "",
        "This file is visual source material and does not have a text transcription in this mirror.",
        "",
    ])
    dest.write_text("\n".join(lines), encoding="utf-8")


def iter_sources() -> list[Path]:
    files: list[Path] = []
    for source_dir in SOURCE_DIRS:
        for path in source_dir.rglob("*"):
            if path.is_file() and path.suffix.lower() in ALL_EXTS:
                files.append(path)
    files.sort(key=lambda p: p.as_posix())
    return files


def dest_for(src: Path) -> Path:
    return (DEST_ROOT / src.relative_to(ROOT)).with_suffix(".md")


def main() -> None:
    files = iter_sources()
    if not files:
        raise SystemExit("No archival source files found.")

    DEST_ROOT.mkdir(parents=True, exist_ok=True)

    generated = 0
    for src in files:
        dest = dest_for(src)
        dest.parent.mkdir(parents=True, exist_ok=True)

        ext = src.suffix.lower()
        if ext in PDF_EXTS:
            write_pdf_copy(src, dest)
        elif ext in TEXT_EXTS:
            write_text_copy(src, dest)
        elif ext in IMAGE_EXTS:
            write_image_copy(src, dest)
        else:
            continue

        generated += 1

    print(f"Generated {generated} markdown copy files in {DEST_ROOT}.")


if __name__ == "__main__":
    main()
