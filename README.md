# Sanskrit Corpus

Local-first tools for acquiring and tracking Sanskrit corpus sources.

## Quick start

```sh
uv run sanskrit-corpus pull --source all --sample --dry-run
uv run sanskrit-corpus pull --source ud_sanskrit_vedic --sample
```

Generated downloads and manifests are written under `data/` and ignored by Git.
