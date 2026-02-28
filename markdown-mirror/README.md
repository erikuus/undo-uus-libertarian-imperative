# markdown-mirror

This folder contains readability-first markdown mirrors of the archival originals.

## Purpose

- Improve readability and searchability in standard git interfaces.
- Keep all source originals untouched in their native formats.
- Simplify text for machine reading by removing extraction noise.
- Maintain source traceability with path and SHA256 metadata in each copy.

## Dependencies

To regenerate the mirror locally:

```bash
python3 -m pip install -r requirements.txt
```

## Normalization Rules

- PDF-derived text is normalized for readability (hard wraps merged into paragraphs, separator blocks normalized to `---`, and spacing cleaned). Page visual layout is not preserved.
- Inline em-dash conventions (` --- `) are normalized to `—` where they occur within a text line.
- Text/TeX sources are mirrored as text (line endings normalized; content preserved) and are not reflowed into paragraphs.

## Scope

The mirror covers all source files in:

- `undo-uus-archive/_IMPERATIVE_Article/*`
- `undo-uus-archive/1997_Libertaarimperatiiv/*` (secondary-language publication context)

Some canonical artifacts may be intentionally excluded from mirroring (for example, full journal-issue scans dominated by third-party content). These remain preserved under `undo-uus-archive/` and covered by fixity manifests.

## Regeneration

Run:

```bash
python3 scripts/build_markdown_mirror.py
```

Validation-only mode:

```bash
python3 scripts/build_markdown_mirror.py --check
```

Note: `--check` validates headers and manifests and can run without installing `requirements.txt`.

Portable behavior:
- By default, `--check` validates stable fields (source path/hash, mirror format/profile, manifests) and does **not** fail due to local OCR engine/version differences.
- Use strict OCR environment matching only when needed:

```bash
python3 scripts/build_markdown_mirror.py --check --strict-ocr-check
```

Deterministic metadata mode:

```bash
python3 scripts/build_markdown_mirror.py --deterministic
```

## Fixity

- `manifest-sha256.txt` in this folder records checksums for markdown mirror files.
- `../undo-uus-archive/manifest-sha256.txt` records checksums for canonical source artifacts.

## Folder Index

- [`undo-uus-archive/_IMPERATIVE_Article/README.md`](undo-uus-archive/_IMPERATIVE_Article/README.md)
- [`undo-uus-archive/1997_Libertaarimperatiiv/README.md`](undo-uus-archive/1997_Libertaarimperatiiv/README.md)
