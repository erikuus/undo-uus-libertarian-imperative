# The Libertarian Imperative Archive

This repository preserves the archival record of Undo Uus's philosophical project **The Libertarian Imperative** and publishes a reader-facing site built from that archive.

The repo has a clear split:

- the **archive itself**: original article files, publication variants, correspondence, and related material
- the **public presentation layer**: the Astro site in `site/` and the mirrored narrative text in [`docs/argument-map.md`](docs/argument-map.md)

## Start Here

- Public site: [https://libertarianimperative.org/](https://libertarianimperative.org/)
- Site-text mirror / argument map: [`docs/argument-map.md`](docs/argument-map.md)
- Documentation index: [`docs/README.md`](docs/README.md)
- Development timeline: [`docs/timeline.md`](docs/timeline.md)
- Process map: [`docs/process-map.md`](docs/process-map.md)
- File catalog: [`docs/file-catalog.md`](docs/file-catalog.md)

## Repository Structure

- [`undo-uus-archive/`](undo-uus-archive/README.md): canonical archival wrapper for original materials
- [`markdown-mirror/`](markdown-mirror/README.md): script-generated markdown mirrors of core texts
- [`markdown-reader/`](markdown-reader/README.md): hand-edited reader copies for more difficult source material
- [`site/`](site/README.md): Astro site source for the public presentation
- [`docs/`](docs/README.md): interpretive and navigational documentation

## Main Archive Entry Points

- Original article corpus: [`undo-uus-archive/_IMPERATIVE_Article/README.md`](undo-uus-archive/_IMPERATIVE_Article/README.md)
- Publishing workflow records: [`undo-uus-archive/_IMPERATIVE_Article/PublishingProcess/README.md`](undo-uus-archive/_IMPERATIVE_Article/PublishingProcess/README.md)
- Responses dossier: [`undo-uus-archive/_IMPERATIVE_Responses/README.md`](undo-uus-archive/_IMPERATIVE_Responses/README.md)
- Estonian publication materials: [`undo-uus-archive/1997_Libertaarimperatiiv/README.md`](undo-uus-archive/1997_Libertaarimperatiiv/README.md)

## Website

- App source: [`site/README.md`](site/README.md)
- Local run: `cd site && npm install && npm run dev`
- Deployment workflow: [`.github/workflows/deploy-pages.yml`](.github/workflows/deploy-pages.yml)

## Preservation Principles

- Originals are preserved as-is in `undo-uus-archive/`.
- Markdown mirrors prioritize readability while preserving traceability.
- Fixity manifests record checksums for both canonical and mirrored files.
- Mirror generation is reproducible via [`scripts/build_markdown_mirror.py`](scripts/build_markdown_mirror.py).

## Rights and Citation

- Rights statement: [`RIGHTS.md`](RIGHTS.md)
- Citation guidance: [`CITE.md`](CITE.md)
- Machine-readable citation metadata: [`CITATION.cff`](CITATION.cff)
- Curator intervention log: [`CURATOR_LOG.md`](CURATOR_LOG.md)

## Integrity Checks

- Canonical source fixity: `undo-uus-archive/manifest-sha256.txt`
- Mirror fixity: `markdown-mirror/manifest-sha256.txt`
- Validation command: `python3 scripts/build_markdown_mirror.py --check`
