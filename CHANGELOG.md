# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Training publish now builds an inference-facing bundle under
  `inference/models/tm/`, including a generated model config, slim MALLET `.pipe`,
  inferencer, normalized vocab, character normalization table, and topic
  descriptions.
- Generated inference configs record MALLET runtime version, normalized-lemma
  preprocessing settings, expected linguistic-processing S3 run/path, and sibling
  artifact filenames.
- `scripts/build-inference-bundle-v3.0.0.sh` wraps the post-training inference
  bundle build for one or more languages.

## [3.0.0] - 2026-05-08

### Added

- **Language-independent character normalization pipeline**: new `lib/build_char_normalization_table.py`
  builds an ASCII-folding table from corpus character frequencies; new `lib/normalize_lemma_vocabulary.py`
  applies the table to raw lemma counts and validates the normalized vocabulary.
  Policy: base-letter fold (ä→a, ö→o, ü→u), ligatures (œ→oe, æ→ae, ﬁ→fi, ﬂ→fl),
  long-s (ſ→s), ß→ss; operators and decorative symbols deleted, not converted to
  lexical material.
- **v3.0 training configs** for all four languages (`de`, `en`, `fr`, `lb`) under
  `configs/config-topic-training-tm-{lang}-all-v3.0.mk`. Each config pins the
  MALLET binary version via `MALLET ?= ./mallet-2.1.0/bin/mallet`.
- **v3.0 exclude-vocab placeholder files** under `resources/exclude-vocab/` for all
  languages (to be replaced with corpus-derived word lists after the first eligible run).
- **`scripts/prepare-v3.0.0.sh`**: runs `topic-training-prepare-<lang>` for all four
  languages sequentially, with per-language log files under `logs/`.
- **`scripts/train-v3.0.0.sh`**: runs `topic-training-all-<lang>` for all four
  languages sequentially, with per-language log files under `logs/`.
- **`MALLET_MEMORY` env var support**: all MALLET invocations now set both `MEMORY`
  (read by MALLET 2.0.8) and `MALLET_MEMORY` (read by MALLET 2.1.0).
- **MALLET binary recorded in training metadata**: the `binary` field is written to
  `metadata/{lang}.training.json`, making the exact MALLET version traceable.
- **MALLET 2.1.0** distribution added at `mallet-2.1.0/` (JARs: `mallet-2.1.0.jar`,
  `hppc-0.8.1.jar`).
- **`COLLECTION_JOBS`/`MAX_LOAD` forwarding** in `topic-training-prepare-%` and
  `topic-training-all-%`: the internal GNU parallel load cap is now always inherited by
  sub-make calls to `topic-training-eligible-%`.
- `RELEASE_PROCESS.md` adapted to this repository.

### Changed

- `lib/extract_eligible_texts.py`: logging adapted to template conventions
  (`%`-style lazy formatting, `main(args=None)` signature, `log.info("%s", args)`).
- `lib/build_char_normalization_table.py`: `MANUAL_CHAR_MAP` revised to
  language-independent Latin-ASCII folding policy; spacing diacritics (˝, ᾿) and
  math/operator symbols (₌, ≠, ≮, ≯) now map to `None` (delete) instead of being
  mapped to lexical characters or spaces; added ﬁ/ﬂ ligatures and long-s ſ.
- Training configs renamed from `v2.2` to `v3.0`; old `v2.2` configs removed.
- `fr` config: removed empty `TOPIC_TRAIN_ADDITIONAL_EXCLUDE_VOCAB_fr +=` line
  (non-words list no longer needed with normalization pipeline).
- `AGENT.md`: config filename, `remake` example, and MALLET versioning convention updated.

### Removed

- `configs/config-topic-training-tm-{de,en,fr,lb}-all-v2.2.mk` (superseded by v3.0 configs).
- `topic-training-prepares` and `topic-training-alls` Makefile aggregate targets
  (misleading: each language requires a different config; replaced by `scripts/` wrappers).

## [2.2.0] - 2026-03-01

Initial tracked state on the `version-2.2` branch. Established the core pipeline:
lemma frequency → vocabulary → eligible texts → stratified sample → MALLET training
→ topic descriptions → smoke inference → S3 publish.
