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

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = [
    ROOT / "undo-uus-archive" / "_IMPERATIVE_Article",
    ROOT / "undo-uus-archive" / "_IMPERATIVE_Responses",
    ROOT / "undo-uus-archive" / "1997_Libertaarimperatiiv",
]
DEST_ROOT = ROOT / "markdown-mirror"
PDF_EXTS = {".pdf"}
TEXT_EXTS = {".txt", ".tex"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff"}
ALL_EXTS = PDF_EXTS | TEXT_EXTS | IMAGE_EXTS

# Some canonical artifacts are intentionally not mirrored (e.g., full journal-issue scans that
# contain mostly third-party content). They remain in fixity manifests.
MIRROR_EXCLUDE_SOURCE_RELS = {
    "undo-uus-archive/1997_Libertaarimperatiiv/Akadeemia_1997_10_0001.pdf",
    # Response dossier is intentionally handled via a human-edited reader layer.
    "undo-uus-archive/_IMPERATIVE_Responses/Responses-to-Imperative.pdf",
}

MIRROR_FORMAT_VERSION = "readability-v13"
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
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate mirror files even if they appear up to date (refreshes the `Generated` timestamp).",
    )
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
    normalized = normalized.translate(_UNICODE_LIGATURE_TRANSLATION)
    return normalized


_UNICODE_LIGATURE_TRANSLATION = str.maketrans(
    {
        # Common PDF extraction artifacts: Latin presentation-form ligatures.
        "\ufb00": "ff",   # ﬀ
        "\ufb01": "fi",   # ﬁ
        "\ufb02": "fl",   # ﬂ
        "\ufb03": "ffi",  # ﬃ
        "\ufb04": "ffl",  # ﬄ
        "\ufb05": "ft",   # ﬅ (rare)
        "\ufb06": "st",   # ﬆ (rare)
    }
)


_LATIN_LETTER_CLASS = r"A-Za-zÀ-ÖØ-öø-ÿÕÄÖÜõäöü"
_LATIN_LOWER_CLASS = r"a-zà-öø-ÿõäöü"
_LATIN_UPPER_CLASS = r"A-ZÀ-ÖÕÄÖÜ"


def repair_common_extracted_text_artifacts(text: str) -> str:
    """Repair common OCR/PDF-extraction artifacts without changing semantics."""
    repaired = normalize_text(text)
    repaired = re.sub(rf",(?=[{_LATIN_LETTER_CLASS}])", ", ", repaired)
    repaired = re.sub(rf"([{_LATIN_LOWER_CLASS}])\.([{_LATIN_UPPER_CLASS}])", r"\1. \2", repaired)
    return repaired


def strip_trailing_page_number_line(text: str, *, page_num: int) -> str:
    """Remove a trailing footer page number line when it matches the PDF page index."""
    lines = text.splitlines()
    if not lines:
        return text

    last_idx = None
    for idx in range(len(lines) - 1, -1, -1):
        if lines[idx].strip() != "":
            last_idx = idx
            break
    if last_idx is None:
        return text

    candidate = lines[last_idx].strip()
    if candidate.isdigit() and int(candidate) == page_num and len(candidate) <= 3:
        del lines[last_idx]
        return "\n".join(lines).rstrip("\n")
    return text


