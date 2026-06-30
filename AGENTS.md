# Repository Guidelines

## Project Structure & Module Organization

This repository currently stores planning and research material for a Sanskrit corpus effort. Use `deep-research/` for source evaluations, architecture notes, corpus acquisition plans, OCR strategy, and related long-form research. Existing examples are `deep-research/chatgpt.md` and `deep-research/gemini.txt`.

When adding implementation code later, keep it separate from research notes. Suggested future layout:

- `src/` for ingestion, normalization, scoring, and export code.
- `tests/` for automated tests matching the source package layout.
- `data/` for small fixtures only; do not commit large corpora, scans, or generated datasets.
- `docs/` for design notes that are not raw research captures.

## Build, Test, and Development Commands

No build system or test runner is currently defined. Before adding commands, document them in a `README.md` or project-specific task file.

Useful current commands:

- `find . -maxdepth 3 -type f | sort` lists tracked-style project files.
- `wc -l deep-research/*` gives a quick size check for research notes.
- `rg "license|provenance|OCR" deep-research/` searches the existing corpus-planning notes.

## Coding Style & Naming Conventions

For Markdown, use sentence-case headings, short sections, and fenced code blocks for commands or schemas. Keep Sanskrit technical terms consistent within a document, and prefer UTF-8 text. Name research files with lowercase, hyphenated slugs such as `source-registry.md` or `ocr-pipeline.md`.

For future code, follow the formatter and linter native to the chosen language. Keep pipeline names explicit, for example `source_registry`, `license_audit`, `ocr_confidence`, and `dedup_lineage`.

## Testing Guidelines

There are no automated tests yet. When code is introduced, add tests with small, license-clean fixtures that cover script normalization, provenance metadata, deduplication, and OCR confidence logic. Avoid tests that require downloading external corpora. Document the exact test command beside the implementation.

## Commit & Pull Request Guidelines

This checkout does not include local Git history, so no project-specific convention can be inferred. Use concise, imperative commit subjects such as `Add OCR source inventory`.

Pull requests should include a short purpose statement, changed files, commands run, and licensing or provenance implications. For corpus changes, identify source URLs, license posture, and whether content is releasable, restricted, synthetic, or internal review only.

## Data, Licensing & Provenance

Treat provenance as required metadata. Do not add large raw datasets or redistributed copyrighted text without a documented license decision. For every new source note, capture the source name, URL, access method, license terms, release status, and any audit gaps.
