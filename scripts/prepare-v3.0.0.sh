#!/usr/bin/env bash
# prepare-v3.0.0.sh
#
# Runs the full preparation pipeline (vocab + eligible + diagnostics) for all
# four v3.0.0 language configs, one language at a time. Each language is
# internally parallel via GNU parallel (COLLECTION_JOBS/MAX_LOAD).
#
# Usage:
#   ./scripts/prepare-v3.0.0.sh
#   COLLECTION_JOBS=4 MAX_LOAD=8 ./scripts/prepare-v3.0.0.sh
#   TOPIC_TRAIN_BUCKET=132-component-final COLLECTION_JOBS=4 MAX_LOAD=8 ./scripts/prepare-v3.0.0.sh
#
# Environment variables (all optional):
#   TOPIC_TRAIN_BUCKET            S3 bucket for training outputs (default set in config)
#   TOPIC_TRAIN_FORCE_S3_OVERWRITE  Overwrite existing S3 artifacts (TRUE/FALSE, default FALSE)
#   COLLECTION_JOBS               Number of parallel newspaper jobs (default: nproc/2)
#   MAX_LOAD                      System load limit for GNU parallel (default: nproc)
#
# After this script completes, review the diagnostic output files:
#   - topic-training-singleton-lemmas-<lang>
#   - topic-training-rare-docfreq-negative-lemmas-<lang>
# Then update the exclude-vocab files in resources/exclude-vocab/ and rerun
# topic-training-vocab-<lang> with TOPIC_TRAIN_ADDITIONAL_EXCLUDE_VOCAB_<lang>=<path>
# before running train-v3.0.0.sh.
#
# Logs: logs/prepare-v3.0.0-<timestamp>.log (combined stdout+stderr)

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
echo "prepare-v3.0.0.sh  started: $(date)"
echo "COLLECTION_JOBS=${COLLECTION_JOBS:-<default>}  MAX_LOAD=${MAX_LOAD:-<default>}  TOPIC_TRAIN_BUCKET=${TOPIC_TRAIN_BUCKET:-<from config>}  FORCE_S3_OVERWRITE=${TOPIC_TRAIN_FORCE_S3_OVERWRITE:-FALSE}"
echo "========================================"

run_prepare() {
    local lang="$1"
    local cfg="$2"
    local extra_vars=()
    [[ -n "$COLLECTION_JOBS"             ]] && extra_vars+=("COLLECTION_JOBS=$COLLECTION_JOBS")
    [[ -n "$MAX_LOAD"                    ]] && extra_vars+=("MAX_LOAD=$MAX_LOAD")
    [[ -n "$TOPIC_TRAIN_BUCKET"          ]] && extra_vars+=("TOPIC_TRAIN_BUCKET=$TOPIC_TRAIN_BUCKET")
    [[ -n "$TOPIC_TRAIN_FORCE_S3_OVERWRITE" ]] && extra_vars+=("TOPIC_TRAIN_FORCE_S3_OVERWRITE=$TOPIC_TRAIN_FORCE_S3_OVERWRITE")
    local logfile="logs/prepare-v3.0.0-${lang}-${START_TS}.log"

    echo ""
    echo "----------------------------------------"
    echo "[$lang] started:  $(date)"
    echo "[$lang] config:   $cfg"
    echo "[$lang] log:      $logfile"
    echo "----------------------------------------"

    make topic-training-prepare-"$lang" CFG="$cfg" "${extra_vars[@]}" \
        > >(tee -a "$logfile") 2>&1

    echo "[$lang] finished: $(date)"
}

run_prepare de configs/config-topic-training-tm-de-all-v3.0.mk
run_prepare fr configs/config-topic-training-tm-fr-all-v3.0.mk
run_prepare en configs/config-topic-training-tm-en-all-v3.0.mk
run_prepare lb configs/config-topic-training-tm-lb-all-v3.0.mk

echo ""
echo "========================================"
echo "prepare-v3.0.0.sh  finished: $(date)"
echo ""
echo "NEXT STEPS:"
echo "  1. Review diagnostic vocab files produced by each language."
echo "  2. Update resources/exclude-vocab/ exclude lists as needed."
echo "  3. Rerun topic-training-vocab-<lang> with updated exclusions."
echo "  4. Then run: ./scripts/train-v3.0.0.sh"
echo "========================================"
