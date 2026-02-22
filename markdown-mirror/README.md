# markdown-mirror

This folder contains readability-first markdown mirrors of the archival originals.

## Purpose

- Improve readability and searchability in standard git interfaces.
- Keep all source originals untouched in their native formats.
- Simplify text for machine reading by removing extraction noise.
- Maintain source traceability with path and SHA256 metadata in each copy.

## Normalization Rules

- Hard line wraps are merged into readable paragraphs.
- Repeated separator character blocks are normalized to `---`.
- Excess spacing and blank lines are cleaned.
- Meaning and textual content are preserved; page visual layout is not preserved.

## Scope

The mirror covers all source files in:

- `undo-uus-archive/_IMPERATIVE_Article/*`
- `undo-uus-archive/_IMPERATIVE_Responses/*`

## Regeneration

Run:

```bash
python3 scripts/build_markdown_mirror.py
```

## Folder Index

- [`undo-uus-archive/_IMPERATIVE_Article/README.md`](undo-uus-archive/_IMPERATIVE_Article/README.md)
- [`undo-uus-archive/_IMPERATIVE_Responses/README.md`](undo-uus-archive/_IMPERATIVE_Responses/README.md)
