# Curator Change Log

This log records non-original, curator-layer interventions.

## Policy

- `undo-uus-archive/_IMPERATIVE_Article/*` and `undo-uus-archive/_IMPERATIVE_Responses/*` are canonical source artifacts and should remain immutable in content.
- Curator corrections, metadata additions, and representation changes must occur in docs/scripts/mirror layers.

## Entries

- 2026-02-22: Initialized archive repository structure and first documentation/index layers.
- 2026-02-22: Reorganized canonical sources under `undo-uus-archive/` wrapper with explicit provenance README.
- 2026-02-22: Renamed wrapper from `undo_uus_archive` to `undo-uus-archive` and updated all links.
- 2026-02-22: Converted `markdown-mirror` to readability-first normalization policy.
- 2026-02-22: Moved ingest context model to `undo-uus-archive/METADATA.md` with curator-authored disclaimer.
- 2026-02-22: Added rights statement, citation layer, argument map, fixity manifests, OCR fallback for image-only pages, and forensics-friendly `build_markdown_mirror.py` modes (`--check`, `--deterministic`).
- 2026-02-22: Completed article citation record with explicit absence/provenance notes for page range/DOI/ISSN and updated mirror validation behavior so `--check` is portable by default; added optional strict OCR matching (`--strict-ocr-check`).
