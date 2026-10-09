###############################################################################
# MALLET TOPIC TRAINING TARGETS
#
# Repo-specific model training add-on. The cookbook provides common setup,
# logging, S3 credentials, and path conventions; this file owns the
# topic-training pipeline and artifact contract.
###############################################################################

$(call log.debug, COOKBOOK BEGIN INCLUDE: cookbook-repo-addons/topic_training.mk)

PYTHON ?= python3
OS ?= $(shell uname -s)
JAVA_PACKAGE_APT ?= openjdk-17-jre-headless
JAVA_PACKAGE_BREW ?= openjdk@17
NPROC ?= $(shell getconf _NPROCESSORS_ONLN 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 1)
MAX_LOAD ?= $(NPROC)
COLLECTION_JOBS ?= $(shell v=$$(expr $(NPROC) / 2); [ "$$v" -lt 1 ] && v=1; echo $$v)

TOPIC_TRAIN_BUCKET ?= 130-component-sandbox
TOPIC_TRAIN_FINAL_BUCKET ?= 132-component-final
TOPIC_TRAIN_PREFIX ?= topics-mallet
TOPIC_TRAIN_RUN_ID ?= tm-training-v1
TOPIC_TRAIN_MODEL_ID ?= $(TOPIC_TRAIN_RUN_ID)
TOPIC_TRAIN_LANGS ?= de fr en lb

S3_BUCKET_LINGPROC_COMPONENT ?= UNCONFIGURED-LINGPROC-COMPONENT-BUCKET
RUN_ID_LINGPROC ?= UNCONFIGURED-LINGPROC-RUN-ID
PATH_LINGPROC_BASE ?= UNCONFIGURED-LINGPROC-BASE-PATH

S3_TOPIC_TRAIN_BASE_PATH := s3://$(TOPIC_TRAIN_BUCKET)/$(TOPIC_TRAIN_PREFIX)/$(TOPIC_TRAIN_RUN_ID)
LOCAL_TOPIC_TRAIN_BASE_PATH := $(BUILD_DIR)/$(TOPIC_TRAIN_BUCKET)/$(TOPIC_TRAIN_PREFIX)/$(TOPIC_TRAIN_RUN_ID)

S3_TOPIC_TRAIN_FINAL_BASE_PATH := s3://$(TOPIC_TRAIN_FINAL_BUCKET)/$(TOPIC_TRAIN_PREFIX)/$(TOPIC_TRAIN_RUN_ID)

TOPIC_TRAIN_LEMMAFREQ_SELECTION_LABEL ?= upos-PROPN_NOUN.minlength-2
S3_TOPIC_TRAIN_LEMMAFREQ_BASE ?= s3://$(S3_BUCKET_LINGPROC_COMPONENT)/lemma-freq/$(RUN_ID_LINGPROC)
topic_train_lemmafreq_s3 = $(S3_TOPIC_TRAIN_LEMMAFREQ_BASE)/$(1)/ALL.$(TOPIC_TRAIN_LEMMAFREQ_SELECTION_LABEL).lemmafreq.json.bz2

TOPIC_TRAIN_LINGPROC_S3_PREFIX ?= s3://$(PATH_LINGPROC_BASE)
TOPIC_TRAIN_INPUT_SUFFIX ?= .jsonl.bz2
topic_train_newspaper_fnmatch = $(or $(value NEWSPAPER_FNMATCH_$(1)),$(NEWSPAPER_FNMATCH))
topic_train_newspapers_to_process_file = $(BUILD_DIR)/topic-training-eligible-$(1).newspapers.txt
topic_train_newspapers_to_process_log_file = $(call topic_train_newspapers_to_process_file,$(1)).log.gz

TOPIC_TRAIN_POS_TAGS ?= PROPN,NOUN
TOPIC_TRAIN_MIN_LEMMA_LENGTH ?= 3
TOPIC_TRAIN_VOCAB_MIN_FREQ ?= 400
TOPIC_TRAIN_VOCAB_MAX_FREQ ?= 2000000
TOPIC_TRAIN_NORMALIZED_MIN_ALPHA ?= 3
TOPIC_TRAIN_NORMALIZED_MIN_ALPHA_RATIO ?= 0.75
TOPIC_TRAIN_NORMALIZED_PROGRESS_INTERVAL ?= 0
TOPIC_TRAIN_INCLUDE_VOCAB_DIR ?= resources/include-vocab
TOPIC_TRAIN_EXCLUDE_VOCAB_DIR ?= resources/exclude-vocab
TOPIC_TRAIN_ADDITIONAL_EXCLUDE_VOCAB ?=

TOPIC_TRAIN_MIN_VOCAB_TOKENS ?= 10
TOPIC_TRAIN_MIN_UNIQUE_LEMMAS ?= 5
TOPIC_TRAIN_MAX_TOKENS ?= 1500
TOPIC_TRAIN_INCLUDE_TITLES ?= true

TOPIC_TRAIN_SAMPLE_SIZE ?= 1000000
TOPIC_TRAIN_SAMPLE_SEED ?= 42
TOPIC_TRAIN_SAMPLE_STRATA ?= newspaper,decade
TOPIC_TRAIN_SAMPLE_MIN_PER_STRATUM ?= 0
TOPIC_TRAIN_SAMPLE_MAX_PER_STRATUM ?=

