# Luxembourgish MALLET topic-training configuration.
#
# This config mirrors the existing inference model specification:
#   tm-lb-all-v3.0.config.json
#
# Luxembourgish model specification for v3.0:
#   {
#     "uposFilter": ["NOUN","PROPN"],
#     "topic_count": 100,
#     "language": "lb",
#     "model_id": "tm-lb-all-v3.0",
#     "lowercase_token": true,
#     "min_lemmas": 8
#   }
#
# Usage:
#   remake topic-training-all-lb CFG=configs/config-topic-training-tm-lb-all-v3.0.mk

LOGGING_LEVEL ?= INFO
SHELL ?= /bin/bash

# Input linguistic-processing and lemma-frequency run.
S3_BUCKET_LINGPROC_COMPONENT ?= 130-component-sandbox
RUN_ID_LINGPROC ?= lingproc-pos-spacy_v3.6.0-multilingual_v1-0-3
TOPIC_TRAIN_LEMMAFREQ_SELECTION_LABEL ?= upos-PROPN_NOUN.minlength-2

# Source lingproc content-item files used for eligible text extraction.
S3_BUCKET_LINGPROC ?= 142-processed-data-final
PROCESS_LABEL_LINGPROC ?= lingproc
PROCESS_SUBTYPE_LABEL_LINGPROC ?=
PATH_LINGPROC_BASE ?= $(S3_BUCKET_LINGPROC)/$(PROCESS_LABEL_LINGPROC)$(PROCESS_SUBTYPE_LABEL_LINGPROC)/$(RUN_ID_LINGPROC)

# Newspaper list generation for language-level eligible extraction.
S3_PREFIX_NEWSPAPERS_TO_PROCESS_BUCKET ?= $(S3_BUCKET_LINGPROC)
NEWSPAPER_PREFIX ?= $(PROCESS_LABEL_LINGPROC)$(PROCESS_SUBTYPE_LABEL_LINGPROC)/$(RUN_ID_LINGPROC)/
NEWSPAPER_HAS_PROVIDER ?= 1
NEWSPAPER_FNMATCH_lb ?= BNL/*

# Topic training output.
TOPIC_TRAIN_BUCKET ?= 131-component-staging
TOPIC_TRAIN_FINAL_BUCKET ?= 132-component-final
TOPIC_TRAIN_PREFIX ?= topics-mallet
TOPIC_TRAIN_RUN_ID ?= tm-lb-all-v3.0
TOPIC_TRAIN_LANGS ?= lb

# Luxembourgish model specification.
TOPIC_TRAIN_MODEL_ID ?= tm-lb-all-v3.0
TOPIC_TRAIN_POS_TAGS := NOUN,PROPN
TOPIC_TRAIN_MIN_LEMMA_LENGTH ?= 3
TOPIC_TRAIN_MIN_VOCAB_TOKENS ?= 8
TOPIC_TRAIN_MIN_UNIQUE_LEMMAS ?= 1
TOPIC_TRAIN_LOWERCASE_TOKEN ?= true

# Vocabulary trimming. Adjust these after inspecting Luxembourgish lemmafreq coverage.
TOPIC_TRAIN_VOCAB_MIN_FREQ ?= 9
TOPIC_TRAIN_VOCAB_MAX_FREQ ?= 500000
TOPIC_TRAIN_INCLUDE_VOCAB_DIR ?= resources/include-vocab
TOPIC_TRAIN_EXCLUDE_VOCAB_DIR ?= resources/exclude-vocab
TOPIC_TRAIN_NEGATIVE_DOC_FREQ_MAX ?= 4
# Optional reviewed diagnostics to apply in addition to resources/exclude-vocab/lb.txt.
TOPIC_TRAIN_ADDITIONAL_EXCLUDE_VOCAB_lb += resources/exclude-vocab/tm-lb-all-v3.0-df-exclusion.docfreq-lte-$(TOPIC_TRAIN_NEGATIVE_DOC_FREQ_MAX).txt

# Eligible-text and sampling defaults.
TOPIC_TRAIN_MAX_TOKENS ?= 100000
TOPIC_TRAIN_INCLUDE_TITLES ?= true
TOPIC_TRAIN_SAMPLE_SIZE ?= 1000000
TOPIC_TRAIN_SAMPLE_SEED ?= 42
TOPIC_TRAIN_SAMPLE_STRATA ?= newspaper,decade
TOPIC_TRAIN_SAMPLE_MIN_PER_STRATUM ?= 0

# MALLET binary (version-pinned per training run).
MALLET ?= ./mallet-2.1.0/bin/mallet
TOPIC_TRAIN_MALLET_VERSION ?= 2.1.0

# MALLET training hyperparameters.
MALLET_NUM_TOPICS ?= 100
MALLET_TRAIN_ITERATIONS ?= 2000
MALLET_OPTIMIZE_INTERVAL ?= 5
MALLET_OPTIMIZE_BURN_IN ?= 200
MALLET_SHOW_TOPICS_INTERVAL ?= 50
MALLET_THREADS ?= 8
MALLET_TRAIN_MEMORY ?= 64g
MALLET_STD_MEMORY ?= 16g
MALLET_RANDOM_SEED ?= 42

# Smoke inference only; full inference is handled by the inference cookbook.
MALLET_SMOKE_DOCS ?= 1000
MALLET_SMOKE_INFER_ITERATIONS ?= 100
MALLET_TOPIC_ASSIGNMENT_THRESHOLD ?= 0.02
TOPIC_TRAIN_WORD_THRESHOLD ?= 200
TOPIC_TRAIN_SINGLETON_DOC_FREQ_MAX ?= 4
