###############################################################################
# Makefile for MALLET Topic Modeling
# Topic modeling toolkit for historical newspaper data using MALLET
###############################################################################

SHELL := /bin/bash

# Load cookbook logging functions first
include cookbook/log.mk

# USER-VARIABLE: CONFIG_LOCAL_MAKE
# Defines the name of the local configuration file to include.
#
# This file is used to override default settings and provide local configuration.
# Never add config.local.mk to the repository!
CONFIG_LOCAL_MAKE ?= config.local.mk
ifdef CFG
  CONFIG_LOCAL_MAKE := $(CFG)
  $(info Overriding CONFIG_LOCAL_MAKE to $(CONFIG_LOCAL_MAKE) from CFG variable)
else
  $(call log.info, CONFIG_LOCAL_MAKE)
endif
# Load local config if it exists (ignore silently if it does not exist)
-include $(CONFIG_LOCAL_MAKE)

# Now we can use the logging function
  $(call log.info, LOGGING_LEVEL)

# Load cookbook help system
include cookbook/help.mk

# USER-VARIABLE: BUILD_DIR
# Build directory for stamps and temporary files
BUILD_DIR ?= build.d
  $(call log.info, BUILD_DIR)

# USER-VARIABLE: LOGGING_LEVEL
# Logging level (INFO, DEBUG, WARNING, ERROR)
LOGGING_LEVEL ?= INFO
  $(call log.info, LOGGING_LEVEL)

$(BUILD_DIR):
	mkdir -p $@

.DEFAULT_GOAL := help

###
# INCLUDES AND CONFIGURATION FILES
#------------------------------------------------------------------------------

# Set shared make options
include cookbook/make_settings.mk

# Load general setup
include cookbook/setup.mk

# Load newspaper list configuration and processing rules
include cookbook/newspaper_list.mk

# Load path conversion utilities
include cookbook/local_to_s3.mk

###
# TOPIC MODELING TARGETS
#------------------------------------------------------------------------------

# Include topic training rules (repo-specific)
include cookbook-repo-addons/topic_training.mk

###
# HELP TARGETS
#------------------------------------------------------------------------------

.PHONY: help
help::
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@echo "Topic Training Targets:"
	@echo "  make help-topic-training        # Show detailed topic training help"
	@echo "  make topic-training-vocab-LANG  # Build vocabulary for language LANG"
	@echo "  make topic-training-eligible-newspaper LANG=de NEWSPAPER=BL/AATA"
	@echo "  make topic-training-sample-LANG # Create stratified sample"
	@echo "  make topic-training-train-LANG  # Train MALLET model"
	@echo ""
	@echo "Note: Use 'remake' instead of 'make' when running locally on macOS."
	@echo ""
