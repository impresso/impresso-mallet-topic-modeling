# English MALLET topic-training configuration.
#
# This config mirrors the existing inference model specification pattern:
#   tm-de-all-v2.0.config.json
#   tm-fr-all-v2.0.config.json
#
# Inferred English model specification:
#   {
#     "uposFilter": ["NOUN", "PROPN"],
#     "topic_count": 100,
#     "language": "en",
#     "model_id": "tm-en-all-v2.2",
#     "lowercase_token": false,
#     "min_lemmas": 8
#   }
#
# Usage:
#   remake topic-training-all-en CFG=configs/config-topic-training-tm-en-all-v2.2.mk

LOGGING_LEVEL ?= INFO
SHELL ?= /bin/bash

# Input linguistic-processing and lemma-frequency run.
S3_BUCKET_LINGPROC_COMPONENT ?= 130-component-sandbox
RUN_ID_LINGPROC ?= lingproc-spacy_v3.6.0-multilingual_v1-0-3
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
TOPIC_TRAIN_RUN_ID ?= tm-en-all-v2.2
TOPIC_TRAIN_LANGS ?= en

# English model specification.
TOPIC_TRAIN_MODEL_ID ?= tm-en-all-v2.2
TOPIC_TRAIN_POS_TAGS ?= NOUN,PROPN
TOPIC_TRAIN_MIN_LEMMA_LENGTH ?= 2
TOPIC_TRAIN_MIN_VOCAB_TOKENS ?= 8
TOPIC_TRAIN_MIN_UNIQUE_LEMMAS ?= 1
TOPIC_TRAIN_LOWERCASE_TOKEN ?= false

# Vocabulary trimming. Adjust these after inspecting English lemmafreq coverage.
TOPIC_TRAIN_VOCAB_MIN_FREQ ?= 9
TOPIC_TRAIN_VOCAB_MAX_FREQ ?= 5000
TOPIC_TRAIN_INCLUDE_VOCAB_DIR ?= resources/include-vocab
TOPIC_TRAIN_EXCLUDE_VOCAB_DIR ?= resources/exclude-vocab

# Eligible-text and sampling defaults.
TOPIC_TRAIN_MAX_TOKENS ?= 1500
TOPIC_TRAIN_INCLUDE_TITLES ?= true
TOPIC_TRAIN_SAMPLE_SIZE ?= 1000000
TOPIC_TRAIN_SAMPLE_SEED ?= 42
TOPIC_TRAIN_SAMPLE_STRATA ?= newspaper,decade
TOPIC_TRAIN_SAMPLE_MIN_PER_STRATUM ?= 0

# MALLET training hyperparameters.
MALLET_NUM_TOPICS ?= 100
MALLET_TRAIN_ITERATIONS ?= 1000
MALLET_OPTIMIZE_INTERVAL ?= 10
MALLET_THREADS ?= 8
MALLET_TRAIN_MEMORY ?= 64g
MALLET_STD_MEMORY ?= 16g
MALLET_RANDOM_SEED ?= 42

# Smoke inference only; full inference is handled by the inference cookbook.
MALLET_SMOKE_DOCS ?= 1000
MALLET_SMOKE_INFER_ITERATIONS ?= 100
MALLET_TOPIC_ASSIGNMENT_THRESHOLD ?= 0.02
TOPIC_TRAIN_WORD_THRESHOLD ?= 200
