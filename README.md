# Impresso MALLET Topic Modeling

A comprehensive toolkit for topic modeling using MALLET (MAchine Learning for LanguagE Toolkit) with the Impresso newspaper corpus. This repository provides tools for extracting tokens from linguistic processing data, training topic models, and converting MALLET outputs to structured JSON formats.

## Table of Contents

- [Overview](#overview)
- [Key Documentation Guides](#key-documentation-guides)
- [Features](#features)
- [Prerequisites & Installation](#prerequisites--installation)
- [Project Structure](#project-structure)
- [Quickstart Workflow](#quickstart-workflow)
- [Running a Full Training Pipeline](#running-a-full-training-pipeline)
- [Python Utilities](#python-utilities)
- [MALLET Integration](#mallet-integration)
- [Configuration](#configuration)
- [Dependencies](#dependencies)
- [License](#license)

## Overview

This project facilitates topic modeling workflows for historical newspaper data from the Impresso project. It bridges linguistic processing data (POS-tagged, lemmatized text) with MALLET's topic modeling capabilities and provides utilities to convert results into machine-readable JSON formats.

## Key Documentation Guides

- [Topic Modeling Overview for Digital Humanists](documentation/topic-modeling-overview.md): High-level overview explaining why topic modeling is used for historical newspapers, what topics look like in the Impresso interface and Topic Explorer, the 8-stage pipeline, and how to read topics critically.
- [Topic Labeling Guide](LABELING_README.md): Detailed documentation of the OpenAI LLM-based topic labeling pipeline, prompt design, JSON schema, validation, and cost management.
- [Agent and Pipeline Specifications](AGENTS.md): Pipeline contracts, artifact layout, safety rules, and local development conventions.
- [Release Process](RELEASE_PROCESS.md): Step-by-step checklist for release preparation and publishing.

## Features

- **Token Extraction & Normalization**: Extract tokens from linguistically processed newspaper data with UPOS tag filtering, character normalization for historical spellings, and allow/deny lists
- **Vocabulary Curation**: Build pre-normalized and normalized lemma vocabularies with frequency thresholds and singleton/rare document frequency diagnostics
- **Stratified Sampling**: Sample articles deterministically across newspapers, decades, and years
- **MALLET Topic Modeling**: Seamless interface with MALLET 2.1.0 (and 2.0.8) for LDA topic modeling
- **LLM Topic Labeling**: Automated conceptual topic labeling via OpenAI models with schema validation and domain categorization
- **Downstream Inference Bundling**: Package published models into standalone bundles (`.pipe`, `.inferencer`, `.vocab.tsv.bz2`, `.char-normalization.json`, and self-describing `.config.json`)
- **S3 & Streaming Integration**: Direct read/write support for local files and AWS S3 with overwrite protections

## Prerequisites & Installation

### Prerequisites

- **Python 3.11**
- **Java Development Kit (JDK 8+ / JDK 11+)**: includes both `java` and `javac` (required to compile `CreateMinimalMalletFile.java` for inference pipe extraction).
- **GNU Parallel**: required for multi-threaded newspaper text extraction.
- **Bash 4+**: required by `scripts/*.sh` (on macOS, install modern bash with `brew install bash`).
- **remake (macOS)**: the default macOS `/usr/bin/make` is outdated; use `remake` (`brew install remake`).
- **Pipenv** (recommended) or pip.

### Setup

1. Clone the repository:

```bash
git clone <repository-url>
cd impresso-mallet-topic-modeling
```

2. Install Python dependencies using Pipenv:

```bash
pipenv install
pipenv shell
```

Or using pip:

```bash
pip install -r requirements.txt
```

3. Verify MALLET installation:

```bash
./mallet/bin/mallet --help
```

## Project Structure

```
.
├── mallet/                    # MALLET 2.0.8 distribution
│   ├── bin/
│   │   └── mallet            # MALLET executable script
│   └── lib/
│       ├── mallet.jar        # Core MALLET library
│       └── mallet-deps.jar   # MALLET dependencies
├── mallet-2.1.0/              # MALLET 2.1.0 distribution (used by v3.0 training configs)
│   ├── bin/
│   └── lib/
│
├── lib/                       # Python & Java utilities
│   ├── topic_vocab.py                 # Build pre-norm and final vocabularies
│   ├── build_char_normalization_table.py # Build character normalization mapping
│   ├── normalize_lemma_vocabulary.py  # Map lemma frequencies using char normalization
│   ├── extract_eligible_texts.py      # Extract and filter eligible articles
│   ├── analyze_doc_freq.py            # Singleton and rare lemma diagnostics
│   ├── stratified_sample.py           # Stratified sampling across newspapers & time
│   ├── label_topics.py                # LLM-based structured topic labeling
│   ├── write_inference_model_config.py# Write inference model JSON contract
│   ├── CreateMinimalMalletFile.java   # Strip sample instances to keep only Alphabet/Pipe
│   ├── token_extractor.py             # Extract tokens from lingproc data
│   ├── mallet2topic_description_json.py     # Convert topic descriptions to JSON/JSONL
│   ├── mallet2topic_assignment_jsonl.py     # Stream topic assignments to JSONL
│   ├── copy_uri.py                    # Local/S3 copy utility with overwrite check
│   └── s3_overwrite.py                # S3 safety guard check
│
├── configs/                   # Run-specific configurations (*.mk)
├── cookbook/                  # Shared Impresso make cookbook
├── cookbook-repo-addons/      # Pipeline make rules (topic_training.mk)
├── documentation/             # Topic modeling overview & documentation
├── resources/                 # Vocabulary deny/allow lists and character normalizations
├── scripts/                   # Version-specific orchestration scripts
├── Pipfile                    # Python dependencies
└── LICENSE                    # AGPL-3.0 license
```

## MALLET Integration

### MALLET Directory (`mallet/`)

The `mallet/` directory contains the MALLET topic modeling toolkit:

#### `mallet/bin/mallet`

Bash script that serves as the main entry point for MALLET commands. It:

- Sets up the Java classpath with MALLET JARs
- Configures memory allocation (default: 1GB, configurable via `MEMORY` env var)
- Provides command-line interface to MALLET functionality

**Key Commands:**

- `train-topics` - Train an LDA topic model
- `infer-topics` - Infer topics for new documents using a trained model
- `evaluate-topics` - Estimate probability of new documents under a trained model
- `import-dir` - Load directory contents into MALLET instances
- `import-file` - Load a single file into MALLET instances

**Example Usage:**

```bash
# Train a topic model with 50 topics
./mallet/bin/mallet train-topics \
  --input corpus.mallet \
  --num-topics 50 \
  --output-state topic-state.gz \
  --output-doc-topics doc-topics.txt \
  --output-topic-keys topic-keys.txt
```

#### `mallet/lib/`

Contains MALLET Java libraries:

- **mallet.jar** (2.2 MB) - Core MALLET functionality for topic modeling, classification, and sequence tagging
- **mallet-deps.jar** (2.6 MB) - Required dependencies for MALLET

## Python Utilities

The active training pipeline tools in `lib/` are standalone CLI programs that support streaming I/O, local files, and `s3://` URIs via `smart_open`.

### Vocabulary & Normalization

#### `topic_vocab.py`

Builds pre-normalized or final vocabularies from aggregated lemma frequency distributions.

**Features:**
- Minimum and maximum frequency thresholds
- Allow-lists (`--include-vocab`) and deny-lists (`--exclude-vocab`, `--negative-list`)
- Produces TSV vocabulary output and JSON metadata sidecar

**Usage:**

```bash
pipenv run python lib/topic_vocab.py \
  --lemmafreq s3://bucket/lemmafreq/de.lemmafreq.json.bz2 \
  --language de \
  --min-frequency 100 \
  --max-frequency 5000000 \
  --exclude-vocab resources/exclude-vocab/de.txt \
  --output vocab.tsv.bz2 \
  --metadata-output vocab.manifest.json \
  --run-id my-run-id
```

#### `build_char_normalization_table.py`

Discovers OCR noise and historical character variations from pre-normalized vocabulary distributions and generates a character mapping table.

**Features:**
- Suggests ASCII/standard character mappings for non-standard codepoints
- Generates comprehensive mapping and optional diagnostic report (`--report-json`)

**Usage:**

```bash
pipenv run python lib/build_char_normalization_table.py \
  --min-count 50 \
  --report-json char-normalization.report.json \
  vocab.pre-norm.json.bz2 \
  char-normalization.json
```

#### `normalize_lemma_vocabulary.py`

Applies character normalization mappings to raw lemma frequencies to consolidate spelling variants before final vocabulary creation.

**Features:**
- Applies boundary stripping, core token preservation, and alphabetic ratio checks
- Aggregates frequencies across normalized lemmas

**Usage:**

```bash
pipenv run python lib/normalize_lemma_vocabulary.py \
  lemmafreq.json.bz2 \
  char-normalization.json \
  normalized-lemma-vocab.json.bz2
```

### Data Preparation & Extraction

#### `extract_eligible_texts.py`

Extracts eligible text instances from linguistic processing (`lingproc`) JSONL files.

**Features:**
- Validates tokens against the vocabulary and character normalization table
- Filters by UPOS tag (e.g. `NOUN`, `PROPN`)
- Filters documents by minimum token count, unique lemmas, and maximum length
- Outputs MALLET TSV rows (`doc_id\tDUMMY\tlemma1 lemma2 ...`) and execution statistics

**Usage:**

```bash
pipenv run python lib/extract_eligible_texts.py \
  --input s3://bucket/lingproc/newspaper-1920.jsonl.bz2 \
  --vocab vocab.tsv.bz2 \
  --char-normalization char-normalization.json \
  --language de \
  --pos-tags NOUN PROPN \
  --min-vocab-tokens 20 \
  --output eligible.tsv.bz2 \
  --stats-output stats.json \
  --run-id my-run-id
```

#### `analyze_doc_freq.py`

Scans extracted eligible texts to calculate document frequencies for rare and singleton lemmas.

**Features:**
- Identifies lemmas appearing in only 1 document (singletons) or few documents
- Highlights potential OCR errors and outliers to review before final sampling and training

**Usage:**

```bash
pipenv run python lib/analyze_doc_freq.py \
  --input-prefix s3://bucket/eligible/ \
  --language de \
  --max-doc-freq 2 \
  --output rare-lemmas.tsv.bz2
```

#### `stratified_sample.py`

Draws reproducible, stratified samples from eligible text collections across newspapers and time periods.

**Features:**
- Deterministic sampling with explicit seed (`--seed`)
- Stratification across newspapers and decades/years
- Configurable stratum caps (`--min-per-stratum`, `--max-per-stratum`)
- Produces sample TSV for MALLET import and a complete provenance manifest

**Usage:**

```bash
pipenv run python lib/stratified_sample.py \
  --s3-prefix s3://bucket/eligible/ \
  --sample-size 100000 \
  --seed 42 \
  --strata newspaper,decade \
  --language de \
  --output sample.tsv.bz2 \
  --manifest-output sample.manifest.json \
  --run-id my-run-id
```

### Topic Labeling & Output Conversion

#### `label_topics.py`

Generates human-readable, conceptual topic labels from MALLET topic descriptions using OpenAI models (or offline mock files).

**Features:**
- Structured JSON output conforming to strict schema (short label, long label, category, confidence, rationale)
- Validates that representative words appear literally in the topic word list
- Categorizes topics into 17 standard domains (political, OCR noise, sports, etc.)
- Batch processing with prompt size bounds

**Usage:**

```bash
pipenv run python lib/label_topics.py \
  --input topic_model_topic_description.jsonl.bz2 \
  --output topic_labels.jsonl.gz \
  --model gpt-4o-mini
```

See [LABELING_README.md](LABELING_README.md) for complete details on prompt guidelines, JSON schemas, and mock testing.

#### `mallet2topic_assignment_jsonl.py`

Converts MALLET's document-topic distributions into memory-efficient JSONL lines.

**Features:**
- Streaming converter for large corpora
- Filters by minimum topic probability threshold (`--min-prob`)
- Local and S3 input/output support

**Usage:**

```bash
pipenv run python lib/mallet2topic_assignment_jsonl.py \
  --input doc-topics.txt \
  --output assignments.jsonl.bz2 \
  --min-prob 0.05
```

#### `mallet2topic_description_json.py`

Converts MALLET's `topic-keys` and word weights to structured JSON/JSONL format.

**Usage:**

```bash
pipenv run python lib/mallet2topic_description_json.py \
  --input topic-keys.txt \
  --output topic_descriptions.jsonl.bz2 \
  --top-n 100
```

#### `write_inference_model_config.py`

Generates the self-describing model metadata `.config.json` that binds the inferencer, alphabet pipe, vocabulary, character normalization, and topic descriptions for downstream inference.

**Usage:**

```bash
pipenv run python lib/write_inference_model_config.py \
  --output tm-de-all-v3.0.config.json \
  --model-id tm-de-all-v3.0 \
  --language de \
  --topic-count 100 \
  --mallet-version 2.1.0 \
  --mallet-runtime ./mallet-2.1.0/bin/mallet \
  --preprocessing-mode normalized-lemma \
  --upos-filter NOUN,PROPN \
  --lowercase-token true \
  --min-lemma-length 2 \
  --min-vocab-tokens 20 \
  --min-unique-lemmas 10 \
  --include-titles false \
  --expected-lingproc-run-id v3.0 \
  --expected-lingproc-s3-base s3://130-component-sandbox/lingproc \
  --inferencer tm-de-all-v3.0.inferencer \
  --pipe tm-de-all-v3.0.pipe \
  --vocab tm-de-all-v3.0.vocab.tsv.bz2 \
  --char-normalization tm-de-all-v3.0.char-normalization.json \
  --topic-description tm-de-all-v3.0.topic_model_topic_description.jsonl.bz2
```

## Quickstart Workflow

For a standard training run across the corpus, versioned bash wrappers in `scripts/` orchestrate multi-language execution in sequence.

```bash
# 1. Prepare vocabularies, eligible texts, and diagnostic lists for all languages:
./scripts/prepare-v3.0.0.sh

# 2. Review diagnostic outputs (singletons & rare words) in build.d/ or logs/
# Add noise terms to resources/exclude-vocab/<lang>.txt if needed.

# 3. Train topic models (sample -> MALLET import -> LDA train -> descriptions -> LLM labels -> smoke inference):
./scripts/train-v3.0.0.sh

# 4. Build downstream inference bundles (config, pipe, inferencer, vocab, normalization):
./scripts/build-inference-bundle-v3.0.0.sh
```

Or run single language targets via Make (`remake` on macOS):

```bash
# Prepare German model inputs:
remake topic-training-prepare-de CFG=configs/config-topic-training-tm-de-all-v3.0.mk

# Run training from existing sample:
remake topic-training-from-sample-de CFG=configs/config-topic-training-tm-de-all-v3.0.mk
```

## Dependencies

### Python Packages

Defined in `Pipfile`:

- **impresso-mallet-lda** - Impresso-specific MALLET utilities
- **python-dotenv** - Environment variable management
- **smart-open[s3]** - Unified interface for local/S3 file operations
- **boto3** (==1.35.95) - AWS SDK for S3 operations
- **jq** - JSON processing
- **pandas** - Data manipulation (used in converters)

### System Requirements

- **Java 8+** - Required for MALLET
- **Python 3.11** - Specified in Pipfile
- **GNU Make** - For cookbook processing pipelines (optional)

### Installing Dependencies

```bash
# Using Pipenv (recommended)
pipenv install

# Using pip
pip install python-dotenv "smart-open[s3]" "boto3==1.35.95" jq pandas

# Install Impresso MALLET utilities
pip install git+https://github.com/impresso/impresso-mallet-topic-inference.git@main#subdirectory=lib
```

## Configuration

### Environment Variables

Configure memory for MALLET (note: `MEMORY` is read by MALLET 2.0.8, while `MALLET_MEMORY` is used by MALLET 2.1.0; Makefile targets export both automatically):

```bash
export MEMORY=4g         # MALLET 2.0.8 (default: 1g)
export MALLET_MEMORY=4g  # MALLET 2.1.0 (default: 1g)
```

Configure OpenAI credentials for topic labeling (optional, incurred during `topic-training-label-*`):

```bash
export OPENAI_API_KEY=your_openai_key
# Optional model override (defaults to gpt-4o-mini):
export TOPIC_TRAIN_LABEL_MODEL=gpt-4o-mini
# Or use mock responses for cost-free testing:
export TOPIC_TRAIN_LABEL_MOCK_RESPONSE=TRUE
```

### S3 Authentication

Configure AWS credentials for S3 access:

```bash
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=us-east-1
```

Or use AWS CLI configuration:

```bash
aws configure
```

## Cookbook Integration

This repository integrates with the [Impresso Make-Based Processing Cookbook](cookbook/README.md) for automated pipeline execution. The cookbook provides:

- Makefile-based orchestration
- S3 synchronization
- Distributed processing support
- Progress tracking with stamp files

See [cookbook/README.md](cookbook/README.md) for detailed information.

## Running a Full Training Pipeline

Version-specific training scripts in `scripts/` orchestrate all four language models in sequence, capture per-language logs, and guide you through the mandatory vocabulary review step.

### Step 1 — Preparation (vocab + eligible texts + diagnostics)

The scripts accept environment variables to configure the run. Set them as needed before calling the script:

| Variable                         | Description                                      | Default       |
| -------------------------------- | ------------------------------------------------ | ------------- |
| `TOPIC_TRAIN_BUCKET`             | S3 bucket for all training outputs               | set in config |
| `TOPIC_TRAIN_FORCE_S3_OVERWRITE` | Overwrite existing S3 artifacts (`TRUE`/`FALSE`) | `FALSE`       |
| `COLLECTION_JOBS`                | Parallel newspaper jobs per language             | `nproc/2`     |
| `MAX_LOAD`                       | System load limit for GNU parallel               | `nproc`       |

```bash
# Minimal
./scripts/prepare-v3.0.0.sh

# With all variables
TOPIC_TRAIN_BUCKET=132-component-final \
  COLLECTION_JOBS=4 MAX_LOAD=8 \
  ./scripts/prepare-v3.0.0.sh
```

Logs are written to `logs/prepare-v3.0.0-<lang>-<timestamp>.log`.

After the script completes, **review the diagnostic vocab output** for each language:

- `topic-training-singleton-lemmas-<lang>` output — lemmas appearing in only one document
- `topic-training-rare-docfreq-negative-lemmas-<lang>` output — rare lemmas that are likely noise

Update `resources/exclude-vocab/` with any additional terms to exclude, then rerun vocabulary for that language:

```bash
make topic-training-vocab-de \
  CFG=configs/config-topic-training-tm-de-all-v3.0.mk \
  TOPIC_TRAIN_ADDITIONAL_EXCLUDE_VOCAB_de=resources/exclude-vocab/my-extra-exclusions.txt
```

### Step 2 — Training (sample + MALLET import + train + describe + smoke-infer)

```bash
# Minimal
./scripts/train-v3.0.0.sh

# With all variables
TOPIC_TRAIN_BUCKET=132-component-final \
  COLLECTION_JOBS=4 MAX_LOAD=8 \
  ./scripts/train-v3.0.0.sh
```

Logs are written to `logs/train-v3.0.0-<lang>-<timestamp>.log`.

Make stamp files ensure already-completed steps are skipped on re-runs. To force a specific step to re-run, delete the corresponding stamp file in `build.d/`.

### Step 3 — Build inference bundles

After training has produced the model artifacts, build the flat inference bundles:

```bash
# All languages
./scripts/build-inference-bundle-v3.0.0.sh

# One language
./scripts/build-inference-bundle-v3.0.0.sh lb
```

Logs are written to `logs/build-inference-bundle-v3.0.0-<lang>-<timestamp>.log`.
The script requires Bash 4 or newer; on macOS, install a current Bash with
Homebrew if `/bin/bash` is too old.

### Single-language runs

You can also run individual make targets directly for one language at a time:

```bash
# Preparation only
make topic-training-prepare-de CFG=configs/config-topic-training-tm-de-all-v3.0.mk

# Full pipeline
make topic-training-all-de CFG=configs/config-topic-training-tm-de-all-v3.0.mk

# Publish after review
make topic-training-publish-de CFG=configs/config-topic-training-tm-de-all-v3.0.mk
```

Publishing also creates a flat inference bundle under:

```text
s3://<bucket>/topics-mallet/<run-id>/inference/models/tm/
```

For each language/model, the bundle contains:

- `{model_id}.config.json`
- `{model_id}.pipe`
- `{model_id}.inferencer`
- `{model_id}.vocab.tsv.bz2`
- `{model_id}.char-normalization.json`
- `{model_id}.topic_model_topic_description.jsonl.bz2`

The generated config is the downstream inference contract. It records MALLET
`2.1.0`, the normalized-lemma preprocessing mode, the expected lingproc S3
run/path used for training, and the sibling artifact filenames. The `.pipe` file
is a slim MALLET file derived from the training sample, retaining the pipe and
alphabet without shipping the full sample.

Run `make help-topic-training` to see all available targets.

## Contributing

Contributions are welcome! This project is part of the Impresso project for historical newspaper processing.

### Development Guidelines

- Follow Python PEP 8 style guidelines
- Add docstrings to new functions
- Test with both local and S3 data sources
- Update this README for new utilities

## License

This project is licensed under the **GNU Affero General Public License v3.0** (AGPL-3.0).

See [LICENSE](LICENSE) for the full license text.

## Credits

**Original Authors:**

- Phillip Ströbel (pstroebel@cl.uzh.ch)
- Institute of Computational Linguistics, University of Zurich

**Impresso Project:**

- Part of the Impresso - Media Monitoring of the Past project
- Processing historical newspaper archives

## References

- [MALLET: MAchine Learning for LanguagE Toolkit](http://mallet.cs.umass.edu/)
- [Impresso Project](https://impresso-project.ch/)
- [LDA Topic Modeling](https://en.wikipedia.org/wiki/Latent_Dirichlet_allocation)

## Support

For issues and questions:

- Open an issue in the repository
- Consult the [cookbook documentation](cookbook/README.md)
- Review MALLET documentation for topic modeling questions
