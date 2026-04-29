SHELL := /bin/bash

CONFIG_LOCAL_MAKE ?= config.local.mk
ifdef CFG
  CONFIG_LOCAL_MAKE := $(CFG)
  $(info Overriding CONFIG_LOCAL_MAKE to $(CONFIG_LOCAL_MAKE) from CFG variable)
endif
-include $(CONFIG_LOCAL_MAKE)

BUILD_DIR ?= build.d
LOGGING_LEVEL ?= INFO

$(BUILD_DIR):
	mkdir -p $@


ifndef log.debug
define log.debug
endef
endif

ifndef log.info
define log.info
$(info $(1))
endef
endif

.DEFAULT_GOAL := help

.PHONY: help
help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "Topic training:"
	@echo "  make help-topic-training"
	@echo "  make topic-training-vocab-de"
	@echo "  make topic-training-eligible-newspaper LANG=de NEWSPAPER=BL/AATA"
	@echo "  make topic-training-sample-de"
	@echo "  make topic-training-train-de"
	@echo ""
	@echo "Use remake instead of make when running locally on macOS."

include cookbook/newspaper_list.mk
include cookbook-repo-addons/topic_training.mk
