# Impresso MALLET Topic Modeling

A comprehensive toolkit for topic modeling using MALLET (MAchine Learning for LanguagE Toolkit) with the Impresso newspaper corpus. This repository provides tools for extracting tokens from linguistic processing data, training topic models, and converting MALLET outputs to structured JSON formats.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Project Structure](#project-structure)
- [MALLET Integration](#mallet-integration)
- [Python Utilities](#python-utilities)
- [Usage Examples](#usage-examples)
- [Dependencies](#dependencies)
- [License](#license)

## Overview

This project facilitates topic modeling workflows for historical newspaper data from the Impresso project. It bridges linguistic processing data (POS-tagged, lemmatized text) with MALLET's topic modeling capabilities and provides utilities to convert results into machine-readable JSON formats.

## Features

- **Token Extraction**: Extract tokens from linguistically processed newspaper data with POS tag and language filtering
- **Frequency Distribution**: Build and filter frequency distributions across corpora
- **Topic Model Training**: Interface with MALLET for LDA topic modeling
- **Format Conversion**: Convert MALLET outputs to JSON/JSONL formats
- **S3 Integration**: Read and write data directly from/to S3 storage
- **Multi-language Support**: Process documents in multiple languages with language-specific filtering

## Installation

### Prerequisites

- Python 3.11 or higher
- Java Runtime Environment (for MALLET)
- Pipenv (recommended) or pip

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
├── mallet/                    # MALLET topic modeling toolkit
│   ├── bin/
│   │   └── mallet            # MALLET executable script
│   └── lib/
│       ├── mallet.jar        # Core MALLET library
│       └── mallet-deps.jar   # MALLET dependencies
│
├── lib/                       # Python utilities
│   ├── token_extractor.py             # Extract tokens from lingproc data
│   ├── make_freq_dist.py              # Create frequency distributions
│   ├── freq_filter.py                 # Filter texts by frequency
│   ├── aggregate_freq_dist.py         # Aggregate frequency distributions
│   ├── sampling.py                    # Sample data for topic modeling
│   ├── lingproc2simplified_per_language.py  # Convert lingproc to simplified format
│   ├── mallet2topic_assignment_json.py      # Convert topic assignments to JSON
│   ├── mallet2topic_assignment_jsonl.py     # Convert topic assignments to JSONL
│   └── mallet2topic_description_json.py     # Convert topic descriptions to JSON
│
├── cookbook/                  # Processing pipeline configurations
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

### Data Preparation

#### `token_extractor.py`

Extracts tokens from linguistically processed (lingproc) JSONL data with filtering capabilities.

**Features:**

- POS tag filtering (e.g., extract only NOUN, VERB, ADJ)
- Language filtering for multi-lingual corpora
- S3 file support with smart-open
- Streaming processing for large files

**Usage:**

```bash
python lib/token_extractor.py \
  --input s3://bucket/lingproc/file.jsonl.bz2 \
  --pos-tags NOUN VERB ADJ \
  --languages de fr \
  --output tokens.txt
```

**Input Format:** Lingproc JSONL with structure:

```json
{
  "id": "doc-id",
  "sents": [
    {
      "lg": "de",
      "tok": [{ "t": "token", "p": "NOUN", "l": "lemma" }]
    }
  ]
}
```

**Output:** Document ID followed by space-separated tokens (one document per line)

#### `lingproc2simplified_per_language.py`

Converts complex lingproc format to simplified per-language format suitable for topic modeling.

**Features:**

- Extract tokens, POS tags, and lemmas per language
- Synchronize token-level information across sentences
- Filter by language
- S3 input/output support

**Usage:**

```bash
python lib/lingproc2simplified_per_language.py \
  --s3-prefix s3://bucket/lingproc/newspaper-1927.jsonl.bz2 \
  --language de \
  --output simplified-de.jsonl
```

**Output Format:**

```json
{
  "id": "doc-id",
  "tokens": ["token1", "token2"],
  "pos_tags": ["NOUN", "VERB"],
  "lemmas": ["lemma1", "lemma2"]
}
```

### Frequency Analysis

#### `make_freq_dist.py`

Creates frequency distributions over corpora for vocabulary pruning.

**Features:**

- Multiprocessing support for large corpora
- Per-language frequency tracking
- Punctuation filtering
- Outputs sorted frequency lists

**Usage:**

```bash
python lib/make_freq_dist.py \
  --input-dir data/json/ \
  --output-dir resources/freqdists/
```

**Output:** TSV files with `count\ttoken` format per language

#### `aggregate_freq_dist.py`

Aggregates multiple frequency distribution files into a single distribution.

**Usage:**

```bash
python lib/aggregate_freq_dist.py
```

Reads from `resources/freqdists/*` and outputs aggregated counts.

#### `freq_filter.py`

Filters texts using frequency distribution files to remove rare/common words.

**Features:**

- Minimum/maximum frequency thresholds
- Multiprocessing for performance
- Preserves document structure

**Usage:**

```bash
python lib/freq_filter.py \
  --input-dir data/json/ \
  --freq-dist resources/freqdists/de.txt \
  --min-freq 5 \
  --max-freq 10000 \
  --output-dir filtered/
```

#### `sampling.py`

Samples documents from large corpora for topic modeling experiments.

**Features:**

- Random sampling with fixed seed (reproducibility)
- Configurable sample size
- Maintains UTF-8 encoding

**Usage:**

```bash
python lib/sampling.py \
  --input corpus.txt \
  --sample-size 10000 \
  --output sample.txt
```

### MALLET Output Conversion

#### `mallet2topic_assignment_json.py`

Converts MALLET topic assignment output to JSON format.

**Supported Formats:**

- **Matrix Format**: Dense probability distributions per document
- **Sparse Format**: Only non-zero topic probabilities

**Features:**

- Filters topics by minimum probability threshold
- Configurable top-N topics per document
- Extracts document IDs from file paths

**Usage:**

```bash
python lib/mallet2topic_assignment_json.py \
  --input doc-topics.txt \
  --format sparse \
  --min-prob 0.01 \
  --top-n 5 \
  --output assignments.json
```

**Input Format (Sparse):**

```
0  doc-id  56  0.3638  653  0.0608  718  0.0355
```

**Output Format:**

```json
{
  "doc-id": [
    { "topic_id": 56, "probability": 0.3638 },
    { "topic_id": 653, "probability": 0.0608 }
  ]
}
```

#### `mallet2topic_assignment_jsonl.py`

Streaming version that outputs JSONL (one JSON object per line).

**Features:**

- Memory-efficient streaming processing
- Supports both local and S3 files
- Progress logging every 1000 lines
- Configurable probability thresholds

**Usage:**

```bash
python lib/mallet2topic_assignment_jsonl.py \
  --input doc-topics.txt \
  --output assignments.jsonl \
  --min-prob 0.05
```

**Output Format (JSONL):**

```jsonl
{"id": "doc1", "topics": [{"topic_id": 5, "prob": 0.4}, {"topic_id": 12, "prob": 0.3}]}
{"id": "doc2", "topics": [{"topic_id": 8, "prob": 0.6}]}
```

#### `mallet2topic_description_json.py`

Converts MALLET topic-keys output to structured JSON format with word probabilities.

**Features:**

- Normalizes word probabilities per topic
- Filters words by minimum probability
- Top-N words per topic
- Multiple output formats (single JSON or per-topic files)

**Usage:**

```bash
python lib/mallet2topic_description_json.py \
  --input topic-keys.txt \
  --min-prob 0.001 \
  --top-n 100 \
  --output topics.json
```

**Input Format:**

```
0  0.05  word1 word2 word3 ...
```

**Output Format:**

```json
{
  "topic_0": {
    "topic_id": 0,
    "word_count": 100,
    "words": [
      { "word": "word1", "probability": 0.15 },
      { "word": "word2", "probability": 0.12 }
    ]
  }
}
```

## Usage Examples

### Complete Topic Modeling Workflow

```bash
# 1. Extract tokens from lingproc data
python lib/token_extractor.py \
  --input s3://bucket/lingproc/newspaper-1927.jsonl.bz2 \
  --pos-tags NOUN VERB ADJ \
  --languages de \
  --output mallet-input.txt

# 2. Import into MALLET format
./mallet/bin/mallet import-file \
  --input mallet-input.txt \
  --output corpus.mallet \
  --keep-sequence

# 3. Train topic model (50 topics, 1000 iterations)
./mallet/bin/mallet train-topics \
  --input corpus.mallet \
  --num-topics 50 \
  --num-iterations 1000 \
  --output-state topic-state.gz \
  --output-doc-topics doc-topics.txt \
  --output-topic-keys topic-keys.txt \
  --optimize-interval 10 \
  --num-threads 4

# 4. Convert outputs to JSON
python lib/mallet2topic_description_json.py \
  --input topic-keys.txt \
  --output topics.json

python lib/mallet2topic_assignment_jsonl.py \
  --input doc-topics.txt \
  --output assignments.jsonl \
  --min-prob 0.05
```

### Working with S3 Data

```bash
# Extract tokens directly from S3
python lib/token_extractor.py \
  --input s3://42-processed-data/lingproc/newspaper.jsonl.bz2 \
  --pos-tags NOUN \
  --output tokens.txt

# Convert and upload to S3
python lib/lingproc2simplified_per_language.py \
  --s3-prefix s3://input-bucket/lingproc/ \
  --language fr \
  --output s3://output-bucket/simplified/fr.jsonl
```

### Frequency-Based Filtering

```bash
# 1. Build frequency distribution
python lib/make_freq_dist.py \
  --input-dir data/processed/ \
  --output-dir freqdists/

# 2. Filter corpus (remove words appearing < 5 or > 10000 times)
python lib/freq_filter.py \
  --input-dir data/processed/ \
  --freq-dist freqdists/de.txt \
  --min-freq 5 \
  --max-freq 10000 \
  --output-dir data/filtered/

# 3. Sample for quick experiments
python lib/sampling.py \
  --input data/filtered/corpus.txt \
  --sample-size 5000 \
  --output sample-5k.txt
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

Configure memory for MALLET:

```bash
export MEMORY=4g  # Allocate 4GB to MALLET (default: 1g)
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

```bash
./scripts/prepare-v3.0.0.sh
# Optional: control parallelism
COLLECTION_JOBS=4 MAX_LOAD=8 ./scripts/prepare-v3.0.0.sh
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
./scripts/train-v3.0.0.sh
# Optional: control parallelism (only affects the eligible step if it re-runs)
COLLECTION_JOBS=4 MAX_LOAD=8 ./scripts/train-v3.0.0.sh
```

Logs are written to `logs/train-v3.0.0-<lang>-<timestamp>.log`.

Make stamp files ensure already-completed steps are skipped on re-runs. To force a specific step to re-run, delete the corresponding stamp file in `build.d/`.

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
