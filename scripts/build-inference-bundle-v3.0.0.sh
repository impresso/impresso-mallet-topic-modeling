#!/usr/bin/env bash
# build-inference-bundle-v3.0.0.sh
#
# Builds the flat inference bundle for v3.0.0 topic models after training has
# produced the sample MALLET file, inferencer, vocabulary, normalization table,
# and topic descriptions.
#
# Usage:
#   ./scripts/build-inference-bundle-v3.0.0.sh
#   ./scripts/build-inference-bundle-v3.0.0.sh lb
#   TOPIC_TRAIN_BUCKET=132-component-final ./scripts/build-inference-bundle-v3.0.0.sh lb
#
# Environment variables (all optional):
#   TOPIC_TRAIN_BUCKET              S3 bucket for training outputs (default set in config)
#   TOPIC_TRAIN_FORCE_S3_OVERWRITE  Overwrite existing S3 artifacts (TRUE/FALSE, default FALSE)
#
# Output:
#   s3://<TOPIC_TRAIN_BUCKET>/topics-mallet/<run-id>/inference/models/tm/

set -euo pipefail

if (( BASH_VERSINFO[0] < 4 )); then
    echo "This script requires Bash 4 or newer. On macOS, install it with: brew install bash" >&2
    exit 2
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

TOPIC_TRAIN_BUCKET="${TOPIC_TRAIN_BUCKET:-}"
TOPIC_TRAIN_FORCE_S3_OVERWRITE="${TOPIC_TRAIN_FORCE_S3_OVERWRITE:-}"

mkdir -p logs
START_TS="$(date +%Y%m%d-%H%M%S)"

declare -A CONFIG_BY_LANG=(
    [de]="configs/config-topic-training-tm-de-all-v3.0.mk"
    [fr]="configs/config-topic-training-tm-fr-all-v3.0.mk"
    [en]="configs/config-topic-training-tm-en-all-v3.0.mk"
    [lb]="configs/config-topic-training-tm-lb-all-v3.0.mk"
)

if [ "$#" -gt 0 ]; then
    LANGS=("$@")
else
    LANGS=(de fr en lb)
fi

echo "========================================"
echo "build-inference-bundle-v3.0.0.sh started: $(date)"
echo "LANGS=${LANGS[*]}  TOPIC_TRAIN_BUCKET=${TOPIC_TRAIN_BUCKET:-<from config>}  FORCE_S3_OVERWRITE=${TOPIC_TRAIN_FORCE_S3_OVERWRITE:-FALSE}"
echo "========================================"

for lang in "${LANGS[@]}"; do
    cfg="${CONFIG_BY_LANG[$lang]:-}"
    if [ -z "$cfg" ]; then
        echo "Unsupported language: $lang" >&2
        echo "Supported languages: de fr en lb" >&2
        exit 2
    fi

    logfile="logs/build-inference-bundle-v3.0.0-${lang}-${START_TS}.log"

    echo ""
    echo "----------------------------------------"
    echo "[$lang] started:  $(date)"
    echo "[$lang] config:   $cfg"
    echo "[$lang] log:      $logfile"
    echo "----------------------------------------"

    extra_vars=()
    [[ -n "$TOPIC_TRAIN_BUCKET" ]] && extra_vars+=("TOPIC_TRAIN_BUCKET=$TOPIC_TRAIN_BUCKET")
    [[ -n "$TOPIC_TRAIN_FORCE_S3_OVERWRITE" ]] && extra_vars+=("TOPIC_TRAIN_FORCE_S3_OVERWRITE=$TOPIC_TRAIN_FORCE_S3_OVERWRITE")

    make topic-training-inference-bundle-"$lang" CFG="$cfg" "${extra_vars[@]}" \
        > >(tee -a "$logfile") 2>&1

    echo "[$lang] finished: $(date)"
done

echo ""
echo "========================================"
echo "build-inference-bundle-v3.0.0.sh finished: $(date)"
echo "========================================"
