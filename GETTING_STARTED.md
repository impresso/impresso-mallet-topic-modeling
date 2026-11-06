# Getting Started with Impresso MALLET Topic Training

Welcome! This guide is designed to help new users and contributors set up, understand, and run the MALLET topic modeling training pipeline on historical newspaper data.

Whether you want to understand the training architecture, test a local workflow without cloud credentials, or run the production pipeline against S3, this document walks you through each step.

---

## 1. Overview: What Does This Pipeline Do?

This repository owns the **training-side contract** for the Impresso project's LDA topic models. It takes linguistically processed newspaper articles and builds fully-trained, labeled, self-describing topic models:

```
+-------------------------------------------------------------------------------------------------+
| 1. Lemma Frequency & Character Normalization                                                    |
|    Aggregate lemma frequencies -> Build pre-norm vocab -> Derive character normalization table  |
|    -> Produce clean, normalized lemma vocabulary                                                |
+-------------------------------------------------------------------------------------------------+
                                                |
                                                v
+-------------------------------------------------------------------------------------------------+
| 2. Eligible Text Extraction & Diagnostics                                                       |
|    Filter articles by UPOS (NOUN, PROPN), length, and vocabulary -> Run singleton & rare       |
|    document-frequency diagnostics to review noise and OCR artifacts                             |
+-------------------------------------------------------------------------------------------------+
                                                |
                                                v
+-------------------------------------------------------------------------------------------------+
| 3. Stratified Sampling                                                                          |
|    Draw reproducible, balanced samples across newspapers and time periods (decades/years)       |
+-------------------------------------------------------------------------------------------------+
                                                |
                                                v
+-------------------------------------------------------------------------------------------------+
| 4. MALLET Import & LDA Training                                                                 |
|    Import sample to MALLET instances -> Train LDA with hyperparameter optimization              |
|    -> Output models, inferencer, topic-keys, and topic-word weights                             |
+-------------------------------------------------------------------------------------------------+
                                                |
                                                v
+-------------------------------------------------------------------------------------------------+
| 5. Topic Descriptions & Automated LLM Labeling                                                  |
|    Convert word weights to JSONL -> Prompt OpenAI LLM (or mock) for conceptual labels & domains |
+-------------------------------------------------------------------------------------------------+
                                                |
                                                v
+-------------------------------------------------------------------------------------------------+
| 6. Downstream Inference Bundle & Publishing                                                     |
|    Extract slim minimal .pipe -> Generate self-describing .config.json -> Publish bundle        |
+-------------------------------------------------------------------------------------------------+
```

Supported languages include **German (`de`)**, **French (`fr`)**, **English (`en`)**, and **Luxembourgish (`lb`)**.

