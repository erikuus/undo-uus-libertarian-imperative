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
- Text/TeX sources are mirrored as text (line endings normalized; content preserved) and are not reflowed into paragraphs.

## Scope

The mirror covers all source files in:

- `undo-uus-archive/_IMPERATIVE_Article/*`
- `undo-uus-archive/_IMPERATIVE_Responses/*`

## Regeneration

Run:

```bash
python3 scripts/build_markdown_mirror.py
```

Validation-only mode:

```bash
python3 scripts/build_markdown_mirror.py --check
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
- [`undo-uus-archive/_IMPERATIVE_Responses/README.md`](undo-uus-archive/_IMPERATIVE_Responses/README.md)
