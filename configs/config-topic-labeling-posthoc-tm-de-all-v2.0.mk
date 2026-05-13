# Post-hoc label generation config for tm-de-all-v2.0
#
# Generates GPT labels for a pre-computed topic-description JSONL already on S3.
# Bypasses the training pipeline; only the label step is run.
#
# Usage:
#   make posthoc-label CFG=configs/config-topic-labeling-posthoc-tm-de-all-v2.0.mk

LOGGING_LEVEL ?= INFO
SHELL ?= /bin/bash

# Source description file and label output location.
POSTHOC_MODEL_ID ?= tm-de-all-v2.0
POSTHOC_S3_BASE ?= s3://141-processed-data-staging/topics/topics-tm-mallet_infer_seed42_v2.0.1-multilingual_v2-0-1
POSTHOC_DESCRIPTION_S3 ?= $(POSTHOC_S3_BASE)/$(POSTHOC_MODEL_ID).topic_model_topic_description.jsonl.bz2
POSTHOC_LABELS_S3 ?= $(POSTHOC_S3_BASE)/$(POSTHOC_MODEL_ID).topic_labels.jsonl.gz

# Label-generation parameters.
TOPIC_TRAIN_LABEL_MODEL ?= gpt-5.5
TOPIC_TRAIN_LABEL_TOP_TERMS ?= 30
TOPIC_TRAIN_LABEL_MAX_PROMPT_CHARS ?= 120000
TOPIC_TRAIN_LABEL_MAX_TOPICS_PER_BATCH ?= 0
TOPIC_TRAIN_LABEL_MOCK_RESPONSE ?=
TOPIC_TRAIN_FORCE_S3_OVERWRITE ?= FALSE

.PHONY: posthoc-label
posthoc-label: FORCE
	$(PYTHON) lib/label_topics.py \
		--input $(POSTHOC_DESCRIPTION_S3) \
		--output $(POSTHOC_LABELS_S3) \
		--model $(TOPIC_TRAIN_LABEL_MODEL) \
		--top-terms $(TOPIC_TRAIN_LABEL_TOP_TERMS) \
		--max-prompt-chars $(TOPIC_TRAIN_LABEL_MAX_PROMPT_CHARS) \
		--max-topics-per-batch $(TOPIC_TRAIN_LABEL_MAX_TOPICS_PER_BATCH) \
		$(if $(TOPIC_TRAIN_LABEL_MOCK_RESPONSE),--mock-response $(TOPIC_TRAIN_LABEL_MOCK_RESPONSE),) \
		--force-s3-overwrite $(TOPIC_TRAIN_FORCE_S3_OVERWRITE)
