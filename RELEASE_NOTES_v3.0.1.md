# Release Notes - v3.0.1

**Release Date:** 2026-05-09
**Tag:** v3.0.1
**Branch:** prepare-for-inference
**Status:** Stable

## Overview

v3.0.1 adds the training-side packaging needed by downstream topic-model
inference. Publishing a trained model now creates a flat inference bundle under
`inference/models/tm/` with the MALLET inferencer, a slim MALLET pipe, normalized
vocabulary, character normalization table, topic descriptions, and a generated
self-describing config.

This release keeps the v3.0 model IDs and training configuration family. It is a
packaging and metadata release for the v3.0 topic models, not a new model
specification.

## Major Features

### Inference Bundle Generation

- Added `topic-training-inference-bundle-<lang>` to build and upload the
  inference-facing artifact set for one trained language model.
- `topic-training-publish-<lang>` now builds the inference bundle before copying
  release artifacts to the final S3 location.
- Added `scripts/build-inference-bundle-v3.0.0.sh` to build bundles for one or
  more languages using the v3.0 configs.

### Inference Model Config

- Added generated `*.config.json` metadata for each model bundle.
- The config records model ID, language, topic count, MALLET version/runtime,
  preprocessing parameters, expected linguistic-processing input run, and sibling
  artifact filenames.

### Minimal MALLET Pipe Export

- Added `lib/CreateMinimalMalletFile.java` to derive a compact MALLET file that
  preserves the original training pipe for inference without carrying the full
  training sample.

## Technical Improvements

- Added `TOPIC_TRAIN_MALLET_VERSION` to all v3.0 language configs so generated
  inference metadata records the runtime version explicitly.
- Added Makefile variables for inference bundle paths, schema version,
  preprocessing mode, MALLET classpath, and config source.
- Documented the inference bundle contract in `AGENT.md`.

## Bug Fixes

- None.

## Breaking Changes

- None. Existing v3.0 training model IDs and configs remain unchanged.

## Dependencies

- No new Python dependencies.
- Requires `javac` at bundle-build time to compile the minimal MALLET pipe helper.

## Migration Guide

1. Keep using the existing v3.0 training configs.
2. After a trained language model has the required v3.0 training artifacts, run:
   ```bash
   make topic-training-inference-bundle-de CFG=configs/config-topic-training-tm-de-all-v3.0.mk
   ```
3. Use the generated files under `inference/models/tm/` as the downstream
   inference contract.

## Known Issues

- The bundle builder depends on the trained model artifacts already existing in
  the configured training S3 location.

## Links

- Changelog: [CHANGELOG.md](CHANGELOG.md)
- Release Process: [RELEASE_PROCESS.md](RELEASE_PROCESS.md)