> [!NOTE]
> This repository **does not** perform full-corpus topic inference. Downstream inference is performed by the sibling project [`impresso-mallet-topic-inference`](https://github.com/impresso/impresso-mallet-topic-inference), which directly consumes the published inference bundles produced here.

---

## 2. Environment & Prerequisites

### System Requirements
- **Python**: 3.11 (`pipenv` is used to manage virtual environments and dependencies)
- **Java**: JDK 8+ or JDK 11+ (both `java` and `javac` are required; `javac` compiles `lib/CreateMinimalMalletFile.java`)
- **GNU Parallel**: Required for parallel newspaper extraction across CPUs
- **GNU Make / remake**: On macOS, default `/usr/bin/make` is outdated (3.81). Install and use `remake` (`brew install remake`)
- **Bash 4+**: Required by orchestration scripts in `scripts/` (macOS users: `brew install bash`)

### Step-by-Step Installation

#### macOS
```bash
# 1. Install prerequisites via Homebrew
brew install python@3.11 openjdk@17 make remake parallel bash

# 2. Configure Java in your shell
export JAVA_HOME=$(/usr/libexec/java_home -v 17)
# (Recommended) Add to ~/.zshrc:
# echo 'export JAVA_HOME=$(/usr/libexec/java_home -v 17)' >> ~/.zshrc
```

#### Ubuntu / Debian
```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip openjdk-17-jdk \
                    make parallel bash coreutils
```

### Python Virtual Environment Setup

```bash
# 1. Clone repository
git clone https://github.com/impresso/impresso-mallet-topic-modeling.git
cd impresso-mallet-topic-modeling

# 2. Install dependencies using Pipenv
pipenv install
```

Verify your environment:
```bash
# Verify Python scripts compile
pipenv run python -m py_compile lib/*.py

# Verify MALLET 2.1.0 binary
./mallet-2.1.0/bin/mallet --help

# Verify Make orchestration
remake help-topic-training
```

---

## 3. Quickstart: Local MALLET Training Walkthrough (No S3 / No Credentials)

You do not need AWS S3 access or credentials to test MALLET importing, LDA training, and topic description generation. A small compressed corpus sample is available in `test.jsonl.bz2`:

```bash
# 1. Create a local temporary workspace
mkdir -p build.d/quickstart

# 2. Import 100 sample articles into MALLET instance format
./mallet-2.1.0/bin/mallet import-file \
  --input <(bzcat test.jsonl.bz2 | head -n 100) \
  --output build.d/quickstart/sample.mallet \
  --keep-sequence

# 3. Train a quick 5-topic LDA model (20 iterations)
./mallet-2.1.0/bin/mallet train-topics \
  --input build.d/quickstart/sample.mallet \
  --num-topics 5 \
  --num-iterations 20 \
  --inferencer-filename build.d/quickstart/sample.inferencer \
  --output-topic-keys build.d/quickstart/sample.topickeys \
  --topic-word-weights-file build.d/quickstart/sample.topicwordweights

# 4. Convert topic word weights into structured topic descriptions
pipenv run python lib/mallet2topic_description_json.py \
  build.d/quickstart/sample.topicwordweights \
  -N 5 \
  -L en \
  -M test-quickstart-v1 \
  -o build.d/quickstart/sample.topic_description.jsonl.bz2

# 5. Inspect the generated topics
bzcat build.d/quickstart/sample.topic_description.jsonl.bz2 | head -n 1 | jq .
```

---

## 4. Understanding Pipeline Data Contracts & Artifacts

### 1. Linguistic Processing Input (`lingproc` format)
Inputs are JSONL lines containing lemmatized, POS-tagged sentences:
```json
{
  "id": "doc-identifier-123",
  "sents": [
    {
      "lg": "de",
      "tok": [
        {"t": "Bundesrat", "p": "NOUN", "l": "Bundesrat"},
        {"t": "beschliesst", "p": "VERB", "l": "beschliessen"}
      ]
    }
  ]
}
```

### 2. Extracted Eligible Text Format (MALLET TSV)
Articles that meet vocabulary and length criteria are extracted as single rows:
```tsv
doc_id	DUMMY	lemma1 lemma2 lemma3 ...
```

### 3. Downstream Inference Model Bundle
Published models are bundled under `inference/models/tm/` with the following contract:
- `{model_id}.config.json`: Self-describing JSON specifying the preprocessing mode, UPOS tags, minimum length, and artifact names.
- `{model_id}.pipe`: Slim MALLET binary containing only the alphabet pipe (instances stripped).
- `{model_id}.inferencer`: Binary MALLET topic inferencer.
- `{model_id}.vocab.tsv.bz2`: Frequency-trimmed vocabulary TSV.
- `{model_id}.char-normalization.json`: Character normalization mapping.
- `{model_id}.topic_model_topic_description.jsonl.bz2`: Topic terms and weights.

---

## 5. Production Pipeline Execution

Production workflows use configurations in `configs/` and targets orchestrated by `Makefile` and `cookbook-repo-addons/topic_training.mk`.

### Prerequisites for Production
1. **S3 Credentials**: Configure AWS credentials with read/write access to Impresso buckets:
   ```bash
   export AWS_ACCESS_KEY_ID=your_key
   export AWS_SECRET_ACCESS_KEY=your_secret
   export AWS_DEFAULT_REGION=us-east-1
   ```
2. **OpenAI API Key** (for topic labeling):
   ```bash
   export OPENAI_API_KEY=your_openai_api_key
   # Or set TOPIC_TRAIN_LABEL_MOCK_RESPONSE=TRUE for cost-free testing
   ```

### Option A: Automated Multi-Language Scripts

Versioned scripts in `scripts/` automate all four languages (`de`, `fr`, `en`, `lb`):

```bash
# Step 1: Preparation (Vocabularies + Eligible extraction + Diagnostics)
./scripts/prepare-v3.0.0.sh

# Step 2: Review diagnostics (singletons and rare words) in build.d/ or logs/
# Update resources/exclude-vocab/<lang>.txt if extra OCR artifacts appear.

# Step 3: Train models (sample -> MALLET import -> LDA train -> descriptions -> LLM labels -> smoke infer)
./scripts/train-v3.0.0.sh

# Step 4: Assemble inference bundles
./scripts/build-inference-bundle-v3.0.0.sh
```

### Option B: Single-Language Make Targets

You can execute granular pipeline stages for any specific language (e.g. German `de`):

```bash
CFG=configs/config-topic-training-tm-de-all-v3.0.mk

# 1. Build pre-normalized vocab & character normalization
remake topic-training-pre-norm-vocab-de CFG=$CFG
remake topic-training-char-normalization-de CFG=$CFG
remake topic-training-normalized-lemma-vocab-de CFG=$CFG
remake topic-training-vocab-de CFG=$CFG

# 2. Extract eligible texts for a single newspaper (or entire language)
remake topic-training-eligible-newspaper LNG=de NEWSPAPER=BL/AATA CFG=$CFG
remake topic-training-eligible-de CFG=$CFG

# 3. Check rare and singleton diagnostics
remake topic-training-singleton-lemmas-de CFG=$CFG
remake topic-training-rare-docfreq-negative-lemmas-de CFG=$CFG

# 4. Sample and Train
remake topic-training-sample-de CFG=$CFG
remake topic-training-train-de CFG=$CFG

# 5. Describe, Label, and Smoke-Infer
remake topic-training-describe-de CFG=$CFG
remake topic-training-label-de CFG=$CFG
remake topic-training-smoke-infer-de CFG=$CFG

# 6. Build bundle and publish
remake topic-training-inference-bundle-de CFG=$CFG
remake topic-training-publish-de CFG=$CFG
```

---

## 6. Troubleshooting & FAQ

- **`make: *** [topic-training-...] Error 1` on macOS**:
  The default `/usr/bin/make` on macOS is version 3.81, which cannot evaluate modern make syntax. Always run make commands using `remake` (e.g. `remake help-topic-training`).
- **`javac: command not found` during inference bundle creation**:
  `topic-training-inference-pipe-*` compiles `lib/CreateMinimalMalletFile.java` to strip training instances from the sample. Ensure a full JDK (not just JRE) is installed and active in your `$PATH`.
- **MALLET Java OutOfMemoryError**:
  Increase MALLET heap allocation before running:
  ```bash
  export MEMORY=8g         # Read by MALLET 2.0.8
  export MALLET_MEMORY=8g  # Read by MALLET 2.1.0
  ```
- **S3 Overwrite Blocked**:
  By default, `TOPIC_TRAIN_FORCE_S3_OVERWRITE=FALSE` prevents accidental destruction of existing S3 artifacts. Pass `TOPIC_TRAIN_FORCE_S3_OVERWRITE=TRUE` when intentionally re-running a stage.
- **Testing Topic Labeling Without API Costs**:
  Pass `TOPIC_TRAIN_LABEL_MOCK_RESPONSE=TRUE` (or `--mock-response <path>`) to validate the labeling parser and JSONL format without making live OpenAI API calls.
