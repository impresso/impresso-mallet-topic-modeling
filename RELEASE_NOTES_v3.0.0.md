# Release Notes - v3.0.0

**Release Date:** 2026-05-08
**Tag:** v3.0.0
**Branch:** version-2.2
**Status:** Stable

## Overview

v3.0.0 introduces a language-independent character normalization pipeline that
replaces the ad-hoc per-language non-words exclusion lists used in v2.2. Lemma
vocabulary is now built by ASCII-folding observed Unicode characters to a stable
base form before frequency filtering, producing cleaner, more reproducible
vocabularies across all four supported languages (de, en, fr, lb).

All training configurations are updated to v3.0 model IDs. The Makefile gains
aggregate multi-language targets and correct parallelism control for the eligible
extraction step.

## Major Features

### Language-Independent Character Normalization

Two new scripts implement the normalization pipeline:

- **`lib/build_char_normalization_table.py`** — reads the corpus character-frequency
  JSON produced by the lingproc component and emits a `char_normalization` JSON that
  maps each observed non-ASCII character to its ASCII approximation (or `null` to
  delete it). The folding policy is:

  | Class                           | Policy                               |
  | ------------------------------- | ------------------------------------ |
  | Latin diacritics (é, ü, ñ, …)   | strip diacritic → base letter (NFKD) |
  | Ligatures (œ, æ, ﬁ, ﬂ)          | expand (oe, ae, fi, fl)              |
  | Special Latin (ß, ſ)            | ss, s                                |
  | Spacing diacritics (¨, ˝, ᾿, …) | delete                               |
  | Apostrophe variants             | normalize to `'`                     |
  | Dash/hyphen variants            | normalize to `-`                     |
  | Operators/symbols (≠, ₌, ©, …)  | delete                               |

  The design is deliberately language-independent: `ä → a`, not `ä → ae`.
  This is the right trade-off for a multi-language European newspaper corpus.

- **`lib/normalize_lemma_vocabulary.py`** — applies the table to raw lemma counts,
  strips boundary punctuation, deletes internal operators, and validates that the
  normalized core is `[a-z]+` with optional internal hyphens and at least three
  alphabetic characters. Outputs a `normalized_freqs` JSON consumed by the
  vocabulary-building step.

The pipeline replaces the French `tm-fr-all-v2.2-all-non-words.txt` exclusion list,
which is no longer needed with normalization active.

### Multi-Language Aggregate Makefile Targets

```bash
remake topic-training-prepares CFG=configs/config-topic-training-tm-de-all-v3.0.mk
remake topic-training-alls     CFG=configs/config-topic-training-tm-de-all-v3.0.mk
```

Both targets iterate over `TOPIC_TRAIN_LANGS` sequentially. The `eligible` step is
already internally parallel via GNU parallel; running multiple languages
simultaneously would over-commit the machine.

### Parallelism Control Forwarded Through Pipeline

`topic-training-prepare-%` and `topic-training-all-%` now explicitly forward
`COLLECTION_JOBS` and `MAX_LOAD` to the `eligible` sub-make, so the internal
parallel load cap is always inherited:

```bash
remake topic-training-all-de COLLECTION_JOBS=4 MAX_LOAD=8 \
  CFG=configs/config-topic-training-tm-de-all-v3.0.mk
```

## Technical Improvements

- `lib/extract_eligible_texts.py` logging updated to template conventions:
  `%`-style lazy formatting, `main(args=None)` signature for testability.
- `lib/build_char_normalization_table.py` `MANUAL_CHAR_MAP` revised: spacing
  diacritics and math operators now mapped to `None`; ﬁ/ﬂ ligatures and long-s ſ
  added explicitly.
- `fr` config cleaned: spurious empty `TOPIC_TRAIN_ADDITIONAL_EXCLUDE_VOCAB_fr +=`
  line removed.
- `RELEASE_PROCESS.md` added and adapted to this repository.
- `CHANGELOG.md` introduced.

## Breaking Changes

- **Model IDs changed**: `TOPIC_TRAIN_RUN_ID` and `TOPIC_TRAIN_MODEL_ID` are now
  `tm-{lang}-all-v3.0` in all configs. Any downstream inference cookbook referencing
  v2.2 model IDs must be updated.
- **v2.2 configs removed**: `configs/config-topic-training-tm-{de,en,fr,lb}-all-v2.2.mk`
  are deleted. Use the v3.0 equivalents.
- **Vocabulary is not backward-compatible**: the normalization step changes lemma
  forms (e.g., `économie → economie`). A new full eligible/sample/train run is
  required; v2.2 vocab artifacts cannot be reused.

## Migration Guide

1. Replace any reference to `v2.2` config files with the corresponding `v3.0` file.
2. Re-run the full pipeline from scratch:
   ```bash
   remake topic-training-all-de CFG=configs/config-topic-training-tm-de-all-v3.0.mk
   ```
3. Update exclude-vocab files with corpus-derived word lists once the first eligible
   run and diagnostic analysis (`topic-training-rare-docfreq-negative-lemmas-de`) complete.
4. Update any downstream inference cookbook configs to reference the new model IDs.

## Known Issues

- v3.0 `df-exclusion` vocab files for `de` and `en` are currently empty placeholders.
  They will be populated after the first full eligible run and diagnostic analysis.
- The `fr` v3.0 `df-exclusion` file is a copy of the v2.2 `lte-3` list used as a
  starting point; it will be regenerated from the v3.0 eligible run.

## Dependencies

No new dependencies. Requires the same environment as v2.2:

- Python 3.11 (`pipenv install`)
- Java (OpenJDK 17) for MALLET
- `impresso-mallet-lda` (git dependency, installed via Pipfile)
- `smart-open[s3]`, `boto3==1.35.95`

## Links

- Changelog: [CHANGELOG.md](CHANGELOG.md)
- Release Process: [RELEASE_PROCESS.md](RELEASE_PROCESS.md)
