#!/usr/bin/env python3
"""Build readability-first markdown mirrors while preserving originals unchanged."""

from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = [
    ROOT / "undo-uus-archive" / "_IMPERATIVE_Article",
    ROOT / "undo-uus-archive" / "_IMPERATIVE_Responses",
]
DEST_ROOT = ROOT / "markdown-mirror"
PDF_EXTS = {".pdf"}
TEXT_EXTS = {".txt", ".tex"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff"}
ALL_EXTS = PDF_EXTS | TEXT_EXTS | IMAGE_EXTS
HEADER_RE = re.compile(
    r"^(From\s|Subject:|To:|Cc:|Bcc:|Date:|Sent:|Reply-To:|In message <|On .+ wrote:|Re:|Fwd:)",
    re.IGNORECASE,
)
SIGNOFF_RE = re.compile(r"^(Yours,|Regards,|Sincerely,|Thanking in advance,|Best,|Cordially,)$", re.IGNORECASE)
DATE_HEADING_RE = re.compile(r"^[A-Z][a-z]+\s+\d{4}$")
TITLE_CONNECTORS = {"a", "an", "and", "as", "at", "be", "can", "for", "in", "is", "of", "on", "or", "the", "to", "with"}


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
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace("\u00a0", " ")
    return normalized


def clean_line(line: str) -> str:
    line = line.replace("\t", " ")
    line = re.sub(r"\s+", " ", line.strip())
    return line


def is_separator_line(line: str) -> bool:
    compressed = line.replace(" ", "")
    if len(compressed) < 8:
        return False
    return bool(re.fullmatch(r"[-=_.~*•·]+", compressed))


def is_structural_line(line: str) -> bool:
    if HEADER_RE.match(line):
        return True
    if SIGNOFF_RE.match(line):
        return True
    if DATE_HEADING_RE.match(line):
        return True
    if line.isdigit() and len(line) <= 3:
        return True
    if line.endswith(":") and len(line) <= 40:
        return True
    if is_title_heading_line(line):
        return True
    return False


def is_title_heading_line(line: str) -> bool:
    if "." in line and not line.endswith("?"):
        return False
    if "," in line or ";" in line or ":" in line:
        return False
    words = line.split()
    if not 2 <= len(words) <= 12:
        return False

    alpha_words = [w.strip("()[]{}'\"-") for w in words]
    if any(not w for w in alpha_words):
        return False

    for i, word in enumerate(alpha_words):
        lower = word.lower()
        if lower in TITLE_CONNECTORS:
            continue
        if word[0].isalpha() and not word[0].isupper():
            return False
        if i == 0 and word.isupper():
            # Avoid turning section-body shouting artifacts into headings.
            return False

    return True


def merge_wrapped_lines(lines: list[str]) -> str:
    if not lines:
        return ""

    merged = lines[0]
    for nxt in lines[1:]:
        if merged.endswith("-") and nxt and nxt[0].islower():
            # Join words split by extraction line-wrap hyphenation.
            merged = merged[:-1] + nxt
        else:
            merged = f"{merged} {nxt}"

    merged = re.sub(r"\s+", " ", merged).strip()
    merged = re.sub(r"\s+([,.;:!?])", r"\1", merged)
    return merged


def normalize_for_readability(text: str) -> str:
    lines = normalize_text(text).split("\n")
    out: list[str] = []
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            out.append(merge_wrapped_lines(paragraph))
            paragraph.clear()

    for raw in lines:
        line = clean_line(raw)
        if not line:
            flush_paragraph()
            if out and out[-1] != "":
                out.append("")
            continue

        if is_separator_line(line):
            flush_paragraph()
            if not out or out[-1] != "---":
                out.append("---")
            continue

        if is_structural_line(line):
            flush_paragraph()
            out.append(line)
            continue

        if out and SIGNOFF_RE.match(out[-1]) and re.fullmatch(r"[A-Za-z][A-Za-z .'-]{0,39}", line):
            flush_paragraph()
            out.append(line)
            continue

        paragraph.append(line)

    flush_paragraph()

    compact: list[str] = []
    for line in out:
        if line == "":
            if compact and compact[-1] != "":
                compact.append("")
        else:
            compact.append(line)

    while compact and compact[-1] == "":
        compact.pop()

    return "\n".join(compact)


def extract_pdf_pages(path: Path) -> tuple[int, list[tuple[int, str]]]:
    reader = PdfReader(str(path))
    pages: list[tuple[int, str]] = []

    for idx, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        page_text = normalize_for_readability(page_text)
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
        "Preservation note: this is a readability-first markdown mirror generated from the original source.",
        "",
        f"- Source type: `{kind}`",
        f"- Source path: `{src_rel}`",
        f"- SHA256: `{checksum}`",
        f"- Generated: `{stamp}`",
        f"- Original file: `[{src.name}]({rel_posix(dest, src)})`",
        "- Normalization: line-wrap unwrapping, separator simplification, and spacing cleanup (content preserved).",
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
    body = normalize_for_readability(src.read_text(encoding="utf-8", errors="replace"))
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
