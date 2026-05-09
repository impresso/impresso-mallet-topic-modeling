# French MALLET topic-training configuration.
#
# This config mirrors the existing inference model specification pattern:
#   tm-de-all-v2.0.config.json
#   tm-fr-all-v2.0.config.json
#
# French model specification for v3.0:
#   {
#     "uposFilter": ["NOUN", "PROPN"],
#     "topic_count": 100,
#     "language": "fr",
#     "model_id": "tm-fr-all-v3.0",
#     "lowercase_token": true,
#     "min_lemmas": 8
#   }
#
# Usage:
#   remake topic-training-all-fr CFG=configs/config-topic-training-tm-fr-all-v3.0.mk

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

# Topic training output.
TOPIC_TRAIN_BUCKET ?= 130-component-sandbox
TOPIC_TRAIN_FINAL_BUCKET ?= 132-component-final
TOPIC_TRAIN_PREFIX ?= topics-mallet
TOPIC_TRAIN_RUN_ID ?= tm-fr-all-v3.0
TOPIC_TRAIN_LANGS ?= fr

# French model specification.
TOPIC_TRAIN_MODEL_ID ?= tm-fr-all-v3.0
TOPIC_TRAIN_POS_TAGS ?= NOUN,PROPN
TOPIC_TRAIN_MIN_LEMMA_LENGTH ?= 3
TOPIC_TRAIN_MIN_VOCAB_TOKENS ?= 8
TOPIC_TRAIN_MIN_UNIQUE_LEMMAS ?= 1
TOPIC_TRAIN_LOWERCASE_TOKEN ?= true

# Vocabulary trimming. French has millions of articles, so very low-frequency
# lemmas are usually OCR, lemmatization, or table artifacts rather than useful
# topic anchors.
TOPIC_TRAIN_VOCAB_MIN_FREQ ?= 100
TOPIC_TRAIN_VOCAB_MAX_FREQ ?= 50000000
TOPIC_TRAIN_NORMALIZED_PROGRESS_INTERVAL ?= 100000
TOPIC_TRAIN_INCLUDE_VOCAB_DIR ?= resources/include-vocab
TOPIC_TRAIN_EXCLUDE_VOCAB_DIR ?= resources/exclude-vocab
TOPIC_TRAIN_NEGATIVE_DOC_FREQ_MAX ?= 10
TOPIC_TRAIN_ADDITIONAL_EXCLUDE_VOCAB_fr += resources/exclude-vocab/tm-fr-all-v3.0-df-exclusion.docfreq-lte-$(TOPIC_TRAIN_NEGATIVE_DOC_FREQ_MAX).txt

# Eligible-text and sampling defaults.
TOPIC_TRAIN_MAX_TOKENS ?= 4500
TOPIC_TRAIN_INCLUDE_TITLES ?= true
TOPIC_TRAIN_SAMPLE_SIZE ?= 2000000
TOPIC_TRAIN_SAMPLE_SEED ?= 42
TOPIC_TRAIN_SAMPLE_STRATA ?= newspaper,decade
TOPIC_TRAIN_SAMPLE_MIN_PER_STRATUM ?= 0
TOPIC_TRAIN_SAMPLE_MAX_PER_STRATUM ?= 10000

# MALLET binary (version-pinned per training run).
MALLET ?= ./mallet-2.1.0/bin/mallet
TOPIC_TRAIN_MALLET_VERSION ?= 2.1.0

# MALLET training hyperparameters.
MALLET_NUM_TOPICS ?= 100
MALLET_TRAIN_ITERATIONS ?= 2000
MALLET_OPTIMIZE_INTERVAL ?= 10
MALLET_OPTIMIZE_BURN_IN ?= 200
MALLET_THREADS ?= 8
MALLET_TRAIN_MEMORY ?= 96g
MALLET_STD_MEMORY ?= 16g
MALLET_RANDOM_SEED ?= 42

# Smoke inference only; full inference is handled by the inference cookbook.
MALLET_SMOKE_DOCS ?= 1000
MALLET_SMOKE_INFER_ITERATIONS ?= 100
MALLET_TOPIC_ASSIGNMENT_THRESHOLD ?= 0.02
TOPIC_TRAIN_WORD_THRESHOLD ?= 200
TOPIC_TRAIN_OUTPUT_DOC_TOPICS ?= false
TOPIC_TRAIN_SINGLETON_DOC_FREQ_MAX ?= 10
