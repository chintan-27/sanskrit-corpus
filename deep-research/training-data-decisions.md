# Training Data Decisions and Corpus Accounting

Status: active research policy  
Recorded: 2026-08-14  
Scope: corpus composition, model-training eligibility, evaluation isolation, synthetic-data lineage, and future commercialization review

This document records project decisions, not legal advice. It deliberately separates three questions that must not be collapsed into one field:

1. **Training suitability:** Is the material useful and appropriate for the intended experiment?
2. **Research-use posture:** May the project use the lawfully acquired material for its current scholarly, noncommercial research?
3. **Release posture:** May the project redistribute the processed text, publish a checkpoint, or deploy it commercially under the intended terms?

The `release_status` field and `license_policy.json` govern corpus exports. They are conservative release controls; they do not automatically determine whether a source may be used for internal research training.

## Current Project Decision

The immediate objective is a scholarly Sanskrit research model, not a commercial product. The research training mixture may therefore include all lawfully acquired, technically suitable sources whose terms permit the intended scholarly use, including GRETIL. Every run must retain its complete source mixture and processing provenance.

No present decision authorizes commercial deployment. Commercialization, paid access, transfer to a commercial product, or a public release with materially different terms is a review trigger described below.

## Measured Normalized Human Corpus

The following census was computed directly from the `text` field of each normalized JSONL record on 2026-08-14. It excludes `roundtrip_ocr_sanskrit` and `sangraha_synthetic_sanskrit_deva`. Counts are measurements of the current processed artifacts, not estimates based on JSONL file sizes.

| Source | Records | UTF-8 text bytes | Unicode characters | Whitespace units | Devanagari characters |
|---|---:|---:|---:|---:|---:|
| `github_oliverhellwig` | 754,726 | 94,153,312 | 33,704,934 | 4,233,747 | 30,222,050 |
| `gretil_sanskrit` | 802 | 397,295,160 | 150,783,452 | 19,077,823 | 123,153,729 |
| `itihasa` | 93,030 | 25,379,551 | 9,098,356 | 1,046,707 | 8,140,545 |
| `pe_ocr_sanskrit` | 218,637 | 39,490,538 | 14,143,286 | 1,517,079 | 12,649,845 |
| `sangraha_unverified_sanskrit` sample | 100 | 3,517,873 | 1,294,768 | 140,900 | 1,110,897 |
| `sangraha_verified_sanskrit` sample | 100 | 1,312,419 | 480,983 | 57,833 | 415,681 |
| `sanskrit_wikipedia` | 13,419 | 80,023,290 | 30,222,559 | 3,518,125 | 24,822,451 |
| `sanskrit_wikisource` | 30,666 | 1,005,662,314 | 386,243,045 | 45,391,385 | 307,920,087 |
| `sarit_corpus` | 83 | 146,558,960 | 53,494,519 | 6,054,765 | 46,457,568 |
| `ud_sanskrit_vedic` | 27,182 | 3,419,174 | 1,261,798 | 206,440 | 1,078,407 |
| **Total** | **1,138,745** | **1,796,812,591** | **680,727,700** | **81,244,804** | **555,971,260** |

UTF-8 bytes are the content-token count for a ByT5-style byte tokenizer before special tokens and packing overhead. They are not a substitute for the token count of a SentencePiece/BPE tokenizer. Before choosing model size or a final training budget, rerun the census with the exact production tokenizer and report tokens after filtering and deduplication.

JSONL size must never be used as a token proxy. For example, the DCS JSONL is approximately 2.9 GB because it contains extensive morphological metadata, but its `text` fields contain only 94,153,312 UTF-8 bytes.

## Dataset Roles

### Human language-model material

GRETIL, Wikisource, SARIT, Wikipedia, Itihasa, PE OCR after quality filtering, and non-held-out portions of scholarly corpora are candidate human training material. Inclusion still depends on language identification, OCR quality, deduplication, provenance, and the terms applicable to the intended research use.

### Evaluation and annotated supervision

DCS/Hellwig and UD are unusually valuable gold morphological and dependency resources. They must not be treated as ordinary undifferentiated pretraining text.

Before the next model-training run:

- create immutable train/development/test assignments at stable record-ID level;
- lock evaluation IDs and checksums in a manifest;
- remove held-out texts and near duplicates from every pretraining, curriculum, synthetic-generation, and retrieval input;
- audit the existing grammar and curriculum artifacts for DCS/UD leakage;
- split by work or document where sentence-level splitting would leak the same edition or passage.

The existing grammar artifact is built from DCS and UD. Its current split does not by itself prove isolation from other corpus artifacts.

### OCR-correction tooling

