# Sanskrit Corpus Source Inventory

This is the acquisition backlog for human-authored Sanskrit, aligned translations, grammatical annotations, and OCR inputs. It is comprehensive by source class, not a claim that every catalog item is Sanskrit or legally reusable. Treat collection-level licenses as metadata only: verify the underlying work, edition, scan, transcription, and website terms before training or redistribution.

## Priority and Status

- **P0**: large or linguistically important; implement and audit first.
- **P1**: valuable second-wave source or substantial OCR opportunity.
- **P2**: specialist, small, duplicated, difficult to access, or unclear terms.
- **Open** means an explicit permissive or Creative Commons route appears available; preserve attribution and ShareAlike boundaries.
- **Restricted** means NonCommercial, NoDerivatives, research-only, or access-controlled.
- **Audit** means no reliable reuse conclusion has yet been recorded.

## Large Pretraining and Web Corpora

| Priority | Source | Material and scale | Access / posture |
|---|---|---|---|
| P0 | [AI4Bharat Sangraha](https://huggingface.co/datasets/ai4bharat/sangraha) | `verified/san` reports 1.329B human-source tokens; synthetic Sanskrit is 13.55B and must remain separate. | HF Parquet; dataset CC BY 4.0, underlying-source audit required. |
| P0 | [CulturaX](https://huggingface.co/datasets/uonlp/CulturaX) | Cleaned, fuzzy-deduplicated mC4 + OSCAR; 13.56M Sanskrit tokens. | Gated HF access; upstream terms apply. |
| P0 | [FineWeb 2](https://huggingface.co/datasets/HuggingFaceFW/fineweb-2) | Multilingual Common Crawl with language-specific cleaning; inspect Sanskrit partition and measured words. | Open dataset access; URL-level rights remain mixed. |
| P1 | [OSCAR](https://oscar-project.org/) | Multiple Common Crawl releases; older deduplicated Sanskrit release reported about 1.7M words. | Dataset terms plus source-site rights; heavy overlap with CulturaX. |
| P1 | [mC4](https://huggingface.co/datasets/allenai/c4) | Sanskrit web text used within CulturaX and other mixtures. | ODC-BY dataset; audit URLs and deduplicate. |
| P1 | [MADLAD-400](https://huggingface.co/datasets/allenai/MADLAD-400) | Broad multilingual web corpus with Sanskrit coverage. | ODC-BY; audit source provenance and overlap. |
| P1 | [CC-100](https://data.statmt.org/cc-100/) | Common Crawl monolingual extraction with Sanskrit (`sa`). | Research corpus; verify terms and quality. |
| P1 | [IndicCorp v2 / IndicBERT corpus](https://github.com/AI4Bharat/IndicBERT) | Indic monolingual corpus covering 24 languages, including Sanskrit. | CC BY-NC 4.0; restricted layer. |
| P2 | [Sanskrit Text Corpus for LLM Pre-Training](https://www.kaggle.com/datasets/preetsojitra/sanskrit-text-corpus) | Aggregated monolingual candidate of unclear composition. | Audit Kaggle metadata and source chain before download. |
| P2 | [Anamavajra Sanskrit corpus](https://huggingface.co/datasets/Anamavajra-Labs/sanskrit-corpus) | Convenient aggregate: texts, 2M parallel pairs, dictionaries, and 6.4M morphological rows from 17 sources. | Mixed per-source licenses; use as an index, not a single-license corpus. |

## Scholarly E-texts and Canonical Literature

| Priority | Source | Material | Access / posture |
|---|---|---|---|
| P0 | [Digital Corpus of Sanskrit (DCS)](https://github.com/OliverHellwig/sanskrit) | Roughly 250 works, 650k lines/sentences and 4.5M morphologically analyzed word references. | CoNLL-U/GitHub, CC BY 4.0; overlaps GRETIL. |
| P0 | [GRETIL](https://gretil.sub.uni-goettingen.de/gretil.html) | Largest general repository of machine-readable Indological and Sanskrit texts. | Cumulative TEI download is CC BY-NC-SA 4.0; restricted. |
| P0 | [SARIT](https://github.com/sarit/SARIT-corpus) | Approximately 80–90 scholarly TEI texts with rich structure and edition metadata. | Audit TEI headers per file; commonly ShareAlike. |
| P0 | [Sanskrit Documents](https://sanskritdocuments.org/) | Large community collection of Devanagari and transliterated e-texts plus scan indexes. | Mixed provenance and permissions; audit per item. |
| P0 | [VedaWeb](https://vedaweb.uni-koeln.de/rigveda/) | Curated, accented and annotated Ṛgveda, Brāhmaṇas, and Atharvaveda resources. | Open-access interface; obtain data license/API permission before bulk use. |
| P0 | [Muktabodha Digital Library](https://muktabodha.org/digital-library/) | 3,000+ preserved texts, 570+ searchable e-texts, Śaiva/Tantric and Vedic holdings. | Mixed/custom terms; source- and edition-level audit. |
| P1 | [The Sanskrit Library](https://www.sanskritlibrary.org/) | Digitized primary texts, reference works, corpora, and analysis tools. | Access varies by collection; negotiate bulk data use. |
| P1 | [Sanskrit Heritage](https://sanskrit.uohyd.ac.in/SKT/) | Curated corpus, lexicon, segmentation and morphological analysis resources. | Public tools; data license requires confirmation. |
| P1 | [Digital Sanskrit Buddhist Canon](https://dsbcproject.org/) | Buddhist Sanskrit texts in Devanagari and Romanization. | Compilation/transliteration rights reserved; audit each cited source. |
| P1 | [DharmaNexus](https://dharmanexus.net/) | Buddhist textual corpora and cross-lingual scholarly resources. | Terms vary; audit datasets individually. |
| P1 | [SuttaCentral](https://github.com/suttacentral) | Canonical and parallel Buddhist texts, including Sanskrit fragments/texts. | Many text assets CC0; verify repository-level metadata. |
| P1 | [TITUS](https://titus.uni-frankfurt.de/) | Indo-European text collections including Vedic and Classical Sanskrit. | Scholarly access; bulk reuse terms require permission. |
| P1 | [Gītā Supersite, IIT Kanpur](https://www.gitasupersite.iitk.ac.in/) | Bhagavadgītā text and multiple Sanskrit commentaries/translations. | Public interface; audit individual editions and scraping permission. |
| P1 | [Valmiki Ramayan, IIT Kanpur](https://www.valmiki.iitk.ac.in/) | Structured Rāmāyaṇa text with translations/commentary. | Public interface; terms and edition rights need audit. |
| P2 | [Polyglotta](https://www2.hf.uio.no/polyglotta/) | Multilingual aligned ancient texts with Sanskrit in selected corpora. | Open-access interface; verify each corpus. |
| P2 | [Ambuda](https://ambuda.org/) | Structured reading library aggregating Sanskrit works and annotations. | Audit source provenance, API/export options, and per-work rights. |
| P2 | [Sangrah / Sandarbha](https://www.sangrah.org/) | Searchable Sanskrit corpus and partner manuscript collections. | Partner/access terms require discussion. |
| P2 | [Wisdom Library Sanskrit](https://www.wisdomlib.org/) | Large web presentation of texts, dictionaries and secondary material. | Website and edition terms unclear; do not crawl before permission. |

## Parallel, Translation, and Alignment Data

| Priority | Source | Material | Access / posture |
|---|---|---|---|
| P0 | [Itihāsa](https://huggingface.co/datasets/rahular/itihasa) | About 93k Sanskrit–English epic verse pairs. | Apache-2.0 dataset card; preserve attribution and source identity. |
| P0 | [Sāmayik](https://github.com/ayushbits/saamayik) | About 53k contemporary English–Sanskrit prose pairs. | Research-use/unclear repository terms; restricted pending audit. |
| P0 | [MITRA](https://github.com/ryderwishart/mitra) | Large Sanskrit/Pāli/Tibetan/Chinese parallel corpus and retrieval data. | Reported CC BY-SA 4.0; verify released subsets and provenance. |
| P0 | [BPCC / IndicTrans2](https://github.com/AI4Bharat/IndicTrans2) | English–Indic and Indic–Indic bitext, including Sanskrit. | Mixed CC0/CC BY 4.0 components; audit row provenance. |
| P1 | [FLORES-200](https://huggingface.co/datasets/facebook/flores) | Small professionally translated Sanskrit benchmark. | CC BY-SA 4.0; reserve primarily for evaluation. |
| P1 | [Samasāmayik](https://arxiv.org/abs/2603.24307) | Contemporary Hindi–Sanskrit parallel dataset. | Confirm artifact URL and license before ingestion. |
| P1 | [Santham](https://aclanthology.org/2026.iscls-1.5/) | Sanskrit–Tamil data with anvaya and large monolingual component. | Verify released artifacts, synthetic split, and license. |
| P1 | [Dharmamitra](https://dharmamitra.org/) | Sanskrit–English Buddhist and Śaiva translation/alignment resources. | Some derivatives CC BY-NC 4.0; restricted unless subset says otherwise. |
| P2 | [Samhitika 0.0.1](https://huggingface.co/datasets/khoomeik/samhitika-0.0.1) | Large BookCorpus-derived synthetic English→Sanskrit translations; known errors and Hindi contamination. | Synthetic quarantine only; source-chain risk despite MIT label. |
| P2 | [Bible/OPUS collections](https://opus.nlpl.eu/) | Sanskrit parallel religious text may appear in multilingual corpora. | Audit translation edition and OPUS subcorpus license. |

## Grammar, Morphology, Tokenization, and Evaluation

| Priority | Source | Material | Access / posture |
|---|---|---|---|
| P0 | [UD Sanskrit Vedic](https://github.com/UniversalDependencies/UD_Sanskrit-Vedic) | Manually validated Vedic dependency treebank, about 27k words. | CC BY-SA 4.0. |
| P0 | [UD Sanskrit UFAL](https://github.com/UniversalDependencies/UD_Sanskrit-UFAL) | Classical Sanskrit dependency data. | Check repository license and source texts. |
| P0 | [DCS morphology](https://github.com/OliverHellwig/sanskrit/tree/master/dcs) | Lemmas, segmentation and morphological features at multi-million-token scale. | CC BY 4.0. |
| P0 | [Sanskrit Heritage Engine](https://sanskrit.inria.fr/) | Segmentation, morphology generation, lexicon and curated analyses. | Tool/code/data terms differ; confirm before redistribution. |
| P1 | [Sanskrit Word Segmentation datasets](https://github.com/OliverHellwig/sanskrit) | DCS-derived segmentation and analysis material used by Sanskrit NLP research. | Preserve upstream DCS provenance. |
| P1 | [AIKosh post-OCR benchmark](https://aikosh.indiaai.gov.in/home/datasets/details/a_benchmark_and_dataset_for_post_ocr_text_correction_in_sanskrit.html) | Corrected Sanskrit OCR pairs and benchmark material. | Registration/access and license need manual verification. |
| P1 | [Aksharantar](https://github.com/AI4Bharat/Aksharantar) | Large transliteration dataset covering Sanskrit and other Indic languages. | CC BY-SA 4.0; isolate human and generated components if present. |
| P1 | [Naamah](https://huggingface.co/datasets/akhil2808/Naamah) | 103k-row Sanskrit NER benchmark with synthetic/silver labels. | MIT label; benchmark/silver layer, sample quality. |
| P1 | [Sanskrit OCR Typed Dataset](https://huggingface.co/datasets/Process-Venue/Sanskrit-OCR-Typed-Dataset) | Page/image-to-transcription examples. | Verify image provenance and dataset license. |
| P1 | [RSL-SHRUTI Sangraha](https://huggingface.co/datasets/RSL-INTRINSICLab-IIT/RSL-SHRUTI-Sangraha) | Sanskrit speech/text resource at million-record scale. | Verify human/synthetic composition, consent, and license. |
| P2 | [Pramāṇa-NLP](https://github.com/Pramana-Initiative) | Specialist Sanskrit NLP datasets and tools. | Research-use restrictions reported for some text subsets. |

## Dictionaries and Knowledge Structures

| Priority | Source | Material | Access / posture |
|---|---|---|---|
| P0 | [Cologne Digital Sanskrit Dictionaries](https://www.sanskrit-lexicon.uni-koeln.de/) | 40+ downloadable XML dictionaries, including Monier-Williams, Apte and Böhtlingk/Roth. | Digitization commonly CC BY-NC-SA 3.0; verify each package. |
| P0 | [Sanskrit Heritage dictionary](https://sanskrit.uohyd.ac.in/SKT/) | Morphology-aware Sanskrit–French lexicon plus adapted MW data. | Confirm data license separately from public access. |
| P1 | [Sanskrit WordNet](https://www.cfilt.iitb.ac.in/wordnet/webswn/) | Sanskrit synsets and lexical relations. | Obtain license/permission for bulk training use. |
| P1 | [Digital Corpus of Sanskrit lexicon](https://github.com/OliverHellwig/sanskrit) | Attested lemmas, forms and historical occurrence metadata. | CC BY 4.0 for released data. |
| P1 | [Amarakośa resources](https://sanskrit.uohyd.ac.in/scl/) | Traditional thesaurus and computational lexical tools. | Confirm individual resource licenses. |

## OCR and Document-Understanding Datasets

Keep **image→transcription ground truth**, **raw OCR→corrected text pairs**, and **synthetically corrupted text** as separate dataset classes. The last class is useful for augmentation but cannot measure real historical OCR performance.

| Priority | Source | Supervision and scale | Access / posture |
|---|---|---|---|
| P0 | [PE-OCR Sanskrit](https://github.com/ayushbits/pe-ocr-sanskrit) | Real post-OCR correction pairs: about 218k sentences and 1.5M words from 30 books across astronomy, medicine, mathematics and other domains. | Public code/data; MIT is reported by the HF mirror, but audit the 30 book editions. |
| P0 | [PE-OCR Hugging Face mirror](https://huggingface.co/datasets/acomquest/sanskrit-ocr-post-correction) | Packaged train/validation/test and out-of-domain splits for the same benchmark. | MIT dataset label; preserve original split and book provenance. |
| P0 | [RoundTripOCR Sanskrit](https://huggingface.co/datasets/cfilt/RoundTripOCR-sanskrit) | About 4.09M `(ocr, correct, font)` rows produced by rendering and OCR round trips across 49 fonts. | Apache-2.0; synthetic OCR-error layer, not a real-scan benchmark. |
| P0 | [Printed Devanagari Ground Truth](https://htr-united.github.io/catalog.html) | Approximately 220 pages/27k words with JPG + ALTO XML from Naval Kishore Press books in Sanskrit, Hindi, Braj and Awadhi. | HTR-United catalog; verify record license and separate languages at line level. |
| P0 | [IHDIA Sanskrit OCR / Indiscapes](https://ihdia.iiit.ac.in/) | Printed Sanskrit OCR resources plus layout annotations for historical Indic/palm-leaf documents. | Locate code/data release and license; do not assume all Indiscapes pages are Sanskrit. |
| P1 | [Process Venue Sanskrit OCR Typed Dataset](https://huggingface.co/datasets/Process-Venue/Sanskrit-OCR-Typed-Dataset) | Small image/transcription OCR dataset. | Audit image origins, transcription method, scripts and license. |
| P1 | [Pracalit Sanskrit/Newar manuscript GT](https://zenodo.org/records/6967421) | Ground truth and OCR model for 16th–19th-century Pracalit-script Sanskrit and Newar manuscripts. | Zenodo artifact; verify declared license and language labels. |
| P1 | [Grantha Palm Leaf Dataset](https://data.mendeley.com/datasets/zjtd63zhz6) | Character crops from Grantha palm leaves, a major South Indian script for Sanskrit. | Verify license/version; character recognition only, not full-page transcription. |
| P1 | [LeafOCR-Line](https://www.nature.com/articles/s41597-026-06718-1) | 1,710 palm-leaf images with text-line masks and deterioration labels. | Open research dataset; layout supervision, with language/script composition to audit. |
| P1 | [AIKosh Sanskrit post-OCR dataset](https://aikosh.indiaai.gov.in/home/datasets/details/a_benchmark_and_dataset_for_post_ocr_text_correction_in_sanskrit.html) | Government catalog entry for the PE-OCR-style Sanskrit correction benchmark. | Registration and artifact terms require manual verification; avoid duplicate ingestion. |
| P1 | [Can OCR-VLMs Read Devanagari?](https://arxiv.org/abs/2606.29213) | 2026 stress-test and post-correction benchmark spanning conjuncts, mātrās, numerals and layout failures. | Find released benchmark artifact/license; reserve a clean split for evaluation. |
| P1 | [Vedic accent OCR resources](https://sanskrit.uohyd.ac.in/19WSC/papers/WSC2025_Tsukagoshi.pdf) | Accent-aware Vedic OCR research and potential evaluation material. | Paper/reference lead; locate released images, transcriptions and terms. |
| P2 | [Upcycle Your OCR](https://arxiv.org/abs/1809.02147) | Romanized Sanskrit post-OCR correction methodology and derived noisy/clean sequences. | Locate accompanying dataset and source editions; audit before use. |
| P2 | [Sanskrit word-level OCR benchmark](https://www.sciencedirect.com/science/article/pii/S1877050926017023) | 2026 Sanskrit word-image dataset described with CRNN/quantum-enhanced baselines. | Confirm whether data is publicly released and under what license. |

### OCR Pairs We Can Derive Lawfully

These are not ready-made datasets, but can become much larger aligned OCR corpora after edition matching and rights review:

- **Internet Archive:** page images, PDFs, DjVu XML/HOCR and `_djvu.txt` provide image/layout/raw-OCR tuples. Proofread transcriptions must come from the same edition.
- **DLI mirrors:** scans and existing OCR can be paired when stable page identifiers survive; many items duplicate Internet Archive.
- **Muktabodha/IFP:** searchable e-texts and manuscript/printed-page images may yield scholarly pairs, but only with institutional permission and reliable page alignment.
- **GRETIL, SARIT, DCS and VedaWeb:** clean scholarly text can supervise OCR only after matching the exact printed edition; a shared work title is insufficient.
- **Wikisource:** Page namespace images plus proofread transcriptions are especially valuable because alignment and review status are explicit; retain contributor attribution and underlying-scan rights.

### OCR Evaluation Splits

Maintain non-overlapping gold sets by document regime: modern clean Devanagari, degraded letterpress Devanagari, Vedic accents, Romanized/IAST, Grantha, Pracalit/Newari, Śāradā, Bengali, Telugu/Kannada scripts, and palm-leaf layout. Split by **book or manuscript**, never randomly by line, to prevent typeface and page leakage.

## Scanned Books, Libraries, and OCR Targets

| Priority | Source | Holdings / opportunity | Access / posture |
|---|---|---|---|
| P0 | [Internet Archive](https://archive.org/advancedsearch.php?q=sanskrit+AND+mediatype%3Atexts) | Large public-domain and contributed Sanskrit book collection with OCR derivatives. | Item-level metadata and rights; deduplicate mirrors/editions. |
| P0 | [Digital Library of India catalog](https://sanskritdocuments.org/scannedbooks/DLI_Catalog/) | Major Indian-language scan collection, much mirrored at Internet Archive. | Public-domain likelihood varies; edition/item audit required. |
| P0 | [National Digital Library of India](https://ndl.iitkgp.ac.in/) | Aggregated books, theses and institutional holdings. | Often discovery/access only; negotiate bulk acquisition. |
| P0 | [Sanskrit Documents scanned books](https://sanskritdocuments.org/scannedbooks/) | Indexes thousands of scans and OCR search resources across repositories. | Use as catalog; follow item-level source and rights. |
| P1 | [Central Sanskrit University Digital Books](https://sanskrit.nic.in/DigitalBook/index.htm) | Alphabetical catalog of Sanskrit books and institutional publications. | Audit publication dates, download terms and edition copyrights. |
| P1 | [National Mission for Manuscripts](https://www.namami.gov.in/) | National catalog with metadata for about four million manuscripts. | Primarily discovery; library partnerships and permissions required. |
| P1 | [IGNCA digital collections](https://ignca.gov.in/divisionss/kalakosa/) | Manuscripts, rare books and Indological collections. | Collection-specific access and reuse terms. |
| P1 | [French Institute of Pondicherry / Muktabodha](https://muktabodha.org/digital-library/) | 2,000+ mostly Śaiva Siddhānta paper transcripts and 1,100+ PDFs. | Restricted/mixed; seek institutional agreement. |
| P1 | [Bhandarkar Oriental Research Institute](https://bori.ac.in/) | Major manuscript and critical-edition holdings, including Mahābhārata scholarship. | Catalog/partnership target; no assumed bulk license. |
| P1 | [Sarasvati Mahal Library](https://tmssmlibrary.com/) | Large palm-leaf manuscript and printed-book collection. | Partnership/OCR target; rights and access negotiated per collection. |
| P1 | [Government Oriental Manuscripts Library](https://www.tnarch.gov.in/government-oriental-manuscripts-library) | Extensive South Indian Sanskrit manuscripts and catalogs. | Institutional partnership required. |
| P1 | [Oriental Research Institute Mysore](https://uni-mysore.ac.in/english-version/oriental-research-institute) | Manuscripts and rare Sanskrit editions. | Institutional partnership required. |
| P1 | [Asiatic Society Kolkata](https://asiaticsocietykolkata.org/) | Sanskrit manuscripts, Bibliotheca Indica editions and catalogs. | Some digital access; audit each edition and collection. |
| P1 | [Shodhganga](https://shodhganga.inflibnet.ac.in/) | Indian theses, including Sanskrit scholarship and edited texts. | Thesis copyright persists; extract only with appropriate permission. |
| P2 | [HathiTrust](https://www.hathitrust.org/) | Public-domain and restricted historical Sanskrit books from research libraries. | Use bibliographic API/public-domain downloads; access restrictions apply. |
| P2 | [Google Books](https://books.google.com/) | Broad historical scan discovery and some public-domain downloads. | Automated bulk extraction restricted; use for discovery/edition matching. |
| P2 | [Gallica](https://gallica.bnf.fr/) | European Indological editions, dictionaries and manuscripts. | Item-level public-domain/reuse terms; OCR quality varies. |
| P2 | [Bodleian Digital Library](https://digital.bodleian.ox.ac.uk/) | Sanskrit manuscript images and catalogs. | Image licenses vary; mostly specialist manuscript OCR. |
| P2 | [Cambridge Digital Library](https://cudl.lib.cam.ac.uk/) | South Asian manuscripts and rare printed works. | Item-level image/reuse terms. |
| P2 | [British Library Asian and African collections](https://www.bl.uk/collection-guides/sanskrit) | Major Sanskrit manuscript and printed holdings. | Catalog and selective images; partnership/permission required. |
| P2 | [Buddhist Digital Resource Center](https://library.bdrc.io/) | Buddhist manuscript and text images across Sanskrit, Tibetan and related languages. | API metadata is open; work/image access and licenses vary. |

## Contemporary Sanskrit and Audio/Video Discovery

| Priority | Source | Material | Access / posture |
|---|---|---|---|
| P1 | [Sanskrit Wikipedia](https://dumps.wikimedia.org/sawiki/latest/) | Contemporary encyclopedic Sanskrit XML dumps. | CC BY-SA 4.0; preserve revision/attribution data. |
| P1 | [Sanskrit Wikisource](https://dumps.wikimedia.org/sawikisource/latest/) | Proofread primary texts and scans. | Wikimedia license plus underlying edition audit. |
| P1 | [Sanskrit Wiktionary](https://dumps.wikimedia.org/sawiktionary/latest/) | Lexical entries and examples. | CC BY-SA 4.0; structured extraction. |
| P1 | [Spoken Tutorial Sanskrit material](https://spoken-tutorial.org/) | Contemporary instructional prose used in Sāmayik. | Verify transcript and translation licensing. |
| P1 | [All India Radio Sanskrit news](https://newsonair.gov.in/) | Contemporary broadcast Sanskrit and possible transcripts/audio. | Broadcast copyright; seek licensing agreement. |
| P1 | [DD News / Sanskrit programming](https://prasarbharati.gov.in/) | News, educational and cultural Sanskrit audio/video. | Copyrighted; partnership and transcript permission required. |
| P1 | [Sanskrit Bharati](https://www.samskritabharati.in/) | Modern teaching, publications and spoken Sanskrit ecosystem. | Partnership target; do not scrape without permission. |
| P2 | [LearnSanskrit.org](https://learnsanskrit.org/) | Structured English grammar instruction with Sanskrit examples. | CC BY-NC-SA; restricted. |
| P2 | [Ashtadhyayi.com](https://ashtadhyayi.com/) | Grammar texts, commentaries, tools and structured examples. | Terms/provenance audit; request data access. |
| P2 | [Gyaandweep Sanskrit](https://gyaandweep.com/learn/sanskrit/) | Grammar and lexical educational pages. | Site terms unclear; audit/request permission. |

## Exclusions and De-duplication Rules

- Do not count Sangraha, CulturaX, OSCAR, mC4, MADLAD, FineWeb 2, or aggregate Hugging Face datasets independently until URL- and document-level deduplication is complete.
- Keep human-authored, OCR-derived, translated, transliterated, and generated records in separate immutable provenance classes.
- Different manuscripts may be valuable witnesses; different web mirrors of the same edition are duplicates. Preserve witness identity while suppressing repeated training text.
- Do not infer training rights from “open access,” downloadable PDFs, ancient authorship, or a dataset-level license.
- Reserve professionally translated benchmarks and gold morphological corpora from pretraining when evaluation contamination is possible.

## Per-source Audit Checklist

For every adapter or catalog import, record:

- canonical source and artifact URLs, retrieval date, revision, checksum and download method;
- creator, work, recension/witness, edition, publisher, publication date and repository identifier;
- license evidence for the underlying work, edition, transcription, scan and repository;
- human/OCR/synthetic provenance, language, script, period, genre and curriculum tier;
- raw bytes/pages/records, accepted characters/words/model tokens and rejection reasons;
- OCR confidence, language confidence, duplicate cluster and overlap with aggregators;
- release posture: `releasable`, `restricted`, `benchmark`, `synthetic`, or `needs_audit`.