def repair_pdf_page_boundaries(pages: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Join hyphen-broken words and remove footer page numbers across PDF pages."""
    if not pages:
        return pages

    page_nums = [num for num, _ in pages]
    texts = [repair_common_extracted_text_artifacts(text) for _, text in pages]
    texts = [strip_trailing_page_number_line(text, page_num=page_num) for text, page_num in zip(texts, page_nums)]

    def last_nonempty(lines: list[str]) -> int | None:
        for idx in range(len(lines) - 1, -1, -1):
            if lines[idx].strip() != "":
                return idx
        return None

    def first_nonempty(lines: list[str]) -> int | None:
        for idx, line in enumerate(lines):
            if line.strip() != "":
                return idx
        return None

    for i in range(len(texts) - 1):
        prev_lines = texts[i].splitlines()
        next_lines = texts[i + 1].splitlines()

        prev_last = last_nonempty(prev_lines)
        next_first = first_nonempty(next_lines)
        if prev_last is None or next_first is None:
            continue

        prev_line = prev_lines[prev_last]
        next_line = next_lines[next_first].lstrip()
        if not next_line:
            continue

        # Join only likely word-break hyphens (letters + '-' + next page starts lowercase),
        # but keep page segmentation by moving only the continuation fragment.
        if prev_line.endswith("-") and len(prev_line) >= 2 and prev_line[-2].isalpha() and next_line[0].islower():
            m = re.match(rf"^([{_LATIN_LOWER_CLASS}]+)(.*)$", next_line)
            if not m:
                continue
            continuation, rest = m.group(1), m.group(2)
            prev_lines[prev_last] = prev_line[:-1] + continuation
            rest = rest.lstrip()
            if rest:
                next_lines[next_first] = rest
            else:
                del next_lines[next_first]
            texts[i] = "\n".join(prev_lines)
            texts[i + 1] = "\n".join(next_lines)

    return list(zip(page_nums, texts))


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
    # Convert triple-hyphen em-dash conventions to a real em dash, but only inline.
    # Standalone separator lines are handled elsewhere and remain `---`.
    merged = re.sub(r"\s---\s", " — ", merged)
    merged = re.sub(r"\s---$", " —", merged)
    return merged


UMLAUT_COMPOSED = {
    "A": "Ä",
    "a": "ä",
    "O": "Ö",
    "o": "ö",
    "U": "Ü",
    "u": "ü",
}


def repair_decomposed_umlauts(text: str) -> str:
    # Common PDF extraction artifact: `¨ o` / `o ¨` style decomposed umlauts.
    # Keep conservative: only compose A/O/U (German/Scandinavian/Estonian overlap).
    text = re.sub(r"\u00a8\s*([AaOoUu])", lambda m: UMLAUT_COMPOSED[m.group(1)], text)
    text = re.sub(r"([AaOoUu])\s*\u00a8", lambda m: UMLAUT_COMPOSED[m.group(1)], text)
    return text


def split_editorial_note(text: str) -> list[str]:
    m = re.match(r"^(Editorial note)\s+(.*)$", text, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return [text]
    label = m.group(1)
    rest = m.group(2).strip()
    if not rest:
        return [label]
    return [label, rest]


def split_inline_footer_blocks(text: str) -> list[str]:
    # Journals often carry "Correspondence:" / "E-mail:" blocks that get merged into
    # surrounding prose during extraction. Split them into their own paragraphs.
    repaired = re.sub(r"\.(E-?mail:)", r". \1", text)
    repaired = re.sub(r"\.\s*;\s*(\d{3,4})\.?$", r".\n\n\1", repaired)

    tokens = [r"\bCorrespondence:", r"\bE-?mail:"]
    parts: list[str] = [repaired]
    for token in tokens:
        next_parts: list[str] = []
        for part in parts:
            m = re.search(token, part)
            if m and m.start() > 0:
                before = part[: m.start()].rstrip()
                after = part[m.start() :].lstrip()
                if before:
                    next_parts.append(before)
                if after:
                    next_parts.append(after)
            else:
                next_parts.append(part)
        parts = next_parts

    return parts


QUOTE_ANCHOR_RE = re.compile(r">\s*(Dear|From:|To:|Subject:|Many\s+thanks|Thanks|Hi|Hello)\b", re.IGNORECASE)
QUOTE_CONTEXT_RE = re.compile(r"\b(wrote|writes)\b", re.IGNORECASE)


def reflow_inline_quotes_to_lines(text: str) -> list[str]:
    # Email quote markers sometimes collapse into a single line, e.g.:
    # `writes >Dear ... > >Many ... Undo >`
    if text.count(">") < 2 or (
        not QUOTE_ANCHOR_RE.search(text) and not QUOTE_CONTEXT_RE.search(text) and not text.lstrip().startswith(">")
    ):
        return [text]

    s = text
    s = re.sub(r"\s+(>+)\s*(?=\S)", r"\n\1 ", s)
    while True:
        new = re.sub(r">\s+>", ">\n>", s)
        if new == s:
            break
        s = new
    s = re.sub(r"(?m)^(>+)(?=\S)", r"\1 ", s)

    raw_lines = [ln.rstrip() for ln in s.splitlines()]
    lines: list[str] = []
    for ln in raw_lines:
        if not lines:
            lines.append(ln)
            continue

        if ln.lstrip().startswith(">") and lines[-1] and not lines[-1].lstrip().startswith(">"):
            lines.append("")
        lines.append(ln)

    return lines


def paragraph_to_lines(paragraph: list[str]) -> list[str]:
    merged = merge_wrapped_lines(paragraph)
    merged = repair_decomposed_umlauts(merged)
    merged = re.sub(r"^(>+)(?=\S)", r"\1 ", merged)
    merged = repair_common_extracted_text_artifacts(merged)

    out: list[str] = []
    for block in split_inline_footer_blocks(merged):
        for part in split_editorial_note(block):
            out.extend(reflow_inline_quotes_to_lines(part))
        out.append("")

    while out and out[-1] == "":
        out.pop()
    return out


def normalize_for_readability(text: str) -> str:
    lines = normalize_text(text).split("\n")
    out: list[str] = []
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            out.extend(paragraph_to_lines(paragraph))
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
            out.append(repair_decomposed_umlauts(line))
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


ESTONIAN_TEXT_REPAIR_VERSION = "estonian-diacritics-v9"
# Some sources encode diacritics as separate “mark” characters near the base letter.
# We repair the common cases for Estonian text.
ESTONIAN_MARKS = {"\u00a8", "\u02dc", "\u02c6", "\u02c7"}  # diaeresis, small tilde, circumflex, caron
ESTONIAN_DIAERESIS_LETTERS = {"Ä", "Ö", "Ü", "ä", "ö", "ü"}
ESTONIAN_TILDE_LETTERS = {"Õ", "õ"}
ESTONIAN_BASE_PRECEDES_DIACRITIC_RE = re.compile(r"([AaOoUu])([ÄäÖöÜüÕõ])")
ESTONIAN_COMPOSED = {
    ("\u00a8", "A"): "Ä",
    ("\u00a8", "a"): "ä",
    ("\u00a8", "O"): "Ö",
    ("\u00a8", "o"): "ö",
    ("\u00a8", "U"): "Ü",
    ("\u00a8", "u"): "ü",
    ("\u02dc", "O"): "Õ",
    ("\u02dc", "o"): "õ",
    # Some extraction paths emit U+02C6 (ˆ) where a caron should be applied.
    ("\u02c6", "Z"): "Ž",
    ("\u02c6", "z"): "ž",
    ("\u02c6", "S"): "Š",
    ("\u02c6", "s"): "š",
    ("\u02c7", "Z"): "Ž",
    ("\u02c7", "z"): "ž",
    ("\u02c7", "S"): "Š",
    ("\u02c7", "s"): "š",
}
ESTONIAN_MARK_THEN_LETTER_RE = re.compile(r"([\u00a8\u02dc\u02c6\u02c7])\s*([A-Za-z])")
ESTONIAN_LETTER_THEN_MARK_RE = re.compile(r"([A-Za-zÄÖÜÕäöüõ])\s*([\u00a8\u02dc\u02c6\u02c7])")
ESTONIAN_SPLIT_WORD_AFTER_CAP_RE = re.compile(r"(^|[\s(\[{\"'“‘«])([ÄÖÜÕ])\s+([a-zäöüõ])", re.MULTILINE)
ESTONIAN_SINGLE_LETTER_BEFORE_DIACRITIC_START_RE = re.compile(
    r"\b([BCDFGHJKLMNPQRSTVWXYZbcdfghjklmnpqrstvwxyz])\s+([ÄÖÜÕäöüõ])(?=[A-Za-zÄÖÜÕäöüõ])"
)
ESTONIAN_TOKEN_BEFORE_DIACRITIC_START_RE = re.compile(r"\b([A-Za-z]{3,})\s+([ÄÖÜÕäöüõ])(?=[A-Za-zÄÖÜÕäöüõ])")
ESTONIAN_DIACRITIC_JOIN_BIGRAMS = {
    "kä",
    "lä",
    "nä",
    "pä",
    "tä",
    "vä",
    "jä",
    "sä",
    "rä",
    "hä",
    "mõ",
    "võ",
    "tõ",
    "põ",
    "kõ",
    "sõ",
    "lõ",
    "rõ",
    "nõ",
    "jõ",
    "hõ",
    "kü",
    "tü",
    "pü",
    "lü",
    "sü",
    "hü",
    "nü",
    "rü",
    "fü",
    "tö",
    "kö",
    "lö",
    "pö",
    "sö",
    "rö",
    "hö",
    "mö",
}
ESTONIAN_DO_NOT_JOIN_LEFT_TOKENS = {
    "veel",
    "seal",
    "siin",
    "aga",
    "kuid",
    "ning",
    "sest",
    "enne",
    "peale",
    "pärast",
    "mitte",
    "seda",
    "see",
    "selle",
    "sellest",
    "meie",
    "teie",
    "nende",
    "tema",
    "mina",
    "sina",
    "siis",
}
ESTONIAN_SUFFIX_JOIN_RE = re.compile(r"\b([a-zäöüõ]{3,})\s+(atuse|valt|sed)\b")
ESTONIAN_OLE_JOIN_RE = re.compile(r"\bol\s+e\b")


def estonian_text_repair_tag(src: Path) -> str | None:
    try:
        rel = src.relative_to(ROOT).as_posix()
    except Exception:
        return None
    if rel.startswith("undo-uus-archive/1997_Libertaarimperatiiv/"):
        return ESTONIAN_TEXT_REPAIR_VERSION
    return None


def repair_estonian_diacritics(text: str) -> str:
    if not text:
        return text

    def mark_then_letter(m: re.Match[str]) -> str:
        mark, letter = m.group(1), m.group(2)
        return ESTONIAN_COMPOSED.get((mark, letter), m.group(0))

    def letter_then_mark(m: re.Match[str]) -> str:
        letter, mark = m.group(1), m.group(2)
        composed = ESTONIAN_COMPOSED.get((mark, letter))
        if composed is not None:
            return composed
        if mark == "\u00a8" and letter in ESTONIAN_DIAERESIS_LETTERS:
            return letter
        if mark == "\u02dc" and letter in ESTONIAN_TILDE_LETTERS:
            return letter
        return m.group(0)

    repaired = ESTONIAN_MARK_THEN_LETTER_RE.sub(mark_then_letter, text)
    repaired = ESTONIAN_LETTER_THEN_MARK_RE.sub(letter_then_mark, repaired)
    repaired = ESTONIAN_SPLIT_WORD_AFTER_CAP_RE.sub(r"\1\2\3", repaired)
    repaired = ESTONIAN_SINGLE_LETTER_BEFORE_DIACRITIC_START_RE.sub(r"\1\2", repaired)

    def join_token_before_diacritic(m: re.Match[str]) -> str:
        left, right = m.group(1), m.group(2)
        left_lower = left.lower()
        bigram = (left_lower[-1] + right.lower())
        if left_lower in ESTONIAN_DO_NOT_JOIN_LEFT_TOKENS:
            return m.group(0)
        if bigram not in ESTONIAN_DIACRITIC_JOIN_BIGRAMS:
            return m.group(0)
        return f"{left}{right}"

    repaired = ESTONIAN_TOKEN_BEFORE_DIACRITIC_START_RE.sub(join_token_before_diacritic, repaired)
    repaired = ESTONIAN_SUFFIX_JOIN_RE.sub(r"\1\2", repaired)
    repaired = ESTONIAN_OLE_JOIN_RE.sub("ole", repaired)

    def base_before_diacritic(m: re.Match[str]) -> str:
        base, diacritic = m.group(1), m.group(2)
        base_lower = base.lower()
        di_lower = diacritic.lower()

        required_base = "a" if di_lower == "ä" else "o" if di_lower in {"ö", "õ"} else "u" if di_lower == "ü" else None
        if required_base != base_lower:
            return m.group(0)

        if base.isupper():
            di_for_base = diacritic.upper()
        else:
            di_for_base = diacritic.lower()

        return f"{di_for_base}{diacritic}"

    repaired = ESTONIAN_BASE_PRECEDES_DIACRITIC_RE.sub(base_before_diacritic, repaired)
    return repaired


def apply_language_repairs(text: str, *, src: Path) -> str:
    if estonian_text_repair_tag(src) is not None:
        return repair_estonian_diacritics(text)
    return text


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
    # Lazy import so `--check` can run without optional PDF/OCR dependencies.
    try:
        from pypdf import PdfReader  # type: ignore
    except ModuleNotFoundError as e:
        raise SystemExit(
            "Missing dependency: pypdf. Install dependencies with: "
            "`python3 -m pip install -r requirements.txt`"
        ) from e

    reader = PdfReader(str(path))
    pages: list[tuple[int, str]] = []
    ocr_used: list[dict[str, Any]] = []

    for idx, page in enumerate(reader.pages, start=1):
        page_text = normalize_for_readability(page.extract_text() or "")
        page_text = apply_language_repairs(page_text, src=path)
        page_text = repair_common_extracted_text_artifacts(page_text)

        if not page_text and ocr_enabled and tesseract_cmd:
            ocr_text, conf, image_count = ocr_page_images(page, tesseract_cmd, ocr_lang)
            if ocr_text:
                page_text = apply_language_repairs(ocr_text, src=path)
                page_text = repair_common_extracted_text_artifacts(page_text)
                ocr_used.append({"page": idx, "confidence": conf, "image_count": image_count})

        if not page_text:
            page_text = "(No extractable text on this page. This page may be image-only.)"

        pages.append((idx, page_text))

    pages = repair_pdf_page_boundaries(pages)
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
    text_repair = estonian_text_repair_tag(src)
    if text_repair is not None:
        lines.append(f"- Text repair: `{text_repair}`")

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
        # Ensure code blocks never contain trailing spaces.
        text = "\n".join(ln.rstrip() for ln in text.splitlines()).rstrip("\n")
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
    body = apply_language_repairs(body, src=src)
    body = repair_common_extracted_text_artifacts(body)
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
        "\n".join(ln.rstrip() for ln in body.splitlines()).rstrip("\n"),
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


def iter_source_artifacts() -> list[Path]:
    files: list[Path] = []
    for source_dir in SOURCE_DIRS:
        for path in source_dir.rglob("*"):
            if path.is_file() and path.suffix.lower() in ALL_EXTS:
                files.append(path)
    files.sort(key=lambda p: p.as_posix())
    return files


def iter_mirror_sources(artifacts: list[Path]) -> list[Path]:
    sources: list[Path] = []
    for path in artifacts:
        if repo_rel(path) in MIRROR_EXCLUDE_SOURCE_RELS:
            continue
        sources.append(path)
    return sources


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
                elif line.startswith("- Text repair: `") and line.endswith("`"):
                    fields["text_repair"] = line[len("- Text repair: `") : -1]
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
    expected_text_repair = estonian_text_repair_tag(src)
    if expected_text_repair is not None and existing.get("text_repair") != expected_text_repair:
        return True, "text repair tag mismatch"

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
    if args.check and args.force:
        raise SystemExit("--force cannot be combined with --check.")

    artifacts = iter_source_artifacts()
    if not artifacts:
        raise SystemExit("No archival source files found.")
    files = iter_mirror_sources(artifacts)

    # In `--check` mode, default behavior should be pure-validation and should not
    # require OCR tooling or PDF parsing libraries. OCR environment matching is
    # only relevant when explicitly requested via `--strict-ocr-check`.
    if args.check and not args.strict_ocr_check:
        ocr_enabled = False
        tesseract_cmd = None
        tess_version = None
    else:
        ocr_enabled = not args.no_ocr
        tesseract_cmd = find_tesseract_command() if ocr_enabled else None
        tess_version = tesseract_version(tesseract_cmd) if ocr_enabled else None

    if not args.check:
        DEST_ROOT.mkdir(parents=True, exist_ok=True)

    generated = 0
    checked = 0
    failures: list[str] = []

    for src in files:
        dest = dest_for(src)
        if not args.check:
            dest.parent.mkdir(parents=True, exist_ok=True)

        checksum = file_sha256(src)
        ext = src.suffix.lower()

        expected_ocr_mode = None
        if ext in PDF_EXTS and (not args.check or args.strict_ocr_check):
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
        if args.force:
            regen, reason = True, "forced"

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
    source_manifest = build_manifest_lines(artifacts)
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
