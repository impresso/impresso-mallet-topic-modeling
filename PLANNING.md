# MALLET Topic Training Plan

This repository builds MALLET topic models and publishes the model contract needed
by the separate MALLET topic inference cookbook. It does not run full-corpus
inference. Full inference should consume the inferencer, model metadata,
vocabulary, and topic descriptions produced here.

## Storage Contract

All intermediate training files are stored below one S3 run prefix:

```text
s3://130-component-sandbox/topics-mallet/{TRAIN_RUN_ID}/
```

The sandbox bucket is for testing. The same layout should later be promoted to:

```text
s3://132-component-final/topics-mallet/{TRAIN_RUN_ID}/
```

The make variables are:

```makefile
TOPIC_TRAIN_BUCKET ?= 130-component-sandbox
TOPIC_TRAIN_PREFIX ?= topics-mallet
TOPIC_TRAIN_RUN_ID ?= tm-training-v1
```

Every local mirror path is derived from `$(BUILD_DIR)`:

```makefile
S3_TOPIC_TRAIN_BASE_PATH := s3://$(TOPIC_TRAIN_BUCKET)/$(TOPIC_TRAIN_PREFIX)/$(TOPIC_TRAIN_RUN_ID)
LOCAL_TOPIC_TRAIN_BASE_PATH := $(BUILD_DIR)/$(TOPIC_TRAIN_BUCKET)/$(TOPIC_TRAIN_PREFIX)/$(TOPIC_TRAIN_RUN_ID)
```

## Pipeline Scope

This repo owns:

```text
lemmafreq -> vocabulary -> eligible texts -> training sample -> MALLET model
          -> inferencer -> topic descriptions -> small inference smoke test
```

The topic inference cookbook owns:

```text
inferencer + vocabulary/model contract -> full-corpus inference -> assignment shards
```

## Artifact Layout

```text
s3://.../{TRAIN_RUN_ID}/
  vocab/{lang}.vocab.tsv.bz2
  vocab/{lang}.vocab.metadata.json
  eligible/{newspaper}.eligible.tsv.bz2
  eligible/{newspaper}.stats.json
  sample/sample.tsv.bz2
  sample/sample.manifest.json
  mallet/{lang}.sample.mallet
  models/{lang}.model
  models/{lang}.inferencer
  models/{lang}.topickeys
  models/{lang}.topicwordweights.bz2
  models/{lang}.sample.doctopics.bz2
  jsonl/{lang}.topic_model_topic_description.jsonl.bz2
  smoke/{lang}.doctopics
  smoke/{lang}.topic_assignment.jsonl.bz2
  metadata/{lang}.training.json
  logs/
```

Large full-corpus `.txt`, `.mallet`, and `.doctopics` files are intentionally
not produced by this repo.

## Make Decomposition

Training-specific rules live in `cookbook-repo-addons/topic_training.mk`. The
add-on should be included by the local cookbook Makefile, after the common
cookbook setup, logging, path, and S3 helpers.

Main targets:

```text
topic-training-vocab-{lang}
topic-training-eligible-{newspaper}-{lang}
topic-training-eligible-{lang}
topic-training-sample-{lang}
topic-training-import-{lang}
topic-training-train-{lang}
topic-training-describe-{lang}
topic-training-smoke-infer-{lang}
topic-training-publish-{lang}
topic-training-all-{lang}
```

Run with `remake` locally on macOS. Keep `make` as the command name in Makefiles
and documentation.

## Stage Details

### 1. Vocabulary

Input:

```text
s3://.../lemma-freq/{RUN_ID_LINGPROC}/{lang}/ALL.upos-PROPN_NOUN.minlength-2.lemmafreq.json.bz2
resources/exclude-vocab/{lang}.txt
optional include/exclude vocabulary files
```

Output:

```text
vocab/{lang}.vocab.tsv.bz2
vocab/{lang}.vocab.metadata.json
```

Filters:

- minimum corpus frequency
- maximum corpus frequency
- minimum lemma length
- negative lemma list
- optional include vocabulary
- optional exclude vocabulary

### 2. Eligible Texts

Each newspaper/language target streams linguistic-processing JSONL from S3,
extracts `PROPN` and `NOUN` lemmas from `sents` and optionally `tsents`, filters
against the vocabulary, and writes only content items that satisfy minimum text
requirements.

Output line format:

```text
ci_id<TAB>DUMMY<TAB>lemma1 lemma2 lemma3 ...
```

Minimum requirements are configurable:

```makefile
TOPIC_TRAIN_MIN_VOCAB_TOKENS ?= 10
TOPIC_TRAIN_MIN_UNIQUE_LEMMAS ?= 5
TOPIC_TRAIN_MAX_TOKENS ?= 1500
```

### 3. Sampling

Sampling consumes eligible shards and creates one training sample per language.
The default stratum is newspaper plus decade, derived from `ci_id`.

The sample manifest records:

- source paths
- sample size
- seed
- stratum counts
- selected counts
- input/output paths

### 4. MALLET Import

Only the sample is imported into MALLET. The full corpus is not imported here.

```bash
./mallet/bin/mallet import-file \
  --input sample.tsv \
  --output sample.mallet \
  --keep-sequence
```

### 5. Training

Training runs on the sample and must create an inferencer:

```bash
./mallet/bin/mallet train-topics \
  --input sample.mallet \
  --output-model models/{lang}.model \
  --inferencer-filename models/{lang}.inferencer \
  --output-topic-keys models/{lang}.topickeys \
  --topic-word-weights-file models/{lang}.topicwordweights \
  --output-doc-topics models/{lang}.sample.doctopics \
  --num-topics $(MALLET_NUM_TOPICS) \
  --num-iterations $(MALLET_TRAIN_ITERATIONS) \
  --optimize-interval $(MALLET_OPTIMIZE_INTERVAL) \
  --num-threads $(MALLET_THREADS) \
  --random-seed $(MALLET_RANDOM_SEED)
```

`MALLET_TRAIN_ITERATIONS` is a first-class hyperparameter and is written to
training metadata.

### 6. Topic Description

Topic-word weights are converted to Impresso topic description JSONL. This output
is part of the model contract for downstream consumers.

### 7. Smoke Inference

The smoke test applies the inferencer to a small sample only. It verifies that
the model artifacts are usable without attempting full-corpus inference.

## Implementation Files

```text
cookbook-repo-addons/topic_training.mk
lib/topic_vocab.py
lib/extract_eligible_texts.py
lib/stratified_sample.py
lib/mallet2topic_description_json.py
```

The Python tools support local paths and S3 paths through `smart_open`. S3 upload
and WIP protection should use cookbook helpers where the add-on is included in a
full cookbook checkout.
