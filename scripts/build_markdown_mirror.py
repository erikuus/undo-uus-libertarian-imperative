#!/usr/bin/env python3
"""Build readability-first markdown mirrors while preserving originals unchanged.

Features:
- Readability-focused normalization for extracted text.
- OCR fallback for image-only PDF pages.
- `--check` mode for forensics-friendly validation.
- Source and mirror fixity manifest generation.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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

MIRROR_FORMAT_VERSION = "readability-v5"
MIRROR_PROFILE = "readability-first"

TESSERACT_CANDIDATES = ["tesseract", "/opt/homebrew/bin/tesseract"]

HEADER_RE = re.compile(
    r"^(From\s|Subject:|To:|Cc:|Bcc:|Date:|Sent:|Reply-To:|In message <|On .+ wrote:|Re:|Fwd:)",
    re.IGNORECASE,
)
SIGNOFF_RE = re.compile(r"^(Yours,|Regards,|Sincerely,|Thanking in advance,|Best,|Cordially,)$", re.IGNORECASE)
DATE_HEADING_RE = re.compile(r"^[A-Z][a-z]+\s+\d{4}$")
TITLE_CONNECTORS = {"a", "an", "and", "as", "at", "be", "can", "for", "in", "is", "of", "on", "or", "the", "to", "with"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate readability-first markdown mirrors.")
    parser.add_argument("--check", action="store_true", help="Validate expected mirror headers/manifests without rewriting files.")
    parser.add_argument("--deterministic", action="store_true", help="Use stable metadata values to avoid volatile timestamps.")
    parser.add_argument("--no-ocr", action="store_true", help="Disable OCR fallback for image-only PDF pages.")
    parser.add_argument("--ocr-lang", default="eng", help="Tesseract language for OCR fallback (default: eng).")
    parser.add_argument(
        "--strict-ocr-check",
        action="store_true",
        help="In --check mode, also require OCR mode headers to match the current local OCR environment.",
    )
    return parser.parse_args()


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
            return False

    return True


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


def merge_wrapped_lines(lines: list[str]) -> str:
    if not lines:
        return ""

    merged = lines[0]
    for nxt in lines[1:]:
        if merged.endswith("-") and nxt and nxt[0].islower():
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


def find_tesseract_command() -> str | None:
    for candidate in TESSERACT_CANDIDATES:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
        candidate_path = Path(candidate)
        if candidate_path.exists() and os.access(candidate_path, os.X_OK):
            return str(candidate_path)
    return None


def tesseract_version(tesseract_cmd: str | None) -> str | None:
    if not tesseract_cmd:
        return None
    try:
        proc = subprocess.run(
            [tesseract_cmd, "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, OSError):
        return None

    first_line = proc.stdout.splitlines()[0] if proc.stdout else ""
    return first_line.strip() or None


def parse_tsv_confidence(tsv_text: str) -> float | None:
    conf: list[float] = []
    lines = tsv_text.splitlines()
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) < 11:
            continue
        value = parts[10].strip()
        if not value or value == "-1":
            continue
        try:
            conf.append(float(value))
        except ValueError:
            continue

    if not conf:
        return None
    return sum(conf) / len(conf)


def ocr_image(image_obj: Any, tesseract_cmd: str, lang: str) -> tuple[str, float | None]:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        image_path = tmp_dir / "page.png"
        txt_base = tmp_dir / "ocr"

        image_obj.save(image_path)

        subprocess.run(
            [tesseract_cmd, str(image_path), str(txt_base), "-l", lang, "--psm", "6"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        ocr_text = txt_base.with_suffix(".txt").read_text(encoding="utf-8", errors="replace")

        subprocess.run(
            [tesseract_cmd, str(image_path), str(txt_base), "-l", lang, "--psm", "6", "tsv"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        tsv_text = txt_base.with_suffix(".tsv").read_text(encoding="utf-8", errors="replace")

    return ocr_text, parse_tsv_confidence(tsv_text)


def ocr_page_images(page: Any, tesseract_cmd: str, lang: str) -> tuple[str, float | None, int]:
    text_chunks: list[str] = []
    confidence: list[float] = []
    image_count = 0

    for image_file in page.images:
        image_count += 1
        image_obj = getattr(image_file, "image", None)
        if image_obj is None and hasattr(image_file, "data") and Image is not None:
            try:
                image_obj = Image.open(io.BytesIO(image_file.data))
            except Exception:
                image_obj = None

        if image_obj is None:
            continue

        try:
            text, conf = ocr_image(image_obj, tesseract_cmd, lang)
        except (subprocess.CalledProcessError, OSError):
            continue

        cleaned = normalize_for_readability(text)
        if cleaned:
            text_chunks.append(cleaned)
        if conf is not None:
            confidence.append(conf)

    if not text_chunks:
        return "", None, image_count

    avg_conf = (sum(confidence) / len(confidence)) if confidence else None
    merged = "\n\n".join(text_chunks)
    return merged, avg_conf, image_count


def extract_pdf_pages(
    path: Path,
    *,
    ocr_enabled: bool,
    tesseract_cmd: str | None,
    ocr_lang: str,
) -> tuple[int, list[tuple[int, str]], list[dict[str, Any]]]:
    reader = PdfReader(str(path))
    pages: list[tuple[int, str]] = []
    ocr_used: list[dict[str, Any]] = []

    for idx, page in enumerate(reader.pages, start=1):
        page_text = normalize_for_readability(page.extract_text() or "")

        if not page_text and ocr_enabled and tesseract_cmd:
            ocr_text, conf, image_count = ocr_page_images(page, tesseract_cmd, ocr_lang)
            if ocr_text:
                page_text = ocr_text
                ocr_used.append({"page": idx, "confidence": conf, "image_count": image_count})

        if not page_text:
            page_text = "(No extractable text on this page. This page may be image-only.)"

        pages.append((idx, page_text))

    return len(reader.pages), pages, ocr_used


def format_ocr_mode(*, ocr_enabled: bool, tesseract_cmd: str | None, ocr_lang: str) -> str:
    if not ocr_enabled:
        return "disabled"
    if not tesseract_cmd:
        return f"unavailable(lang={ocr_lang})"
    return f"enabled(lang={ocr_lang})"


def format_ocr_provenance(*, ocr_enabled: bool, tesseract_cmd: str | None, tess_version: str | None) -> str:
    if not ocr_enabled:
        return "not requested"
    if not tesseract_cmd:
        return "tesseract not found"
    return tess_version or "tesseract (version unknown)"


def header_lines(
    src: Path,
    dest: Path,
    kind: str,
    checksum: str,
    *,
    deterministic: bool,
    ocr_mode: str | None,
    ocr_provenance: str | None,
) -> list[str]:
    stamp = "deterministic" if deterministic else datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    src_rel = repo_rel(src)

    lines = [
        f"# Markdown Copy: `{src_rel}`",
        "",
        "Preservation note: this is a readability-first markdown mirror generated from the original source.",
        "",
        f"- Source type: `{kind}`",
        f"- Source path: `{src_rel}`",
        f"- SHA256: `{checksum}`",
        f"- Mirror format version: `{MIRROR_FORMAT_VERSION}`",
        f"- Mirror profile: `{MIRROR_PROFILE}`",
        f"- Generated: `{stamp}`",
        f"- Original file: `[{src.name}]({rel_posix(dest, src)})`",
    ]

    if kind == "pdf" and ocr_mode is not None:
        lines.append(f"- OCR mode: `{ocr_mode}`")
    if kind == "pdf" and ocr_provenance is not None:
        lines.append(f"- OCR provenance: `{ocr_provenance}`")

    lines.extend([
        "- Normalization: line-wrap unwrapping, separator simplification, and spacing cleanup (content preserved).",
        "",
        "---",
        "",
    ])
    return lines


def write_pdf_copy(
    src: Path,
    dest: Path,
    checksum: str,
    *,
    deterministic: bool,
    ocr_enabled: bool,
    tesseract_cmd: str | None,
    ocr_lang: str,
    tess_version: str | None,
) -> None:
    page_count, pages, ocr_used = extract_pdf_pages(
        src,
        ocr_enabled=ocr_enabled,
        tesseract_cmd=tesseract_cmd,
        ocr_lang=ocr_lang,
    )
    ocr_mode = format_ocr_mode(
        ocr_enabled=ocr_enabled,
        tesseract_cmd=tesseract_cmd,
        ocr_lang=ocr_lang,
    )
    ocr_provenance = format_ocr_provenance(
        ocr_enabled=ocr_enabled,
        tesseract_cmd=tesseract_cmd,
        tess_version=tess_version,
    )

    lines = header_lines(
        src,
        dest,
        "pdf",
        checksum,
        deterministic=deterministic,
        ocr_mode=ocr_mode,
        ocr_provenance=ocr_provenance,
    )
    lines.extend([
        f"This copy contains extracted text from {page_count} page(s).",
        "",
    ])

    if ocr_used:
        summary_parts: list[str] = []
        for item in ocr_used:
            conf = item["confidence"]
            conf_str = f", avg conf {conf:.2f}" if conf is not None else ""
            summary_parts.append(f"p.{item['page']} ({item['image_count']} image(s){conf_str})")
        lines.extend([
            "OCR applied on image-only pages:",
            f"- {'; '.join(summary_parts)}",
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


def write_text_copy(src: Path, dest: Path, checksum: str, *, deterministic: bool) -> None:
    body = normalize_text(src.read_text(encoding="utf-8", errors="replace")).strip()
    lines = header_lines(
        src,
        dest,
        src.suffix.lower().lstrip("."),
        checksum,
        deterministic=deterministic,
        ocr_mode=None,
        ocr_provenance=None,
    )
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


def write_image_copy(src: Path, dest: Path, checksum: str, *, deterministic: bool) -> None:
    dims = image_details(src)
    rel_image = rel_posix(dest, src)
    lines = header_lines(
        src,
        dest,
        "image",
        checksum,
        deterministic=deterministic,
        ocr_mode=None,
        ocr_provenance=None,
    )
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


def read_existing_header(dest: Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    try:
        with dest.open("r", encoding="utf-8", errors="replace") as f:
            for idx, raw in enumerate(f):
                if idx > 80:
                    break
                line = raw.rstrip("\n")
                if line.startswith("- Source path: `") and line.endswith("`"):
                    fields["source_path"] = line[len("- Source path: `") : -1]
                elif line.startswith("- SHA256: `") and line.endswith("`"):
                    fields["sha256"] = line[len("- SHA256: `") : -1]
                elif line.startswith("- Mirror format version: `") and line.endswith("`"):
                    fields["mirror_format_version"] = line[len("- Mirror format version: `") : -1]
                elif line.startswith("- Mirror profile: `") and line.endswith("`"):
                    fields["mirror_profile"] = line[len("- Mirror profile: `") : -1]
                elif line.startswith("- OCR mode: `") and line.endswith("`"):
                    fields["ocr_mode"] = line[len("- OCR mode: `") : -1]
                elif line.startswith("- OCR provenance: `") and line.endswith("`"):
                    fields["ocr_provenance"] = line[len("- OCR provenance: `") : -1]
                elif line.strip() == "---":
                    break
    except FileNotFoundError:
        return {}
    return fields


def needs_regen(
    src: Path,
    dest: Path,
    checksum: str,
    *,
    expected_ocr_mode: str | None,
    compare_ocr_mode: bool,
) -> tuple[bool, str]:
    if not dest.exists():
        return True, "missing"

    existing = read_existing_header(dest)
    if existing.get("source_path") != repo_rel(src):
        return True, "source path mismatch"
    if existing.get("sha256") != checksum:
        return True, "source hash mismatch"
    if existing.get("mirror_format_version") != MIRROR_FORMAT_VERSION:
        return True, "mirror format version mismatch"
    if existing.get("mirror_profile") != MIRROR_PROFILE:
        return True, "mirror profile mismatch"
    if compare_ocr_mode and expected_ocr_mode is not None and existing.get("ocr_mode") != expected_ocr_mode:
        return True, "ocr mode mismatch"

    return False, "ok"


def build_manifest_lines(paths: list[Path]) -> str:
    rows = [f"{file_sha256(path)}  {repo_rel(path)}" for path in sorted(paths, key=lambda p: p.as_posix())]
    return "\n".join(rows) + "\n"


def update_or_check_manifest(path: Path, expected_content: str, *, check_only: bool) -> tuple[bool, str]:
    if check_only:
        if not path.exists():
            return False, f"missing manifest: {repo_rel(path)}"
        current = path.read_text(encoding="utf-8", errors="replace")
        if current != expected_content:
            return False, f"outdated manifest: {repo_rel(path)}"
        return True, "ok"

    path.parent.mkdir(parents=True, exist_ok=True)
    current = path.read_text(encoding="utf-8", errors="replace") if path.exists() else None
    if current != expected_content:
        path.write_text(expected_content, encoding="utf-8")
    return True, "ok"


def main() -> None:
    args = parse_args()

    files = iter_sources()
    if not files:
        raise SystemExit("No archival source files found.")

    ocr_enabled = not args.no_ocr
    tesseract_cmd = find_tesseract_command() if ocr_enabled else None
    tess_version = tesseract_version(tesseract_cmd) if ocr_enabled else None

    DEST_ROOT.mkdir(parents=True, exist_ok=True)

    generated = 0
    checked = 0
    failures: list[str] = []

    for src in files:
        dest = dest_for(src)
        dest.parent.mkdir(parents=True, exist_ok=True)

        checksum = file_sha256(src)
        ext = src.suffix.lower()

        expected_ocr_mode = None
        if ext in PDF_EXTS:
            expected_ocr_mode = format_ocr_mode(
                ocr_enabled=ocr_enabled,
                tesseract_cmd=tesseract_cmd,
                ocr_lang=args.ocr_lang,
            )

        compare_ocr_mode = args.check and args.strict_ocr_check
        regen, reason = needs_regen(
            src,
            dest,
            checksum,
            expected_ocr_mode=expected_ocr_mode,
            compare_ocr_mode=compare_ocr_mode,
        )

        if args.check:
            checked += 1
            if regen:
                failures.append(f"{repo_rel(dest)}: {reason}")
            continue

        if not regen:
            continue

        if ext in PDF_EXTS:
            write_pdf_copy(
                src,
                dest,
                checksum,
                deterministic=args.deterministic,
                ocr_enabled=ocr_enabled,
                tesseract_cmd=tesseract_cmd,
                ocr_lang=args.ocr_lang,
                tess_version=tess_version,
            )
        elif ext in TEXT_EXTS:
            write_text_copy(src, dest, checksum, deterministic=args.deterministic)
        elif ext in IMAGE_EXTS:
            write_image_copy(src, dest, checksum, deterministic=args.deterministic)
        else:
            continue

        generated += 1

    # Fixity manifests
    source_manifest_path = ROOT / "undo-uus-archive" / "manifest-sha256.txt"
    source_manifest = build_manifest_lines(files)
    ok, msg = update_or_check_manifest(source_manifest_path, source_manifest, check_only=args.check)
    if not ok:
        failures.append(msg)

    mirror_files = sorted([p for p in DEST_ROOT.rglob("*.md") if p.is_file()], key=lambda p: p.as_posix())
    mirror_manifest_path = DEST_ROOT / "manifest-sha256.txt"
    mirror_manifest = build_manifest_lines(mirror_files)
    ok, msg = update_or_check_manifest(mirror_manifest_path, mirror_manifest, check_only=args.check)
    if not ok:
        failures.append(msg)

    if args.check:
        if failures:
            for failure in failures:
                print(f"FAIL: {failure}")
            raise SystemExit(1)
        print(f"OK: {checked} mirror files and 2 manifests are up to date.")
        return

    print(f"Generated/updated {generated} markdown copy files in {DEST_ROOT}.")
    print(f"Updated manifests: {repo_rel(source_manifest_path)}, {repo_rel(mirror_manifest_path)}")


if __name__ == "__main__":
    main()