# MALLET binary. Default points to the legacy 2.0.8 distribution committed at mallet/.
# Override in a config with: MALLET ?= ./mallet-X.Y.Z/bin/mallet
# All MALLET invocations set both MEMORY (2.0.8) and MALLET_MEMORY (2.1.0) so
# either version picks up the correct heap size.
MALLET ?= ./mallet/bin/mallet
MALLET_NUM_TOPICS ?= 1000
MALLET_TRAIN_ITERATIONS ?= 1000
MALLET_OPTIMIZE_INTERVAL ?= 10
MALLET_OPTIMIZE_BURN_IN ?= 200
MALLET_SHOW_TOPICS_INTERVAL ?= 50
MALLET_THREADS ?= 8
MALLET_TRAIN_MEMORY ?= 64g
MALLET_STD_MEMORY ?= 16g
MALLET_RANDOM_SEED ?= 42
MALLET_SMOKE_DOCS ?= 1000
MALLET_SMOKE_INFER_ITERATIONS ?= 100
MALLET_TOPIC_ASSIGNMENT_THRESHOLD ?= 0.02
TOPIC_TRAIN_SMOKE_VERBOSE ?= true
TOPIC_TRAIN_WORD_THRESHOLD ?= 200
TOPIC_TRAIN_OUTPUT_DOC_TOPICS ?= true
TOPIC_TRAIN_LABEL_MODEL ?= gpt-5.5
TOPIC_TRAIN_LABEL_TOP_TERMS ?= 50
TOPIC_TRAIN_LABEL_MAX_PROMPT_CHARS ?= 120000
TOPIC_TRAIN_LABEL_MAX_TOPICS_PER_BATCH ?= 0
TOPIC_TRAIN_LABEL_MOCK_RESPONSE ?=
# Upper bound on document frequency for rare-lemma diagnostics.
# Lemmas appearing in *at most* this many documents are reported as singletons/rare.
# Used as --max-document-frequency in analyze_doc_freq.py (not a minimum threshold).
TOPIC_TRAIN_SINGLETON_DOC_FREQ_MAX ?= 4
TOPIC_TRAIN_NEGATIVE_DOC_FREQ_MAX ?= 2
TOPIC_TRAIN_DOC_FREQ_INCLUDE_DOCUMENT_IDS ?= false
TOPIC_TRAIN_DOC_FREQ_PROGRESS_INTERVAL ?= 100000
TOPIC_TRAIN_FORCE_S3_OVERWRITE ?= FALSE
TOPIC_TRAIN_MALLET_VERSION ?= unknown
TOPIC_TRAIN_MALLET_HOME ?= $(patsubst %/bin/mallet,%,$(MALLET))
TOPIC_TRAIN_MALLET_RUNTIME ?= $(notdir $(TOPIC_TRAIN_MALLET_HOME))
TOPIC_TRAIN_MALLET_JAVA_CLASSPATH ?= $(TOPIC_TRAIN_MALLET_HOME)/lib/*
TOPIC_TRAIN_PREPROCESSING_MODE ?= normalized-lemma-vocab-v1
TOPIC_TRAIN_INFERENCE_SCHEMA_VERSION ?= 3.0
TOPIC_TRAIN_INFERENCE_BUNDLE_SUBDIR ?= inference/models/tm
TOPIC_TRAIN_CONFIG_SOURCE ?= $(CONFIG_LOCAL_MAKE)

topic_train_pre_norm_vocab_s3 = $(S3_TOPIC_TRAIN_BASE_PATH)/vocab/$(1).pre-norm.vocab.tsv.bz2
topic_train_pre_norm_vocab_meta_s3 = $(S3_TOPIC_TRAIN_BASE_PATH)/vocab/$(1).pre-norm.vocab.metadata.json
topic_train_char_normalization_s3 = $(S3_TOPIC_TRAIN_BASE_PATH)/vocab/$(1).char-normalization.json
topic_train_char_normalization_report_s3 = $(S3_TOPIC_TRAIN_BASE_PATH)/vocab/$(1).char-normalization.report.json
topic_train_normalized_lemma_vocab_s3 = $(S3_TOPIC_TRAIN_BASE_PATH)/vocab/$(1).normalized-lemma-vocab.json.bz2
topic_train_vocab_s3 = $(S3_TOPIC_TRAIN_BASE_PATH)/vocab/$(1).vocab.tsv.bz2
topic_train_vocab_meta_s3 = $(S3_TOPIC_TRAIN_BASE_PATH)/vocab/$(1).vocab.metadata.json
topic_train_eligible_s3 = $(S3_TOPIC_TRAIN_BASE_PATH)/eligible/$(1).eligible.tsv.bz2
topic_train_eligible_stats_s3 = $(S3_TOPIC_TRAIN_BASE_PATH)/eligible/$(1).stats.json
topic_train_singleton_lemmas_s3 = $(S3_TOPIC_TRAIN_BASE_PATH)/diagnostics/$(TOPIC_TRAIN_MODEL_ID)-df-singletons.docfreq-lte-$(TOPIC_TRAIN_SINGLETON_DOC_FREQ_MAX).tsv.bz2
topic_train_singleton_lemmas_meta_s3 = $(S3_TOPIC_TRAIN_BASE_PATH)/diagnostics/$(TOPIC_TRAIN_MODEL_ID)-df-singletons.docfreq-lte-$(TOPIC_TRAIN_SINGLETON_DOC_FREQ_MAX).metadata.json
topic_train_rare_docfreq_negative_lemmas_s3 = $(S3_TOPIC_TRAIN_BASE_PATH)/diagnostics/$(TOPIC_TRAIN_MODEL_ID)-df-exclusion.docfreq-lte-$(TOPIC_TRAIN_NEGATIVE_DOC_FREQ_MAX).tsv.bz2
topic_train_rare_docfreq_negative_lemmas_meta_s3 = $(S3_TOPIC_TRAIN_BASE_PATH)/diagnostics/$(TOPIC_TRAIN_MODEL_ID)-df-exclusion.docfreq-lte-$(TOPIC_TRAIN_NEGATIVE_DOC_FREQ_MAX).metadata.json
topic_train_singleton_lemmas_word_s3 = $(S3_TOPIC_TRAIN_BASE_PATH)/diagnostics/$(TOPIC_TRAIN_MODEL_ID)-df-singletons.docfreq-lte-$(TOPIC_TRAIN_SINGLETON_DOC_FREQ_MAX).txt
topic_train_rare_docfreq_negative_lemmas_word_s3 = $(S3_TOPIC_TRAIN_BASE_PATH)/diagnostics/$(TOPIC_TRAIN_MODEL_ID)-df-exclusion.docfreq-lte-$(TOPIC_TRAIN_NEGATIVE_DOC_FREQ_MAX).txt
topic_train_singleton_lemmas_word_diagnostics_s3 = $(S3_TOPIC_TRAIN_BASE_PATH)/diagnostics/$(TOPIC_TRAIN_MODEL_ID)-df-singletons.docfreq-lte-$(TOPIC_TRAIN_SINGLETON_DOC_FREQ_MAX).txt.diagnostics.json
topic_train_rare_docfreq_negative_lemmas_word_diagnostics_s3 = $(S3_TOPIC_TRAIN_BASE_PATH)/diagnostics/$(TOPIC_TRAIN_MODEL_ID)-df-exclusion.docfreq-lte-$(TOPIC_TRAIN_NEGATIVE_DOC_FREQ_MAX).txt.diagnostics.json
topic_train_additional_exclude_vocab = $(strip $(TOPIC_TRAIN_ADDITIONAL_EXCLUDE_VOCAB) $(TOPIC_TRAIN_ADDITIONAL_EXCLUDE_VOCAB_$(1)))
topic_train_exclude_vocab_args = $(foreach file,$(wildcard $(TOPIC_TRAIN_EXCLUDE_VOCAB_DIR)/$(1).txt) $(call topic_train_additional_exclude_vocab,$(1)),--exclude-vocab $(file))
topic_train_sample_s3 = $(S3_TOPIC_TRAIN_BASE_PATH)/sample/sample.tsv.bz2
topic_train_sample_manifest_s3 = $(S3_TOPIC_TRAIN_BASE_PATH)/sample/sample.manifest.json

topic_train_local_dir = $(LOCAL_TOPIC_TRAIN_BASE_PATH)/$(1)
topic_train_sample_local = $(LOCAL_TOPIC_TRAIN_BASE_PATH)/sample/sample.tsv
topic_train_sample_mallet_local = $(LOCAL_TOPIC_TRAIN_BASE_PATH)/mallet/$(1).sample.mallet
topic_train_model_local = $(LOCAL_TOPIC_TRAIN_BASE_PATH)/models/$(1).model
topic_train_model_log_local = $(LOCAL_TOPIC_TRAIN_BASE_PATH)/models/$(1).model.log
topic_train_inferencer_local = $(LOCAL_TOPIC_TRAIN_BASE_PATH)/models/$(1).inferencer
topic_train_topickeys_local = $(LOCAL_TOPIC_TRAIN_BASE_PATH)/models/$(1).topickeys
topic_train_topicwordweights_local = $(LOCAL_TOPIC_TRAIN_BASE_PATH)/models/$(1).topicwordweights
topic_train_sample_doctopics_local = $(LOCAL_TOPIC_TRAIN_BASE_PATH)/models/$(1).sample.doctopics
topic_train_description_local = $(LOCAL_TOPIC_TRAIN_BASE_PATH)/jsonl/$(1).topic_model_topic_description.jsonl.bz2
topic_train_smoke_sample_local = $(LOCAL_TOPIC_TRAIN_BASE_PATH)/smoke/$(1).sample.tsv
topic_train_smoke_mallet_local = $(LOCAL_TOPIC_TRAIN_BASE_PATH)/smoke/$(1).sample.mallet
topic_train_smoke_doctopics_local = $(LOCAL_TOPIC_TRAIN_BASE_PATH)/smoke/$(1).doctopics
topic_train_smoke_assignment_plain_local = $(LOCAL_TOPIC_TRAIN_BASE_PATH)/smoke/$(1).topic_assignment.jsonl
topic_train_smoke_assignment_local = $(LOCAL_TOPIC_TRAIN_BASE_PATH)/smoke/$(1).topic_assignment.jsonl.bz2
topic_train_metadata_local = $(LOCAL_TOPIC_TRAIN_BASE_PATH)/metadata/$(1).training.json
topic_train_inference_bundle_local_dir = $(LOCAL_TOPIC_TRAIN_BASE_PATH)/$(TOPIC_TRAIN_INFERENCE_BUNDLE_SUBDIR)
topic_train_inference_java_classes_local_dir = $(LOCAL_TOPIC_TRAIN_BASE_PATH)/java-classes
topic_train_inference_config_local = $(call topic_train_inference_bundle_local_dir)/$(TOPIC_TRAIN_MODEL_ID).config.json
topic_train_inference_pipe_local = $(call topic_train_inference_bundle_local_dir)/$(TOPIC_TRAIN_MODEL_ID).pipe
topic_train_inference_inferencer_local = $(call topic_train_inference_bundle_local_dir)/$(TOPIC_TRAIN_MODEL_ID).inferencer
topic_train_inference_vocab_local = $(call topic_train_inference_bundle_local_dir)/$(TOPIC_TRAIN_MODEL_ID).vocab.tsv.bz2
topic_train_inference_char_normalization_local = $(call topic_train_inference_bundle_local_dir)/$(TOPIC_TRAIN_MODEL_ID).char-normalization.json
topic_train_inference_description_local = $(call topic_train_inference_bundle_local_dir)/$(TOPIC_TRAIN_MODEL_ID).topic_model_topic_description.jsonl.bz2

topic_train_model_s3 = $(S3_TOPIC_TRAIN_BASE_PATH)/models/$(1).model
topic_train_model_log_s3 = $(S3_TOPIC_TRAIN_BASE_PATH)/models/$(1).model.log
topic_train_sample_mallet_s3 = $(S3_TOPIC_TRAIN_BASE_PATH)/mallet/$(1).sample.mallet
topic_train_inferencer_s3 = $(S3_TOPIC_TRAIN_BASE_PATH)/models/$(1).inferencer
topic_train_topickeys_s3 = $(S3_TOPIC_TRAIN_BASE_PATH)/models/$(1).topickeys
topic_train_topicwordweights_s3 = $(S3_TOPIC_TRAIN_BASE_PATH)/models/$(1).topicwordweights
topic_train_sample_doctopics_s3 = $(S3_TOPIC_TRAIN_BASE_PATH)/models/$(1).sample.doctopics
topic_train_description_s3 = $(S3_TOPIC_TRAIN_BASE_PATH)/jsonl/$(1).topic_model_topic_description.jsonl.bz2
topic_train_labels_s3 = $(S3_TOPIC_TRAIN_BASE_PATH)/jsonl/$(1).topic_labels.jsonl.gz
topic_train_smoke_doctopics_s3 = $(S3_TOPIC_TRAIN_BASE_PATH)/smoke/$(1).doctopics
topic_train_smoke_assignment_s3 = $(S3_TOPIC_TRAIN_BASE_PATH)/smoke/$(1).topic_assignment.jsonl.bz2
topic_train_metadata_s3 = $(S3_TOPIC_TRAIN_BASE_PATH)/metadata/$(1).training.json
topic_train_final_vocab_s3 = $(S3_TOPIC_TRAIN_FINAL_BASE_PATH)/vocab/$(1).vocab.tsv.bz2
topic_train_final_vocab_meta_s3 = $(S3_TOPIC_TRAIN_FINAL_BASE_PATH)/vocab/$(1).vocab.metadata.json
topic_train_final_sample_manifest_s3 = $(S3_TOPIC_TRAIN_FINAL_BASE_PATH)/sample/sample.manifest.json
topic_train_final_sample_mallet_s3 = $(S3_TOPIC_TRAIN_FINAL_BASE_PATH)/mallet/$(1).sample.mallet
topic_train_final_model_s3 = $(S3_TOPIC_TRAIN_FINAL_BASE_PATH)/models/$(1).model
topic_train_final_model_log_s3 = $(S3_TOPIC_TRAIN_FINAL_BASE_PATH)/models/$(1).model.log
topic_train_final_inferencer_s3 = $(S3_TOPIC_TRAIN_FINAL_BASE_PATH)/models/$(1).inferencer
topic_train_final_topickeys_s3 = $(S3_TOPIC_TRAIN_FINAL_BASE_PATH)/models/$(1).topickeys
topic_train_final_topicwordweights_s3 = $(S3_TOPIC_TRAIN_FINAL_BASE_PATH)/models/$(1).topicwordweights
topic_train_final_sample_doctopics_s3 = $(S3_TOPIC_TRAIN_FINAL_BASE_PATH)/models/$(1).sample.doctopics
topic_train_final_description_s3 = $(S3_TOPIC_TRAIN_FINAL_BASE_PATH)/jsonl/$(1).topic_model_topic_description.jsonl.bz2
topic_train_final_labels_s3 = $(S3_TOPIC_TRAIN_FINAL_BASE_PATH)/jsonl/$(1).topic_labels.jsonl.gz
topic_train_final_smoke_assignment_s3 = $(S3_TOPIC_TRAIN_FINAL_BASE_PATH)/smoke/$(1).topic_assignment.jsonl.bz2
topic_train_final_metadata_s3 = $(S3_TOPIC_TRAIN_FINAL_BASE_PATH)/metadata/$(1).training.json
topic_train_inference_bundle_s3_dir = $(S3_TOPIC_TRAIN_BASE_PATH)/$(TOPIC_TRAIN_INFERENCE_BUNDLE_SUBDIR)
topic_train_final_inference_bundle_s3_dir = $(S3_TOPIC_TRAIN_FINAL_BASE_PATH)/$(TOPIC_TRAIN_INFERENCE_BUNDLE_SUBDIR)
topic_train_inference_config_s3 = $(call topic_train_inference_bundle_s3_dir)/$(TOPIC_TRAIN_MODEL_ID).config.json
topic_train_inference_pipe_s3 = $(call topic_train_inference_bundle_s3_dir)/$(TOPIC_TRAIN_MODEL_ID).pipe
topic_train_inference_inferencer_s3 = $(call topic_train_inference_bundle_s3_dir)/$(TOPIC_TRAIN_MODEL_ID).inferencer
topic_train_inference_vocab_s3 = $(call topic_train_inference_bundle_s3_dir)/$(TOPIC_TRAIN_MODEL_ID).vocab.tsv.bz2
topic_train_inference_char_normalization_s3 = $(call topic_train_inference_bundle_s3_dir)/$(TOPIC_TRAIN_MODEL_ID).char-normalization.json
topic_train_inference_description_s3 = $(call topic_train_inference_bundle_s3_dir)/$(TOPIC_TRAIN_MODEL_ID).topic_model_topic_description.jsonl.bz2
topic_train_final_inference_config_s3 = $(call topic_train_final_inference_bundle_s3_dir)/$(TOPIC_TRAIN_MODEL_ID).config.json
topic_train_final_inference_pipe_s3 = $(call topic_train_final_inference_bundle_s3_dir)/$(TOPIC_TRAIN_MODEL_ID).pipe
topic_train_final_inference_inferencer_s3 = $(call topic_train_final_inference_bundle_s3_dir)/$(TOPIC_TRAIN_MODEL_ID).inferencer
topic_train_final_inference_vocab_s3 = $(call topic_train_final_inference_bundle_s3_dir)/$(TOPIC_TRAIN_MODEL_ID).vocab.tsv.bz2
topic_train_final_inference_char_normalization_s3 = $(call topic_train_final_inference_bundle_s3_dir)/$(TOPIC_TRAIN_MODEL_ID).char-normalization.json
topic_train_final_inference_description_s3 = $(call topic_train_final_inference_bundle_s3_dir)/$(TOPIC_TRAIN_MODEL_ID).topic_model_topic_description.jsonl.bz2

.NOTINTERMEDIATE: topic-training-import-% topic-training-train-% topic-training-describe-% topic-training-smoke-infer-%
.PHONY: FORCE
FORCE:

.PHONY: help-topic-training
help-topic-training:
	@echo "Usage: make <target>-<lang> CFG=configs/<run>.mk"
	@echo "Example: make topic-training-prepare-fr CFG=configs/config-topic-training-tm-fr-iptc-v3.0.mk"
	@echo "Full reviewed cycle: see step-by-step.md (French IPTC example)."
	@echo ""
	@echo "Topic training targets:"
	@echo "  make topic-training-setup"
	@echo "  make topic-training-install-java"
	@echo "  make topic-training-install-spacy-models"
	@echo "  make topic-training-pre-norm-vocab-<lang>"
	@echo "  make topic-training-char-normalization-<lang>"
	@echo "  make topic-training-normalized-lemma-vocab-<lang>"
	@echo "  make topic-training-vocab-<lang>"
	@echo "  make topic-training-vocabs                           # all langs"
	@echo "  make topic-training-pre-norm-vocabs                   # TOPIC_TRAIN_LANGS"
	@echo "  make topic-training-char-normalizations              # TOPIC_TRAIN_LANGS"
	@echo "  make topic-training-normalized-lemma-vocabs           # TOPIC_TRAIN_LANGS"
	@echo "  make topic-training-eligible-newspaper LNG=de NEWSPAPER=BL/AATA"
	@echo "  make topic-training-eligible-<lang>"
	@echo "  make topic-training-eligible-<lang> COLLECTION_JOBS=4 MAX_LOAD=8"
	@echo "  make topic-training-singleton-lemmas-<lang>"
	@echo "  make topic-training-singleton-lemmas-<lang> TOPIC_TRAIN_SINGLETON_DOC_FREQ_MAX=2"
	@echo "  make topic-training-rare-docfreq-negative-lemmas-<lang>"
	@echo "  make topic-training-vocab-<lang> TOPIC_TRAIN_ADDITIONAL_EXCLUDE_VOCAB_<lang>=s3://..."
	@echo "  make topic-training-prepare-<lang>  # vocab + eligible + diagnostics (review output, then rerun vocab with exclusions)"
	@echo "  make topic-training-sample-<lang>"
	@echo "  make topic-training-import-<lang>"
	@echo "  make topic-training-train-<lang>"
	@echo "  make topic-training-describe-<lang>"
	@echo "  make topic-training-label-<lang>"
	@echo "  make topic-training-labels                          # TOPIC_TRAIN_LANGS"
	@echo "  make topic-training-smoke-infer-<lang>"
	@echo "  make topic-training-inference-bundle-<lang>"
	@echo "  make topic-training-inference-pipe-<lang>            # Requires javac; imports sample"
	@echo "  make topic-training-inference-config-<lang>          # Writes local config only"
	@echo "  make topic-training-publish-<lang>"
	@echo "  make topic-training-all-<lang>"
	@echo "  make topic-training-from-sample-<lang>  # sample + train + describe + label + smoke-infer (after prepare)"
	@echo "  make check-topic-training-mallet"
	@echo ""
	@echo "Reviewed cycle (pass the same CFG to each command):"
	@echo "  prepare -> review exclusions -> rebuild vocab AND eligible if changed"
	@echo "  sample -> train (includes import) -> describe -> label -> smoke-infer"
	@echo "  inference-bundle -> inspect -> publish"
	@echo "  from-sample combines sample through smoke-infer after preparation."
	@echo "  all combines vocab through smoke-infer; it does not publish or run diagnostics."
	@echo "  Bundle creation uploads to training S3; publish rebuilds it and copies to final S3."
	@echo "  Choose a distinct TOPIC_TRAIN_FINAL_BUCKET for publication; avoid copying onto the same paths."
	@echo "  Targets use FORCE; existing S3 outputs normally error unless overwrite is TRUE."
	@echo "  Import reuses a nonempty local MALLET sample and skips an existing S3 copy."
	@echo "  Use a new run/model ID for a changed sample to avoid stale imported data."
	@echo "  Delete existing stage outputs before rerunning; keep overwrite protection FALSE."
	@echo "  Before publish, delete an already-uploaded training bundle so it can be recreated."
	@echo ""
	@echo "Key settings (override in CFG or on the command line):"
	@echo "  TOPIC_TRAIN_RUN_ID / TOPIC_TRAIN_MODEL_ID / TOPIC_TRAIN_LANGS"
	@echo "  TOPIC_TRAIN_BUCKET / TOPIC_TRAIN_FINAL_BUCKET / TOPIC_TRAIN_PREFIX"
	@echo "  TOPIC_TRAIN_POS_TAGS / TOPIC_TRAIN_LEMMAFREQ_SELECTION_LABEL"
	@echo "    The upstream lemma-frequency aggregate must include the selected POS tags."
	@echo "  TOPIC_TRAIN_VOCAB_MIN_FREQ / TOPIC_TRAIN_VOCAB_MAX_FREQ"
	@echo "  TOPIC_TRAIN_ADDITIONAL_EXCLUDE_VOCAB_<lang> / NEWSPAPER_FNMATCH_<lang>"
	@echo "  TOPIC_TRAIN_SINGLETON_DOC_FREQ_MAX / TOPIC_TRAIN_NEGATIVE_DOC_FREQ_MAX"
	@echo "    Diagnostics report document frequency at most these thresholds."
	@echo "  TOPIC_TRAIN_SAMPLE_SIZE / TOPIC_TRAIN_SAMPLE_SEED / TOPIC_TRAIN_SAMPLE_STRATA"
	@echo "  TOPIC_TRAIN_SAMPLE_MIN_PER_STRATUM / TOPIC_TRAIN_SAMPLE_MAX_PER_STRATUM"
	@echo "  MALLET / MALLET_NUM_TOPICS / MALLET_TRAIN_ITERATIONS / MALLET_RANDOM_SEED"
	@echo "  MALLET_THREADS / MALLET_TRAIN_MEMORY / MALLET_STD_MEMORY"
	@echo "  TOPIC_TRAIN_OUTPUT_DOC_TOPICS / MALLET_SMOKE_DOCS / MALLET_SMOKE_INFER_ITERATIONS"
	@echo "  TOPIC_TRAIN_LABEL_MODEL / TOPIC_TRAIN_LABEL_TOP_TERMS"
	@echo "  TOPIC_TRAIN_LABEL_MAX_PROMPT_CHARS / TOPIC_TRAIN_LABEL_MAX_TOPICS_PER_BATCH"
	@echo "    Live labeling requires OPENAI_API_KEY and incurs API costs."
	@echo "    TOPIC_TRAIN_LABEL_MOCK_RESPONSE selects a prepared mock response for testing."
	@echo "  COLLECTION_JOBS / MAX_LOAD                        # GNU parallel extraction"
	@echo "  TOPIC_TRAIN_FORCE_S3_OVERWRITE=FALSE               # TRUE intentionally replaces S3 outputs"
	@echo ""
	@echo "S3 base: $(S3_TOPIC_TRAIN_BASE_PATH)"
	@echo "Final base: $(S3_TOPIC_TRAIN_FINAL_BASE_PATH)"

setup:: topic-training-setup

.PHONY: topic-training-setup topic-training-install-java check-topic-training-mallet topic-training-install-spacy-models
topic-training-setup: topic-training-install-java check-topic-training-mallet topic-training-install-spacy-models $(NEWSPAPERS_TO_PROCESS_FILE)

# Install spaCy language models via direct wheel URLs (PyPI stubs intentionally block plain pip install)
SPACY_MODEL_BASE_URL ?= https://github.com/explosion/spacy-models/releases/download
SPACY_VERSION ?= 3.6.0
topic-training-install-spacy-models:
	$(PYTHON) -c "import de_core_news_md" 2>/dev/null || \
		$(PYTHON) -m pip install "$(SPACY_MODEL_BASE_URL)/de_core_news_md-$(SPACY_VERSION)/de_core_news_md-$(SPACY_VERSION)-py3-none-any.whl"
	$(PYTHON) -c "import fr_core_news_md" 2>/dev/null || \
		$(PYTHON) -m pip install "$(SPACY_MODEL_BASE_URL)/fr_core_news_md-$(SPACY_VERSION)/fr_core_news_md-$(SPACY_VERSION)-py3-none-any.whl"

ifeq ($(OS),Linux)
topic-training-install-java:
	which java >/dev/null || sudo apt-get install -y $(JAVA_PACKAGE_APT)

else ifeq ($(OS),Darwin)
topic-training-install-java:
	which java >/dev/null || brew install $(JAVA_PACKAGE_BREW)
	if brew --prefix $(JAVA_PACKAGE_BREW) >/dev/null 2>&1; then \
		echo "JAVA_HOME=$$(brew --prefix $(JAVA_PACKAGE_BREW))" > .env_java; \
		echo 'PATH=$$JAVA_HOME/bin:$$PATH' >> .env_java; \
	fi

else
topic-training-install-java:
	which java >/dev/null
endif

check-topic-training-mallet:
	@set +e; set +o pipefail; \
	test -x "$(MALLET)" || { echo "MALLET executable not found or not executable: $(MALLET)"; exit 1; }; \
	java -version >/dev/null 2>&1 || { echo "Java not found or not working"; exit 1; }; \
	$(MALLET) train-topics --help >/dev/null 2>&1; status=$$?; \
	test $$status -eq 0 || test $$status -eq 255 || \
	{ echo "MALLET train-topics smoke check failed with exit $$status"; exit $$status; }

topic-training-pre-norm-vocab-%: FORCE
	@mkdir -p $(LOCAL_TOPIC_TRAIN_BASE_PATH)/logs
	$(PYTHON) lib/topic_vocab.py \
		--lemmafreq $(call topic_train_lemmafreq_s3,$*) \
		--language $* \
		--min-frequency $(TOPIC_TRAIN_VOCAB_MIN_FREQ) \
		--max-frequency $(TOPIC_TRAIN_VOCAB_MAX_FREQ) \
		--min-length $(TOPIC_TRAIN_MIN_LEMMA_LENGTH) \
		$(if $(wildcard $(TOPIC_TRAIN_INCLUDE_VOCAB_DIR)/$*.txt),--include-vocab $(TOPIC_TRAIN_INCLUDE_VOCAB_DIR)/$*.txt,) \
		$(call topic_train_exclude_vocab_args,$*) \
		--output $(call topic_train_pre_norm_vocab_s3,$*) \
		--metadata-output $(call topic_train_pre_norm_vocab_meta_s3,$*) \
		--run-id $(TOPIC_TRAIN_RUN_ID) \
		--force-s3-overwrite $(TOPIC_TRAIN_FORCE_S3_OVERWRITE)

topic-training-char-normalization-%: FORCE
	$(PYTHON) lib/build_char_normalization_table.py \
		$(call topic_train_lemmafreq_s3,$*) \
		$(call topic_train_char_normalization_s3,$*) \
		--report-json $(call topic_train_char_normalization_report_s3,$*) \
		--force-s3-overwrite $(TOPIC_TRAIN_FORCE_S3_OVERWRITE)

topic-training-normalized-lemma-vocab-%: FORCE
	$(MAKE) topic-training-char-normalization-$*
	$(PYTHON) lib/normalize_lemma_vocabulary.py \
		$(call topic_train_lemmafreq_s3,$*) \
		$(call topic_train_char_normalization_s3,$*) \
		$(call topic_train_normalized_lemma_vocab_s3,$*) \
		--min-alpha $(TOPIC_TRAIN_NORMALIZED_MIN_ALPHA) \
		--min-alpha-ratio $(TOPIC_TRAIN_NORMALIZED_MIN_ALPHA_RATIO) \
		--progress-interval $(TOPIC_TRAIN_NORMALIZED_PROGRESS_INTERVAL) \
		--force-s3-overwrite $(TOPIC_TRAIN_FORCE_S3_OVERWRITE)

topic-training-vocab-%: FORCE
	@mkdir -p $(LOCAL_TOPIC_TRAIN_BASE_PATH)/logs
	$(MAKE) topic-training-pre-norm-vocab-$*
	$(MAKE) topic-training-normalized-lemma-vocab-$*
	$(PYTHON) lib/topic_vocab.py \
		--lemmafreq $(call topic_train_normalized_lemma_vocab_s3,$*) \
		--freqs-key normalized_freqs \
		--language $* \
		--min-frequency $(TOPIC_TRAIN_VOCAB_MIN_FREQ) \
		--max-frequency $(TOPIC_TRAIN_VOCAB_MAX_FREQ) \
		--min-length $(TOPIC_TRAIN_MIN_LEMMA_LENGTH) \
		$(if $(wildcard $(TOPIC_TRAIN_INCLUDE_VOCAB_DIR)/$*.txt),--include-vocab $(TOPIC_TRAIN_INCLUDE_VOCAB_DIR)/$*.txt,) \
		$(call topic_train_exclude_vocab_args,$*) \
		--output $(call topic_train_vocab_s3,$*) \
		--metadata-output $(call topic_train_vocab_meta_s3,$*) \
		--run-id $(TOPIC_TRAIN_RUN_ID) \
		--force-s3-overwrite $(TOPIC_TRAIN_FORCE_S3_OVERWRITE)

topic-training-pre-norm-vocabs: $(foreach lang,$(TOPIC_TRAIN_LANGS),topic-training-pre-norm-vocab-$(lang))
topic-training-char-normalizations: $(foreach lang,$(TOPIC_TRAIN_LANGS),topic-training-char-normalization-$(lang))
topic-training-normalized-lemma-vocabs: $(foreach lang,$(TOPIC_TRAIN_LANGS),topic-training-normalized-lemma-vocab-$(lang))
topic-training-vocabs: $(foreach lang,$(TOPIC_TRAIN_LANGS),topic-training-vocab-$(lang))

.PHONY: topic-training-eligible-newspaper
topic-training-eligible-newspaper:
	@test -n "$(LNG)" || (echo "LNG is required"; exit 2)
	@test -n "$(NEWSPAPER)" || (echo "NEWSPAPER is required"; exit 2)
	$(PYTHON) lib/extract_eligible_texts.py \
		--s3-prefix $(TOPIC_TRAIN_LINGPROC_S3_PREFIX)/$(NEWSPAPER) \
		--input-suffix $(TOPIC_TRAIN_INPUT_SUFFIX) \
		--vocab $(call topic_train_vocab_s3,$(LNG)) \
		--char-normalization $(call topic_train_char_normalization_s3,$(LNG)) \
		--language $(LNG) \
		--pos-tags $(TOPIC_TRAIN_POS_TAGS) \
		--min-lemma-length $(TOPIC_TRAIN_MIN_LEMMA_LENGTH) \
		--min-vocab-tokens $(TOPIC_TRAIN_MIN_VOCAB_TOKENS) \
		--min-unique-lemmas $(TOPIC_TRAIN_MIN_UNIQUE_LEMMAS) \
		--max-tokens $(TOPIC_TRAIN_MAX_TOKENS) \
		$(if $(filter true,$(TOPIC_TRAIN_INCLUDE_TITLES)),--include-titles,--no-include-titles) \
		--output $(call topic_train_eligible_s3,$(NEWSPAPER)) \
		--stats-output $(call topic_train_eligible_stats_s3,$(NEWSPAPER)) \
		--run-id $(TOPIC_TRAIN_RUN_ID) \
		--force-s3-overwrite $(TOPIC_TRAIN_FORCE_S3_OVERWRITE)

topic-training-eligible-%: FORCE
	$(MAKE) newspaper-list-target \
		'NEWSPAPERS_TO_PROCESS_FILE=$(call topic_train_newspapers_to_process_file,$*)' \
		'NEWSPAPERS_TO_PROCESS_LOG_FILE=$(call topic_train_newspapers_to_process_log_file,$*)' \
		'NEWSPAPER_FNMATCH=$(call topic_train_newspaper_fnmatch,$*)'
	@parallel --version | grep -q 'GNU parallel' || { echo "GNU parallel is required for topic-training-eligible"; exit 2; }; \
	tr -s '[:space:]' '\n' < $(call topic_train_newspapers_to_process_file,$*) | \
		parallel --halt soon,fail=1 --line-buffer \
			--jobs $(COLLECTION_JOBS) \
			--load $(MAX_LOAD) \
			$(MAKE) topic-training-eligible-newspaper LNG=$* NEWSPAPER={}

topic-training-singleton-lemmas-%: FORCE
	$(PYTHON) lib/analyze_doc_freq.py \
		--s3-prefix $(S3_TOPIC_TRAIN_BASE_PATH)/eligible/ \
		--input-suffix .eligible.tsv.bz2 \
		--max-document-frequency $(TOPIC_TRAIN_SINGLETON_DOC_FREQ_MAX) \
		$(if $(filter true,$(TOPIC_TRAIN_DOC_FREQ_INCLUDE_DOCUMENT_IDS)),--include-document-ids,) \
		--progress-interval $(TOPIC_TRAIN_DOC_FREQ_PROGRESS_INTERVAL) \
		--output $(call topic_train_singleton_lemmas_s3,$*) \
		--word-output $(call topic_train_singleton_lemmas_word_s3,$*) \
		--word-diagnostics-output $(call topic_train_singleton_lemmas_word_diagnostics_s3,$*) \
		--metadata-output $(call topic_train_singleton_lemmas_meta_s3,$*) \
		--force-s3-overwrite $(TOPIC_TRAIN_FORCE_S3_OVERWRITE)
	@echo "Review $(call topic_train_singleton_lemmas_word_s3,$*) and manually update $(TOPIC_TRAIN_EXCLUDE_VOCAB_DIR)/$*.txt if the lemmas should be excluded from future vocab builds."

topic-training-rare-docfreq-negative-lemmas-%: FORCE
	$(PYTHON) lib/analyze_doc_freq.py \
		--s3-prefix $(S3_TOPIC_TRAIN_BASE_PATH)/eligible/ \
		--input-suffix .eligible.tsv.bz2 \
		--max-document-frequency $(TOPIC_TRAIN_NEGATIVE_DOC_FREQ_MAX) \
		$(if $(filter true,$(TOPIC_TRAIN_DOC_FREQ_INCLUDE_DOCUMENT_IDS)),--include-document-ids,) \
		--progress-interval $(TOPIC_TRAIN_DOC_FREQ_PROGRESS_INTERVAL) \
		--output $(call topic_train_rare_docfreq_negative_lemmas_s3,$*) \
		--word-output $(call topic_train_rare_docfreq_negative_lemmas_word_s3,$*) \
		--word-diagnostics-output $(call topic_train_rare_docfreq_negative_lemmas_word_diagnostics_s3,$*) \
		--metadata-output $(call topic_train_rare_docfreq_negative_lemmas_meta_s3,$*) \
		--force-s3-overwrite $(TOPIC_TRAIN_FORCE_S3_OVERWRITE)
	@echo "Review $(call topic_train_rare_docfreq_negative_lemmas_word_s3,$*) and manually update $(TOPIC_TRAIN_EXCLUDE_VOCAB_DIR)/$*.txt if the lemmas should be excluded from future vocab builds."

topic-training-sample-%: FORCE
	$(PYTHON) lib/stratified_sample.py \
		--s3-prefix $(S3_TOPIC_TRAIN_BASE_PATH)/eligible/ \
		--input-suffix .eligible.tsv.bz2 \
		--sample-size $(TOPIC_TRAIN_SAMPLE_SIZE) \
		--seed $(TOPIC_TRAIN_SAMPLE_SEED) \
		--strata $(TOPIC_TRAIN_SAMPLE_STRATA) \
		--min-per-stratum $(TOPIC_TRAIN_SAMPLE_MIN_PER_STRATUM) \
		$(if $(TOPIC_TRAIN_SAMPLE_MAX_PER_STRATUM),--max-per-stratum $(TOPIC_TRAIN_SAMPLE_MAX_PER_STRATUM),) \
		--output $(call topic_train_sample_s3,$*) \
		--manifest-output $(call topic_train_sample_manifest_s3,$*) \
		--run-id $(TOPIC_TRAIN_RUN_ID) \
		--language $* \
		--force-s3-overwrite $(TOPIC_TRAIN_FORCE_S3_OVERWRITE)

topic-training-import-%: FORCE
	@mkdir -p $(LOCAL_TOPIC_TRAIN_BASE_PATH)/sample $(LOCAL_TOPIC_TRAIN_BASE_PATH)/mallet
	@if [ -s "$(call topic_train_sample_mallet_local,$*)" ]; then \
		echo "Using existing local MALLET sample: $(call topic_train_sample_mallet_local,$*)"; \
	else \
		$(PYTHON) lib/copy_uri.py --force-s3-overwrite $(TOPIC_TRAIN_FORCE_S3_OVERWRITE) $(call topic_train_sample_s3,$*) $(call topic_train_sample_local,$*) && \
		MEMORY=$(MALLET_STD_MEMORY) MALLET_MEMORY=$(MALLET_STD_MEMORY) $(MALLET) import-file \
			--input $(call topic_train_sample_local,$*) \
			--output $(call topic_train_sample_mallet_local,$*) \
			--keep-sequence; \
	fi
	$(PYTHON) lib/copy_uri.py --skip-existing --force-s3-overwrite $(TOPIC_TRAIN_FORCE_S3_OVERWRITE) $(call topic_train_sample_mallet_local,$*) $(call topic_train_sample_mallet_s3,$*)

topic-training-train-%: topic-training-import-% FORCE
	@mkdir -p $(LOCAL_TOPIC_TRAIN_BASE_PATH)/models $(LOCAL_TOPIC_TRAIN_BASE_PATH)/metadata
	set -o pipefail; MEMORY=$(MALLET_TRAIN_MEMORY) MALLET_MEMORY=$(MALLET_TRAIN_MEMORY) $(MALLET) train-topics \
		--input $(call topic_train_sample_mallet_local,$*) \
		--output-model $(call topic_train_model_local,$*) \
		--inferencer-filename $(call topic_train_inferencer_local,$*) \
		--output-topic-keys $(call topic_train_topickeys_local,$*) \
		--topic-word-weights-file $(call topic_train_topicwordweights_local,$*) $(if $(filter true,$(TOPIC_TRAIN_OUTPUT_DOC_TOPICS)),--output-doc-topics $(call topic_train_sample_doctopics_local,$*),) \
		--num-topics $(MALLET_NUM_TOPICS) \
		--num-iterations $(MALLET_TRAIN_ITERATIONS) \
		--show-topics-interval $(MALLET_SHOW_TOPICS_INTERVAL) \
		--optimize-burn-in $(MALLET_OPTIMIZE_BURN_IN) \
		--optimize-interval $(MALLET_OPTIMIZE_INTERVAL) \
		--num-threads $(MALLET_THREADS) \
		--random-seed $(MALLET_RANDOM_SEED) 2>&1 | tee $(call topic_train_model_log_local,$*)
	$(PYTHON) -c 'import json, datetime; data={"run_id":"$(TOPIC_TRAIN_RUN_ID)","language":"$*","created_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),"mallet":{"binary":"$(MALLET)","num_topics":$(MALLET_NUM_TOPICS),"train_iterations":$(MALLET_TRAIN_ITERATIONS),"optimize_interval":$(MALLET_OPTIMIZE_INTERVAL),"threads":$(MALLET_THREADS),"random_seed":$(MALLET_RANDOM_SEED),"output_doc_topics":"$(TOPIC_TRAIN_OUTPUT_DOC_TOPICS)"},"vocab":"$(call topic_train_vocab_s3,$*)","sample":"$(call topic_train_sample_s3,$*)"}; open("$(call topic_train_metadata_local,$*)","w").write(json.dumps(data, indent=2, sort_keys=True)+"\n")'
	$(PYTHON) lib/copy_uri.py --force-s3-overwrite $(TOPIC_TRAIN_FORCE_S3_OVERWRITE) \
		$(call topic_train_model_local,$*) $(call topic_train_model_s3,$*) \
		$(call topic_train_model_log_local,$*) $(call topic_train_model_log_s3,$*) \
		$(call topic_train_inferencer_local,$*) $(call topic_train_inferencer_s3,$*) \
		$(call topic_train_topickeys_local,$*) $(call topic_train_topickeys_s3,$*) \
		$(call topic_train_topicwordweights_local,$*) $(call topic_train_topicwordweights_s3,$*) $(if $(filter true,$(TOPIC_TRAIN_OUTPUT_DOC_TOPICS)),$(call topic_train_sample_doctopics_local,$*) $(call topic_train_sample_doctopics_s3,$*),) \
		$(call topic_train_metadata_local,$*) $(call topic_train_metadata_s3,$*)

topic-training-describe-%: FORCE
	@mkdir -p $(LOCAL_TOPIC_TRAIN_BASE_PATH)/jsonl $(LOCAL_TOPIC_TRAIN_BASE_PATH)/models
	@if [ ! -s "$(call topic_train_topicwordweights_local,$*)" ]; then \
		$(PYTHON) lib/copy_uri.py --force-s3-overwrite $(TOPIC_TRAIN_FORCE_S3_OVERWRITE) \
			$(call topic_train_topicwordweights_s3,$*) $(call topic_train_topicwordweights_local,$*); \
	fi
	$(PYTHON) lib/mallet2topic_description_json.py \
		-L $* \
		-M $(TOPIC_TRAIN_MODEL_ID) \
		-N $(MALLET_NUM_TOPICS) \
		-W $(TOPIC_TRAIN_WORD_THRESHOLD) \
		-o $(call topic_train_description_local,$*) \
		$(call topic_train_topicwordweights_local,$*)
	$(PYTHON) lib/copy_uri.py --force-s3-overwrite $(TOPIC_TRAIN_FORCE_S3_OVERWRITE) $(call topic_train_description_local,$*) $(call topic_train_description_s3,$*)

topic-training-label-%: FORCE
	$(PYTHON) lib/label_topics.py \
		--input $(call topic_train_description_s3,$*) \
		--output $(call topic_train_labels_s3,$*) \
		--model $(TOPIC_TRAIN_LABEL_MODEL) \
		--top-terms $(TOPIC_TRAIN_LABEL_TOP_TERMS) \
		--max-prompt-chars $(TOPIC_TRAIN_LABEL_MAX_PROMPT_CHARS) \
		--max-topics-per-batch $(TOPIC_TRAIN_LABEL_MAX_TOPICS_PER_BATCH) \
		$(if $(TOPIC_TRAIN_LABEL_MOCK_RESPONSE),--mock-response $(TOPIC_TRAIN_LABEL_MOCK_RESPONSE),) \
		--force-s3-overwrite $(TOPIC_TRAIN_FORCE_S3_OVERWRITE)

topic-training-labels: $(foreach lang,$(TOPIC_TRAIN_LANGS),topic-training-label-$(lang))

topic-training-smoke-infer-%: FORCE
	@mkdir -p $(LOCAL_TOPIC_TRAIN_BASE_PATH)/smoke
	head -n $(MALLET_SMOKE_DOCS) $(call topic_train_sample_local,$*) > $(call topic_train_smoke_sample_local,$*)
	MEMORY=$(MALLET_STD_MEMORY) MALLET_MEMORY=$(MALLET_STD_MEMORY) $(MALLET) import-file \
		--input $(call topic_train_smoke_sample_local,$*) \
		--output $(call topic_train_smoke_mallet_local,$*) \
		--keep-sequence \
		--use-pipe-from $(call topic_train_sample_mallet_local,$*)
	MEMORY=$(MALLET_STD_MEMORY) MALLET_MEMORY=$(MALLET_STD_MEMORY) $(MALLET) infer-topics \
		--inferencer $(call topic_train_inferencer_local,$*) \
		--input $(call topic_train_smoke_mallet_local,$*) \
		--num-iterations $(MALLET_SMOKE_INFER_ITERATIONS) \
		--output-doc-topics $(call topic_train_smoke_doctopics_local,$*) \
		--random-seed $(MALLET_RANDOM_SEED)
	$(PYTHON) lib/copy_uri.py --force-s3-overwrite $(TOPIC_TRAIN_FORCE_S3_OVERWRITE) $(call topic_train_smoke_doctopics_local,$*) $(call topic_train_smoke_doctopics_s3,$*)
	$(PYTHON) lib/mallet2topic_assignment_jsonl.py \
		-L $* \
		-M $(TOPIC_TRAIN_MODEL_ID) \
		-T $(MALLET_TOPIC_ASSIGNMENT_THRESHOLD) \
		$(if $(filter true,$(TOPIC_TRAIN_SMOKE_VERBOSE)),--text-tsv $(call topic_train_smoke_sample_local,$*) --topic-keys $(call topic_train_topickeys_local,$*) --topic-key-word-count 4,) \
		$(call topic_train_smoke_doctopics_local,$*) > $(call topic_train_smoke_assignment_plain_local,$*)
	bzip2 -f $(call topic_train_smoke_assignment_plain_local,$*)
	$(PYTHON) lib/copy_uri.py --force-s3-overwrite $(TOPIC_TRAIN_FORCE_S3_OVERWRITE) $(call topic_train_smoke_assignment_local,$*) $(call topic_train_smoke_assignment_s3,$*)

topic-training-inference-pipe-%: topic-training-import-% FORCE
	@mkdir -p $(call topic_train_inference_bundle_local_dir) $(call topic_train_inference_java_classes_local_dir)
	javac -cp "$(TOPIC_TRAIN_MALLET_JAVA_CLASSPATH)" \
		-d $(call topic_train_inference_java_classes_local_dir) \
		lib/CreateMinimalMalletFile.java
	java -cp "$(call topic_train_inference_java_classes_local_dir):$(TOPIC_TRAIN_MALLET_JAVA_CLASSPATH)" \
		CreateMinimalMalletFile \
		$(call topic_train_sample_mallet_local,$*) \
		$(call topic_train_inference_pipe_local)

topic-training-inference-config-%: FORCE
	@mkdir -p $(call topic_train_inference_bundle_local_dir)
	$(PYTHON) lib/write_inference_model_config.py \
		--output $(call topic_train_inference_config_local) \
		--schema-version $(TOPIC_TRAIN_INFERENCE_SCHEMA_VERSION) \
		--model-id $(TOPIC_TRAIN_MODEL_ID) \
		--language $* \
		--topic-count $(MALLET_NUM_TOPICS) \
		--mallet-version $(TOPIC_TRAIN_MALLET_VERSION) \
		--mallet-runtime $(TOPIC_TRAIN_MALLET_RUNTIME) \
		--preprocessing-mode $(TOPIC_TRAIN_PREPROCESSING_MODE) \
		--upos-filter $(TOPIC_TRAIN_POS_TAGS) \
		--lowercase-token $(TOPIC_TRAIN_LOWERCASE_TOKEN) \
		--min-lemma-length $(TOPIC_TRAIN_MIN_LEMMA_LENGTH) \
		--min-vocab-tokens $(TOPIC_TRAIN_MIN_VOCAB_TOKENS) \
		--min-unique-lemmas $(TOPIC_TRAIN_MIN_UNIQUE_LEMMAS) \
		--include-titles $(TOPIC_TRAIN_INCLUDE_TITLES) \
		--expected-lingproc-run-id $(RUN_ID_LINGPROC) \
		--expected-lingproc-s3-base s3://$(PATH_LINGPROC_BASE) \
		--config-source $(TOPIC_TRAIN_CONFIG_SOURCE) \
		--inferencer $(notdir $(call topic_train_inference_inferencer_local)) \
		--pipe $(notdir $(call topic_train_inference_pipe_local)) \
		--vocab $(notdir $(call topic_train_inference_vocab_local)) \
		--char-normalization $(notdir $(call topic_train_inference_char_normalization_local)) \
		--topic-description $(notdir $(call topic_train_inference_description_local))

topic-training-inference-bundle-%: topic-training-inference-pipe-% topic-training-inference-config-% FORCE
	$(PYTHON) lib/copy_uri.py --force-s3-overwrite $(TOPIC_TRAIN_FORCE_S3_OVERWRITE) \
		$(call topic_train_inferencer_s3,$*) $(call topic_train_inference_inferencer_local) \
		$(call topic_train_vocab_s3,$*) $(call topic_train_inference_vocab_local) \
		$(call topic_train_char_normalization_s3,$*) $(call topic_train_inference_char_normalization_local) \
		$(call topic_train_description_s3,$*) $(call topic_train_inference_description_local)
	$(PYTHON) lib/copy_uri.py --force-s3-overwrite $(TOPIC_TRAIN_FORCE_S3_OVERWRITE) \
		$(call topic_train_inference_config_local) $(call topic_train_inference_config_s3) \
		$(call topic_train_inference_pipe_local) $(call topic_train_inference_pipe_s3) \
		$(call topic_train_inference_inferencer_local) $(call topic_train_inference_inferencer_s3) \
		$(call topic_train_inference_vocab_local) $(call topic_train_inference_vocab_s3) \
		$(call topic_train_inference_char_normalization_local) $(call topic_train_inference_char_normalization_s3) \
		$(call topic_train_inference_description_local) $(call topic_train_inference_description_s3)

topic-training-publish-%: FORCE
	$(MAKE) topic-training-inference-bundle-$*
	$(PYTHON) lib/copy_uri.py --force-s3-overwrite $(TOPIC_TRAIN_FORCE_S3_OVERWRITE) \
		$(call topic_train_vocab_s3,$*) $(call topic_train_final_vocab_s3,$*) \
		$(call topic_train_vocab_meta_s3,$*) $(call topic_train_final_vocab_meta_s3,$*) \
		$(call topic_train_sample_manifest_s3,$*) $(call topic_train_final_sample_manifest_s3,$*) \
		$(call topic_train_sample_mallet_s3,$*) $(call topic_train_final_sample_mallet_s3,$*) \
		$(call topic_train_model_s3,$*) $(call topic_train_final_model_s3,$*) \
		$(call topic_train_model_log_s3,$*) $(call topic_train_final_model_log_s3,$*) \
		$(call topic_train_inferencer_s3,$*) $(call topic_train_final_inferencer_s3,$*) \
		$(call topic_train_topickeys_s3,$*) $(call topic_train_final_topickeys_s3,$*) \
		$(call topic_train_topicwordweights_s3,$*) $(call topic_train_final_topicwordweights_s3,$*) $(if $(filter true,$(TOPIC_TRAIN_OUTPUT_DOC_TOPICS)),$(call topic_train_sample_doctopics_s3,$*) $(call topic_train_final_sample_doctopics_s3,$*),) \
		$(call topic_train_description_s3,$*) $(call topic_train_final_description_s3,$*) \
		$(call topic_train_labels_s3,$*) $(call topic_train_final_labels_s3,$*) \
		$(call topic_train_smoke_assignment_s3,$*) $(call topic_train_final_smoke_assignment_s3,$*) \
		$(call topic_train_metadata_s3,$*) $(call topic_train_final_metadata_s3,$*)
	$(PYTHON) lib/copy_uri.py --force-s3-overwrite $(TOPIC_TRAIN_FORCE_S3_OVERWRITE) \
		$(call topic_train_inference_config_s3) $(call topic_train_final_inference_config_s3) \
		$(call topic_train_inference_pipe_s3) $(call topic_train_final_inference_pipe_s3) \
		$(call topic_train_inference_inferencer_s3) $(call topic_train_final_inference_inferencer_s3) \
		$(call topic_train_inference_vocab_s3) $(call topic_train_final_inference_vocab_s3) \
		$(call topic_train_inference_char_normalization_s3) $(call topic_train_final_inference_char_normalization_s3) \
		$(call topic_train_inference_description_s3) $(call topic_train_final_inference_description_s3)

# topic-training-prepare-% runs the full preparation pipeline up to and including diagnostic
# analysis of rare lemmas. After this target completes, review the word lists produced by
# topic-training-singleton-lemmas-% and topic-training-rare-docfreq-negative-lemmas-%, then
# rerun  make topic-training-vocab-<lang> TOPIC_TRAIN_ADDITIONAL_EXCLUDE_VOCAB_<lang>=<path>
# before proceeding to topic-training-sample-% / topic-training-all-%.
topic-training-prepare-%: FORCE
	$(MAKE) topic-training-vocab-$*
	$(MAKE) topic-training-eligible-$* COLLECTION_JOBS=$(COLLECTION_JOBS) MAX_LOAD=$(MAX_LOAD)
	$(MAKE) topic-training-singleton-lemmas-$*
	$(MAKE) topic-training-rare-docfreq-negative-lemmas-$*

topic-training-all-%: FORCE
	$(MAKE) topic-training-vocab-$*
	$(MAKE) topic-training-eligible-$* COLLECTION_JOBS=$(COLLECTION_JOBS) MAX_LOAD=$(MAX_LOAD)
	$(MAKE) topic-training-sample-$*
	$(MAKE) topic-training-train-$*
	$(MAKE) topic-training-describe-$*
	$(MAKE) topic-training-label-$*
	$(MAKE) topic-training-smoke-infer-$*

# topic-training-from-sample-% runs the training pipeline starting from the sampling step,
# assuming vocab and eligible texts have already been produced by topic-training-prepare-%.
# Use this instead of topic-training-all-% when re-running training after preparation.
topic-training-from-sample-%: FORCE
	$(MAKE) topic-training-sample-$*
	$(MAKE) topic-training-train-$*
	$(MAKE) topic-training-describe-$*
	$(MAKE) topic-training-label-$*
	$(MAKE) topic-training-smoke-infer-$*

$(call log.debug, COOKBOOK END INCLUDE: cookbook-repo-addons/topic_training.mk)
