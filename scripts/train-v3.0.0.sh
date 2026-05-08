#!/usr/bin/env bash
# train-v3.0.0.sh
#
# Runs the full training pipeline (vocab + eligible + sample + train + describe
# + smoke-infer) for all four v3.0.0 language configs, one language at a time.
# Make stamps skip already-completed steps, so eligible texts are not re-extracted
# if prepare-v3.0.0.sh has already run successfully.
#
# Usage:
#   ./scripts/train-v3.0.0.sh
#   COLLECTION_JOBS=4 MAX_LOAD=8 ./scripts/train-v3.0.0.sh
#   TOPIC_TRAIN_BUCKET=132-component-final COLLECTION_JOBS=4 MAX_LOAD=8 ./scripts/train-v3.0.0.sh
#
# Environment variables (all optional):
#   TOPIC_TRAIN_BUCKET            S3 bucket for training outputs (default set in config)
#   TOPIC_TRAIN_FORCE_S3_OVERWRITE  Overwrite existing S3 artifacts (TRUE/FALSE, default FALSE)
#   COLLECTION_JOBS               Number of parallel newspaper jobs (default: nproc/2)
#   MAX_LOAD                      System load limit for GNU parallel (default: nproc)
#
# Prerequisites: run prepare-v3.0.0.sh and review/update exclude-vocab files
# before invoking this script.
#
# Logs: logs/train-v3.0.0-<timestamp>.log (combined stdout+stderr)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

COLLECTION_JOBS="${COLLECTION_JOBS:-}"
MAX_LOAD="${MAX_LOAD:-}"
TOPIC_TRAIN_BUCKET="${TOPIC_TRAIN_BUCKET:-}"
TOPIC_TRAIN_FORCE_S3_OVERWRITE="${TOPIC_TRAIN_FORCE_S3_OVERWRITE:-}"

mkdir -p logs
START_TS="$(date +%Y%m%d-%H%M%S)"

echo "========================================"
echo "train-v3.0.0.sh  started: $(date)"
echo "COLLECTION_JOBS=${COLLECTION_JOBS:-<default>}  MAX_LOAD=${MAX_LOAD:-<default>}  TOPIC_TRAIN_BUCKET=${TOPIC_TRAIN_BUCKET:-<from config>}  FORCE_S3_OVERWRITE=${TOPIC_TRAIN_FORCE_S3_OVERWRITE:-FALSE}"
echo "========================================"

run_train() {
    local lang="$1"
    local cfg="$2"
    local extra_vars=()
    [[ -n "$COLLECTION_JOBS"             ]] && extra_vars+=("COLLECTION_JOBS=$COLLECTION_JOBS")
    [[ -n "$MAX_LOAD"                    ]] && extra_vars+=("MAX_LOAD=$MAX_LOAD")
    [[ -n "$TOPIC_TRAIN_BUCKET"          ]] && extra_vars+=("TOPIC_TRAIN_BUCKET=$TOPIC_TRAIN_BUCKET")
    [[ -n "$TOPIC_TRAIN_FORCE_S3_OVERWRITE" ]] && extra_vars+=("TOPIC_TRAIN_FORCE_S3_OVERWRITE=$TOPIC_TRAIN_FORCE_S3_OVERWRITE")
    local logfile="logs/train-v3.0.0-${lang}-${START_TS}.log"

    echo ""
    echo "----------------------------------------"
    echo "[$lang] started:  $(date)"
    echo "[$lang] config:   $cfg"
    echo "[$lang] log:      $logfile"
    echo "----------------------------------------"

    make topic-training-from-sample-"$lang" CFG="$cfg" "${extra_vars[@]}" \
        > >(tee -a "$logfile") 2>&1

    echo "[$lang] finished: $(date)"
}

run_train de configs/config-topic-training-tm-de-all-v3.0.mk
run_train fr configs/config-topic-training-tm-fr-all-v3.0.mk
run_train en configs/config-topic-training-tm-en-all-v3.0.mk
run_train lb configs/config-topic-training-tm-lb-all-v3.0.mk

echo ""
echo "========================================"
echo "train-v3.0.0.sh  finished: $(date)"
echo ""
echo "NEXT STEPS:"
echo "  1. Publish trained models: make topic-training-publish-<lang> CFG=<cfg>"
echo "  2. Verify model IDs in S3 match TOPIC_TRAIN_MODEL_ID in each config."
echo "========================================"
