# Sanskrit Corpus

Local-first tooling for acquiring, normalizing, validating, auditing, and exporting a traceable Sanskrit text corpus.

## Install

The project uses Python 3.11 or newer and [uv](https://docs.astral.sh/uv/):

```sh
uv sync --locked --group dev
```

## Pipeline

Generated data is stored below `data/` and ignored by Git:

1. `pull` downloads raw sources into `data/raw/` and records acquisition manifests.
2. `process` normalizes raw sources into source-specific JSONL files in `data/processed/`.
3. `validate` checks record schemas and cross-record integrity.
4. `audit` resolves effective licensing and reports release eligibility.
5. `export` validates and writes a filtered release plus a checksum and attribution manifest.

Downloads, processed outputs, reports, and releases are written through temporary paths so a failed refresh does not replace the previous artifact.

## Commands

```sh
uv run sanskrit-corpus pull --source all --sample --dry-run
uv run sanskrit-corpus pull --source ud_sanskrit_vedic --sample
uv run sanskrit-corpus pull --source ud_sanskrit_vedic --full --force
uv run sanskrit-corpus pull --source sangraha_verified_sanskrit --sample
uv run sanskrit-corpus pull --source sangraha_unverified_sanskrit --full
uv run sanskrit-corpus pull --source sangraha_synthetic_sanskrit_deva --full

uv run sanskrit-corpus process --source all
uv run sanskrit-corpus process --source sangraha_verified_sanskrit --limit 100
uv run sanskrit-corpus process --source itihasa --limit 100 --force
uv run sanskrit-corpus process --source pe_ocr_sanskrit --force
uv run sanskrit-corpus process --source roundtrip_ocr_sanskrit --force

uv run sanskrit-corpus quality --source all --limit 1000
uv run sanskrit-corpus quality --source all --workers 8 --force
uv run sanskrit-corpus curriculum
uv run sanskrit-corpus grammar

uv run sanskrit-corpus validate --source all
uv run sanskrit-corpus audit
uv run sanskrit-corpus report

uv run sanskrit-corpus export --profile releasable
uv run sanskrit-corpus export --profile clean_releasable --force

uv run sanskrit-corpus ia-pull --max-gb 1.0 --file-kind ocr_text
```

Validation errors block export. Warnings, including missing provenance fields on legacy records, are reported but do not block it. Reports are written to `data/reports/`; exports retain profile-specific validation evidence so manifest checksums remain stable.

## Record Contract

The packaged `record.schema.json` defines the common JSONL envelope. Every record includes a stable ID, source and record type, text and language, source path and URL, normalization history, license label, and release status. Newly processed rows also include `processing_run_id`; older rows remain valid without it.

Processing runs are recorded in `data/manifests/process_runs.jsonl` with input and output checksums. Each release has a neighboring `<profile>.manifest.json` containing its checksum, validation evidence, contributing processing runs, and attribution requirements.

## Licensing

`license_policy.json` contains reviewed source-level policy. SARIT licenses are resolved per TEI document. Audit and export apply effective policy without rewriting legacy processed files.

Release statuses are:

- `releasable`: eligible for standard release exports.
- `benchmark`: evaluation data kept separate from training corpora.
- `synthetic`: generated or translated data kept in a distinct layer.
- `needs_audit`: quarantined until adequate artifact-level evidence exists.
- `restricted`: known terms, such as NonCommercial conditions, exclude the data from releasable profiles.

Unknown or ambiguous terms always remain `needs_audit`. This registry records project policy and evidence; it is not legal advice.

Research-training eligibility is tracked separately from corpus-export eligibility. See
[`deep-research/training-data-decisions.md`](deep-research/training-data-decisions.md) for the measured token census, dataset roles, evaluation
isolation requirements, GRETIL research-use decision, synthetic lineage policy, and future commercialization review triggers.

## Adding a Source

Add its `SourceRecord` and acquisition adapter in `sources.py`, a processor and dispatch entry in `processing.py`, fixture tests, and any reviewed evidence in `license_policy.json`. Use `needs_audit` unless the exact downloaded artifacts have authoritative license evidence.

## Development

```sh
uv run ruff check src tests
uv run mypy src
uv run pytest --cov=sanskrit_corpus --cov-report=term-missing --cov-fail-under=85
uv build
```

The repository source code is licensed under Apache-2.0. Corpus artifacts retain their upstream licenses and attribution requirements.