`roundtrip_ocr_sanskrit` contains synthetic corrupted/re-recognized versions of text already present elsewhere. Its 4,086,287 records add no new linguistic content. It is excluded from language-model corpus totals and general pretraining. It may be used for OCR-error modeling, correction, augmentation experiments, or paired supervision.

Real OCR-derived sources, including PE OCR and Internet Archive OCR, may contribute new text only after quality, language, edition, and duplicate filtering.

### Machine-translated and generated text

`sangraha_synthetic_sanskrit_deva` is a separate synthetic translation layer. Its 18 GB raw download and approximately 5.79 million quality-profiled records must not be counted as human Sanskrit.

Do not normalize or admit the full source to the main training mixture until the planned A4 evaluation has compared at least 200 stratified samples using Sanskritist judgments, grammatical parseability, contamination, semantic fidelity, and repetition. Any admitted synthetic share must be explicitly capped and reported.

## GRETIL Decision

GRETIL is important research material and contributes 397,295,160 byte tokens, 150,783,452 Unicode characters, and 19,077,823 whitespace units to the current normalized corpus.

The project will include GRETIL in scholarly, noncommercial research training. GRETIL's official site states that its files are for scholarly reference, explicitly excludes commercial use, and leaves copyright with the original copyright holders. Individual files and contributors may have additional or differing notices. Preserve file-level provenance wherever available.

References:

- GRETIL current register: <https://gretil.sub.uni-goettingen.de/>
- GRETIL scholarly-use and commercial-use notice: <https://gretil.sub.uni-goettingen.de/gret_utfbk.htm>
- Creative Commons guidance on AI training: <https://creativecommons.org/using-cc-licensed-works-for-ai-training-2/>

This research-use decision does not assert that model weights are an adaptation of GRETIL, nor that training necessarily requires copyright permission. Those questions are jurisdiction- and use-specific. It also does not promise that a GRETIL-trained checkpoint can later be commercialized without further review.

Every GRETIL-containing run must be marked in its manifest. If future commercial flexibility becomes important, maintain a separately trained lineage that excludes GRETIL and any other source whose terms do not clearly support that use. Fine-tuning a GRETIL-trained checkpoint later is not assumed to remove its provenance.

## Synthetic Generation and Model Lineage

A research model trained on broad data may generate candidate Sanskrit for research. Generated output is not automatically free of its training provenance. A chain such as `GRETIL -> teacher model -> generated text -> student model` must remain documented; distillation is not treated as a licensing reset.

For every generated dataset, record:

- teacher checkpoint and complete source-mixture manifest;
- prompt/template or grammar-engine version;
- sampling parameters and generation date;
- exact and near-duplicate checks against human and restricted sources;
- memorization and long-span reproduction tests;
- automatic quality scores and Sanskritist review results;
- acceptance/rejection rules and downstream student checkpoints.

Generated records must remain labeled `synthetic` even when they pass grammatical or semantic validation.

## Internet Archive Decision Gate

The current Internet Archive quality estimate is based on only 100 files and 60,923 passages. It found 8,148 clean-Sanskrit candidates (13.4%), but that sample is insufficient to extrapolate across publishers, decades, scripts, and scan regimes.

Before committing to full IA OCR processing, profile at least 2,000 files stratified by decade, publisher/provider, format, script, and OCR availability. Report passage yield, clean Sanskrit rate, Hindi/other-language rate, boilerplate, severe OCR failure, duplication, and usable tokens per downloaded gigabyte for every stratum.

The IA decision must be made from expected accepted tokens and diversity, not item count or storage volume.

## Future Commercialization Review Trigger

Stop and conduct a new source-by-source policy and legal review before any of the following:

- selling access to a checkpoint or service;
- integrating a checkpoint into a revenue-generating product;
- licensing or transferring weights to a commercial party;
- releasing weights under terms incompatible with an included source;
- generating a commercial training set directly from a broadly trained research checkpoint.

At that point, decide whether to obtain permissions, rely on a reviewed legal exception, exclude particular sources, or train a separate clean-lineage checkpoint. The review must consider the intended jurisdiction, model behavior, memorization tests, access method, source-specific terms, and planned distribution—not merely the labels in `license_policy.json`.

## Immediate Measurement Priorities

1. Lock DCS and UD held-out sets and audit leakage.
2. Add a reproducible token-census command using the selected tokenizer.
3. Profile 2,000 stratified IA files.
4. Run the 200-sample Sangraha synthetic A4 evaluation.
5. Reclassify round-trip OCR in all reporting as OCR tooling rather than corpus text.
6. Preserve source-mixture and lineage manifests for every model and generated dataset.

These measurements precede model-size selection. The present normalized human pool is approximately 1.80 billion ByT5 content bytes before quality filtering, deduplication, and evaluation holdouts; it must not be described as 1.80 billion tokens for an unspecified tokenizer.
