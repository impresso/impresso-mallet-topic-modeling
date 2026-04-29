# AGENT.md

## Purpose

This repository builds MALLET topic models for the Impresso corpus. It owns the
training-side contract: vocabulary creation, eligible-text extraction, sampling,
MALLET import/training, topic-description conversion, smoke inference, and
publishing model artifacts.

It does not own full-corpus topic inference. Downstream inference should consume
the model, inferencer, vocabulary, topic descriptions, sample metadata, and smoke
outputs produced here.

## Repository Layout

- `Makefile`: local orchestration entrypoint. It includes the shared cookbook
  newspaper list helper and `cookbook-repo-addons/topic_training.mk`.
- `cookbook/`: shared Impresso make cookbook, commonly used like a submodule.
  Treat it as a reusable helper layer with its own conventions.
- `cookbook-repo-addons/topic_training.mk`: repo-specific MALLET topic-training
  pipeline and artifact contract.
- `configs/`: run-specific topic-training configs, for example
  `config-topic-training-tm-en-all-v2.2.mk`.
- `lib/`: Python command-line utilities for vocabulary building, eligible-text
  extraction, sampling, MALLET output conversion, and local/S3 copying.
- `resources/negativelemmas/`: language-specific deny lists used by vocabulary
  filtering.
- `mallet/`: vendored MALLET executable and Java jars.
- `PLANNING.md`: current training pipeline design and artifact layout.

## Environment And Tooling

- Python target version is 3.11.
- The preferred local environments are project-local Pipenv `.venv` or a plain
  `venv/` directory.
- Dependencies are declared in `Pipfile`; `impresso-cookbook` is installed
  editable from `./cookbook/lib`.
- MALLET requires Java. The executable is `./mallet/bin/mallet`.
- Many commands require S3 access and local AWS credentials through the cookbook
  setup.

On macOS, do not use the system `/usr/bin/make` for execution. It is too old for
this project. Run make targets with `remake` locally, for example:

```bash
remake help-topic-training
remake topic-training-all-en CFG=configs/config-topic-training-tm-en-all-v2.2.mk
```

Keep `make` as the command name in Makefiles and user-facing documentation. Do
not rename recipes, help text, docs, or `$(MAKE)` calls to `remake`.

## Main Pipeline

The topic-training flow is:

```text
lemmafreq -> vocabulary -> eligible texts -> training sample -> MALLET import
          -> MALLET training -> topic descriptions -> smoke inference -> publish
```

The main targets are:

- `topic-training-vocab-LANG`
- `topic-training-eligible-newspaper LANG=... NEWSPAPER=...`
- `topic-training-eligible-LANG`
- `topic-training-sample-LANG`
- `topic-training-import-LANG`
- `topic-training-train-LANG`
- `topic-training-describe-LANG`
- `topic-training-smoke-infer-LANG`
- `topic-training-publish-LANG`
- `topic-training-all-LANG`

Run-specific values should live in `configs/*.mk` and be passed with `CFG=...`.
Avoid hard-coding run IDs, buckets, language choices, or MALLET hyperparameters
directly into recipes unless the variable contract is also updated.

## Artifact Contract

Training artifacts are written under:

```text
s3://$(TOPIC_TRAIN_BUCKET)/$(TOPIC_TRAIN_PREFIX)/$(TOPIC_TRAIN_RUN_ID)/
```

Local mirrors are derived from:

```text
$(BUILD_DIR)/$(TOPIC_TRAIN_BUCKET)/$(TOPIC_TRAIN_PREFIX)/$(TOPIC_TRAIN_RUN_ID)/
```

The expected artifact families include:

- `vocab/{lang}.vocab.tsv.bz2`
- `eligible/{lang}/{newspaper}.eligible.tsv.bz2`
- `sample/{lang}/sample.tsv.bz2`
- `mallet/{lang}.sample.mallet`
- `models/{lang}.model`
- `models/{lang}.inferencer`
- `models/{lang}.topickeys`
- `models/{lang}.topicwordweights`
- `models/{lang}.sample.doctopics`
- `jsonl/{lang}.topic_model_topic_description.jsonl.bz2`
- `smoke/{lang}.*`
- `metadata/{lang}.training.json`

Do not add full-corpus inference outputs to this repository's training contract.

## Python Conventions

- Keep utilities usable as standalone CLI scripts with `argparse` and
  `raise SystemExit(main())`.
- Prefer streaming I/O; inputs may be large compressed JSONL or TSV files.
- Use `smart_open` for local and S3 paths. Existing scripts include a local-only
  fallback for `.bz2`; preserve that behavior when practical.
- Preserve deterministic behavior for sampling and metadata: explicit seeds,
  stable sorting, and ISO UTC timestamps.
- Metadata sidecars should record enough source paths, criteria, counts, and run
  IDs to reproduce a training stage.
- Keep output formats stable. MALLET import rows are usually:

```text
ci_id<TAB>DUMMY<TAB>lemma1 lemma2 lemma3 ...
```

## Makefile Conventions

- Expose configurable values with `?=`.
- Keep pipeline-specific rules in `cookbook-repo-addons/topic_training.mk`.
- Keep run-specific overrides in `configs/*.mk`.
- Use cookbook helpers for shared behavior where available.
- Preserve the current target names and artifact path helper functions; downstream
  workflows may rely on them.
- Recipe examples in docs/help should say `make`, but local execution on macOS
  should use `remake`.

## Safety Rules

- Do not commit secrets, `.env`, `.aws/`, credentials, or local S3 config.
- Treat `build/`, local compressed inputs, and untracked sample files as user or
  generated state. Do not delete them unless explicitly asked.
- The worktree may contain modified files and local artifacts. Do not revert
  unrelated changes.
- Be careful with `cookbook/`: it is a shared helper/submodule-style dependency.
  Avoid broad edits there unless the task explicitly concerns cookbook behavior.
- Do not run full training, full eligible extraction, or publish targets without
  confirming intent; they can be expensive and require live S3 credentials.

## Validation

Low-risk checks:

```bash
python3 -m py_compile lib/*.py
remake help-topic-training
./mallet/bin/mallet --help
```

More realistic checks should use a small local input or a narrowly scoped target,
for example one language, one newspaper, or smoke inference only. Document any
validation skipped because it requires S3, Java, credentials, or a large training
run.
