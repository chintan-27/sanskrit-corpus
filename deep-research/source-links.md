# Sanskrit Corpus Source Links

This is a working registry of seed datasets and repositories to evaluate for the Sanskrit corpus. Treat entries as candidates until license, provenance, and data quality have been checked from the source.

| Source | Type | Current notes | Release posture |
|---|---|---|---|
| [OliverHellwig/sanskrit](https://github.com/OliverHellwig/sanskrit) | GitHub repository | Sanskrit NLP/corpus tooling associated with Oliver Hellwig and Digital Corpus of Sanskrit workflows. Check repository files directly for download format, citation, and license. | Candidate; requires repo-level audit. |
| [UD_Sanskrit-Vedic](https://github.com/UniversalDependencies/UD_Sanskrit-Vedic) | Treebank | Universal Dependencies Vedic Sanskrit treebank. README reports 4,000 sentences and 27,000 words from Vedic sources, with manually validated lexical and morphosyntactic information. | Open candidate; CC BY-SA 4.0, attribution and share-alike required. |
| [Sanskrit Text Corpus for LLM Pre-Training](https://www.kaggle.com/datasets/preetsojitra/sanskrit-text-corpus) | Kaggle dataset | Candidate monolingual text corpus for pretraining. Kaggle metadata must be checked manually for source composition, license, and redistribution terms. | Quarantine until license and source chain are verified. |
| [rahular/itihasa](https://huggingface.co/datasets/rahular/itihasa) | Parallel corpus | Sanskrit-English translation dataset. Hugging Face lists 93k rows with train, validation, and test splits. | Open candidate; Apache 2.0 per dataset card. |
| [akhil2808/Naamah](https://huggingface.co/datasets/akhil2808/Naamah) | NER dataset | Sanskrit named-entity recognition dataset. Hugging Face lists JSON format, 103k rows, token and `ner_tags` fields, and synthetic tagging. | Open candidate; MIT per dataset card, but label quality should be sampled. |
| [khoomeik/samhitika-0.0.1](https://huggingface.co/datasets/khoomeik/samhitika-0.0.1) | Synthetic corpus | Large synthetic Sanskrit translation corpus from BookCorpus. Dataset card warns that v0.0.1 is low quality, contains incorrect translations and accidental Hindi, and is suitable only after cleaning/filtering. | Synthetic/restricted layer only; MIT per dataset card, but source-chain and quality risks remain. |
| [AIKosh Sanskrit post-OCR correction](https://aikosh.indiaai.gov.in/home/datasets/details/a_benchmark_and_dataset_for_post_ocr_text_correction_in_sanskrit.html) | OCR benchmark | Benchmark and dataset for post-OCR text correction in Sanskrit. Static page access did not expose full metadata during initial review. | Candidate; manually verify metadata, access terms, and license. |
| [Aksharantar](https://aikosh.indiaai.gov.in/home/datasets/details/aksharantar.html) | Transliteration dataset | AI4Bharat transliteration dataset for 20 Indic languages, including Sanskrit. AIKosh lists 26M Indic-English transliteration pairs. | Open candidate; CC BY-SA 4.0, attribution and share-alike required. |

## Audit Checklist

For each source, record:

- exact URL and download method;
- license text and attribution requirements;
- source provenance and whether text is human-authored, OCR-derived, or synthetic;
- language/script coverage;
- size, format, and schema;
- known quality risks;
- target layer: releasable, restricted, synthetic, benchmark, or internal review.
