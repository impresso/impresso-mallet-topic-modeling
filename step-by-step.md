# French IPTC topic-model training

Run these commands from the repository root, in order. This recipe uses
`configs/config-topic-training-tm-fr-iptc-v3.0.mk` and language `fr`.
It trains a MALLET model with VERB, ADJ, NOUN, and PROPN; the config does not
yet add IPTC supervision or map topics to IPTC categories.

## 1. Prepare the environment and inspect the config

Use the project Python 3.11 environment with the dependencies in `Pipfile`:

```bash
pipenv install
pipenv shell
export CFG=configs/config-topic-training-tm-fr-iptc-v3.0.mk
make help-topic-training CFG="$CFG"
```

Use GNU Make 4 or newer, Java and `javac`, GNU parallel, and working S3
credentials. For automated topic labels, configure `OPENAI_API_KEY` in your
environment. Do not commit credentials.

The main Makefile includes `cookbook/aws.mk`, so AWS setup and help are
available directly:

```bash
make help-aws CFG="$CFG"
make aws-setup CFG="$CFG"
```

Before running `aws-setup`, populate the local `.env` with `SE_HOST_URL`,
`SE_ACCESS_KEY`, and `SE_SECRET_KEY`. The target creates missing `.aws/config`
and `.aws/credentials`; `make create-aws-config CFG="$CFG"` is equivalent.
Existing files are retained, so check their settings if the endpoint or
credentials have changed. If the AWS CLI is missing, run
`make install-aws CFG="$CFG"` to install it in the Pipenv environment.

As in
[cookbook/aws.mk](cookbook/aws.mk), every AWS CLI command below explicitly selects
these local files so it uses the configured S3-compatible endpoint and credentials.
Step 2 checks access to this experiment's actual input. The generic
`make test-aws CFG="$CFG"` target checks a fixed legacy S3 prefix, so a failure
there does not necessarily mean these training inputs are inaccessible.

Check the selected MALLET installation:

```bash
make check-topic-training-mallet CFG="$CFG"
java -version
javac -version
parallel --version
```

`make topic-training-setup CFG="$CFG"` is available for setup, but also installs
Java if missing, installs German/French spaCy models, and generates the newspaper
list. It can require network access and system package installation.

The copied config currently specifies 2,000 topics, 500 iterations, 8 threads,
a 96 GB training heap, and a sample of up to 2 million documents, capped at
1,000 per newspaper/decade stratum. Adjust these in the config to fit the machine
and experiment. Training sample document-topic output is disabled.

Outputs use these paths:

| Purpose | Base path |
| --- | --- |
| Training S3 | `s3://130-component-sandbox/topics-mallet/tm-fr-iptc-v3.0/` |
| Local artifacts | `build.d/130-component-sandbox/topics-mallet/tm-fr-iptc-v3.0/` |
| Configured publication S3 | `s3://130-component-sandbox/topics-mallet/tm-fr-iptc-v3.0/` |

Both output buckets currently point to the sandbox, so publication would copy
objects onto their own paths. Step 8 explicitly selects `132-component-final`
as a separate destination. Change that choice if this is still a sandbox test.

## 2. Verify the upstream inputs

The lemma-frequency input is produced by the separate
`/Users/siclemat/pj/2026/impresso/impresso-linguistic-processing-cookbook`
repository, specifically `cookbook-repo-addons/lemmafreq.mk` and
`lib/s3_lemmafreq.py`. This training repository consumes its output.

If the four-POS aggregate does not exist, generate it there before continuing.
Use that repository's Python environment and local `.env`/`.aws/` setup, plus
Rust/Cargo for its streaming counter. The following commands run in a subshell
so the working directory and training `CFG` outside it remain unchanged:

```bash
(
  set -e
  cd /Users/siclemat/pj/2026/impresso/impresso-linguistic-processing-cookbook
  export CFG=configs/config-lingproc-pos-spacy_v3.6.0-multilingual_v1-0-3.mk
  pipenv run make create-aws-config CFG="$CFG"
  pipenv run make setup-lemmafreq CFG="$CFG"

  # Discover newspapers from the existing lingproc outputs for this run.
  pipenv run make newspaper-list-target CFG="$CFG" \
    S3_PREFIX_NEWSPAPERS_TO_PROCESS_BUCKET=142-processed-data-final \
    NEWSPAPER_PREFIX=lingproc/lingproc-pos-spacy_v3.6.0-multilingual_v1-0-3/ \
    NEWSPAPER_FNMATCH='*' \
    NEWSPAPERS_TO_PROCESS_FILE=build.d/iptc-lemmafreq.newspapers.txt

  # Review build.d/iptc-lemmafreq.newspapers.txt before computing the corpus.
  pipenv run make -j4 -l8 compute-lemma-frequencies-fr CFG="$CFG" \
    NEWSPAPERS_TO_PROCESS_FILE=build.d/iptc-lemmafreq.newspapers.txt \
    S3_BUCKET_LINGPROC_COMPONENT=130-component-sandbox \
    LEMMAFREQ_POS_TAGS=VERB,ADJ,NOUN,PROPN LEMMAFREQ_MIN_LENGTH=2

  pipenv run make aggregate-lemma-frequencies-fr CFG="$CFG" \
    NEWSPAPERS_TO_PROCESS_FILE=build.d/iptc-lemmafreq.newspapers.txt \
    S3_BUCKET_LINGPROC_COMPONENT=130-component-sandbox \
    LEMMAFREQ_POS_TAGS=VERB,ADJ,NOUN,PROPN LEMMAFREQ_MIN_LENGTH=2
)
```

The compute target scans all year-level lingproc files for each selected
newspaper, counts French lemmas, and uploads newspaper-level outputs. The
`-j4` option runs up to four newspaper jobs concurrently; `-l8` limits starting
jobs when system load is high. Adjust both to suit the machine and S3 throughput.
This target uses Make parallelism, rather than `COLLECTION_JOBS`. Run aggregation
only after computation finishes successfully; if computation fails, stop the
sequence and resolve the failed jobs before aggregating.
The aggregate target merges matching newspaper files already on S3; it does not
compute missing ones or restrict the merge to the selection list. Check compute
completion and aggregate logs for corpus coverage. Existing newspaper outputs
or active WIP markers can cause compute jobs to skip.

The upstream config defaults to `NEWSPAPER_FNMATCH=BNF/*`. The commands above
instead discover all newspapers with existing lingproc outputs into a dedicated
list; narrow that selection deliberately if needed. This can be a large S3
computation. It reads existing annotations and does not rerun spaCy processing.
`newspaper-list-target` retains an existing list. If the dedicated list already
exists and needs rediscovery, use `refresh-newspaper-list` with the same discovery
arguments; that explicitly replaces the selected list.

The vocabulary source must contain all four selected POS tags. Check that the
following object exists before preparing the run:

```bash
AWS_CONFIG_FILE=.aws/config AWS_SHARED_CREDENTIALS_FILE=.aws/credentials \
  aws s3 ls s3://130-component-sandbox/lemma-freq/lingproc-pos-spacy_v3.6.0-multilingual_v1-0-3/fr/ALL.upos-VERB_ADJ_NOUN_PROPN.minlength-2.lemmafreq.json.bz2
```

This input's availability has not been verified. The upstream filename replaces
commas in `LEMMAFREQ_POS_TAGS` with underscores, preserving tag order, so the
commands above produce exactly the expected selection label. If an existing aggregate uses
a different POS ordering in its filename, set
`TOPIC_TRAIN_LEMMAFREQ_SELECTION_LABEL` to that exact selection label in the
config. A NOUN/PROPN-only aggregate cannot supply the new VERB/ADJ vocabulary.
Creating the upstream aggregate is a separate prerequisite to this training pipeline.

Eligible extraction reads newspaper content under
`s3://142-processed-data-final/lingproc/lingproc-pos-spacy_v3.6.0-multilingual_v1-0-3/`.
Check access and review the newspaper selection (`NEWSPAPER_FNMATCH_fr` can
restrict it). Also review the inherited exclusion list
`resources/exclude-vocab/tm-fr-all-v3.0-df-exclusion.docfreq-lte-10.txt`.
The IPTC config still includes that French v3 list.

## 3. Build vocabulary, eligible texts, and diagnostics

Preview commands, then run preparation:

```bash
make -n topic-training-prepare-fr CFG="$CFG" COLLECTION_JOBS=4 MAX_LOAD=8
make topic-training-prepare-fr CFG="$CFG" COLLECTION_JOBS=4 MAX_LOAD=8
```

Preparation builds the pre-normalization vocabulary, character normalization
table, normalized lemma frequencies, and final vocabulary. It extracts eligible
texts and runs both rare-lemma diagnostics. Outputs include `vocab/`,
`eligible/*.eligible.tsv.bz2`, per-newspaper statistics, and `diagnostics/`.

## 4. Review exclusions and rebuild affected inputs

Download and inspect the diagnostic word lists:

```bash
mkdir -p build.d/iptc-review
AWS_CONFIG_FILE=.aws/config AWS_SHARED_CREDENTIALS_FILE=.aws/credentials \
  aws s3 cp s3://130-component-sandbox/topics-mallet/tm-fr-iptc-v3.0/diagnostics/tm-fr-iptc-v3.0-df-singletons.docfreq-lte-10.txt build.d/iptc-review/singletons.txt
AWS_CONFIG_FILE=.aws/config AWS_SHARED_CREDENTIALS_FILE=.aws/credentials \
  aws s3 cp s3://130-component-sandbox/topics-mallet/tm-fr-iptc-v3.0/diagnostics/tm-fr-iptc-v3.0-df-exclusion.docfreq-lte-10.txt build.d/iptc-review/exclusions.txt
```

Both thresholds are currently 10: these lists report lemmas occurring in at most
10 documents, rather than strictly one. Review the frequency TSVs and metadata
alongside the word lists; do not exclude useful rare terms automatically.

If needed, create a reviewed local exclusion file (one term per line) and append
it to `TOPIC_TRAIN_ADDITIONAL_EXCLUDE_VOCAB_fr` in the config. Keep the inherited
list only if it is appropriate for this experiment.

After changing exclusions or normalization settings, rebuild vocabulary **and
eligible texts** before sampling. First delete the existing outputs of these
stages from this run's S3 `vocab/` and `eligible/` paths, including metadata,
normalization reports, and per-newspaper statistics. Preserve any artifacts you
need before deleting them, and leave other runs untouched. Then rebuild:

```bash
make topic-training-vocab-fr CFG="$CFG"
make topic-training-eligible-fr CFG="$CFG" COLLECTION_JOBS=4 MAX_LOAD=8
```

If nothing changed, continue without rebuilding. To refresh diagnostics after
the rebuild, delete their existing diagnostic outputs first, then run their
individual targets.

## 5. Sample and train

```bash
make topic-training-sample-fr CFG="$CFG"
make topic-training-train-fr CFG="$CFG"
```

Sampling writes `sample/sample.tsv.bz2` and `sample/sample.manifest.json`.
Inspect the manifest's counts and strata. Training automatically imports the
sample into MALLET, then writes and uploads the model, inferencer, topic keys,
topic-word weights, training log, and metadata.

Inspect `models/fr.model.log`, `models/fr.topickeys`, and
`metadata/fr.training.json` under the local artifact base. Check that training
completed and the topics are useful before continuing.

## 6. Describe, label, and smoke-test the model

```bash
make topic-training-describe-fr CFG="$CFG"
make topic-training-label-fr CFG="$CFG"
make topic-training-smoke-infer-fr CFG="$CFG"
```

Description conversion writes `jsonl/fr.topic_model_topic_description.jsonl.bz2`.
Labeling calls the configured OpenAI model and writes
`jsonl/fr.topic_labels.jsonl.gz`; it requires credentials and incurs API costs.
Review the configured `TOPIC_TRAIN_LABEL_MODEL`, top-term count, and batching
settings. `TOPIC_TRAIN_LABEL_MOCK_RESPONSE` supports testing with a prepared
mock response, which should not be used for production labels.

Smoke inference uses 1,000 sampled documents and 100 inference iterations.
Inspect local `smoke/fr.topic_assignment.jsonl.bz2` and `smoke/fr.doctopics`
for plausible assignments. This is a sample check; full-corpus inference runs
in the downstream inference repository.

As an alternative to steps 5–6, after preparation and review, run
`make topic-training-from-sample-fr CFG="$CFG"` once. It performs sampling,
training, description conversion, labeling, and smoke inference in sequence.
Do not run it after the individual steps merely as a completion check.

## 7. Build and inspect the downstream bundle

```bash
make topic-training-inference-bundle-fr CFG="$CFG"
```

This creates the slim MALLET pipe and inference config, assembles the bundle,
and uploads it to the training S3 base. Under `inference/models/tm/`, expect
`tm-fr-iptc-v3.0` files with these suffixes: `.config.json`, `.pipe`,
`.inferencer`, `.vocab.tsv.bz2`, `.char-normalization.json`, and
`.topic_model_topic_description.jsonl.bz2`.

Inspect the local config: language `fr`, 2,000 topics (unless changed), MALLET
2.1.0, all four POS tags, the expected lingproc run, and correct sibling filenames.
Keep all six files together when transferring the bundle downstream.

## 8. Publish after review

Publishing rebuilds and reuploads the bundle before copying the model artifacts
to the selected final bucket. Because step 7 already uploaded that bundle, first
delete the six bundle objects from this run's training S3
`inference/models/tm/` directory. Keep the local bundle for review. Check the
publication destination and delete any existing objects that this publication
will recreate, including the corresponding bundle and model artifacts, before
running the target. Preserve anything needed before deleting it.

```bash
AWS_CONFIG_FILE=.aws/config AWS_SHARED_CREDENTIALS_FILE=.aws/credentials \
  aws s3 ls s3://132-component-final/topics-mallet/tm-fr-iptc-v3.0/ --recursive
make topic-training-publish-fr CFG="$CFG" TOPIC_TRAIN_FINAL_BUCKET=132-component-final
AWS_CONFIG_FILE=.aws/config AWS_SHARED_CREDENTIALS_FILE=.aws/credentials \
  aws s3 ls s3://132-component-final/topics-mallet/tm-fr-iptc-v3.0/inference/models/tm/
```

Alternatively, omit step 7's bundle command and let publishing create the
bundle for the first time, leaving overwrite protection at its default `FALSE`
when both bundle and final destinations are new.
Keep the explicit `TOPIC_TRAIN_FINAL_BUCKET=132-component-final` override when
using this alternative with the current config.

## Reruns and new experiments

Pipeline targets use `FORCE`; most steps execute again. Existing S3 outputs
normally cause an error with `TOPIC_TRAIN_FORCE_S3_OVERWRITE=FALSE`, rather than
being skipped. Before rerunning a stage, delete its existing S3 outputs,
including sidecars and logs that the stage writes. Keep overwrite protection
at its default `FALSE` and restrict deletion to the intended run and stage.

MALLET import is an exception: it reuses a nonempty local `mallet/fr.sample.mallet`
and skips an existing S3 copy. Changing the sample does not invalidate this cache.
For a new sample or preprocessing experiment, prefer a new `TOPIC_TRAIN_RUN_ID`
and `TOPIC_TRAIN_MODEL_ID` in a separate config and rebuild the inputs there.
If reusing a run, deliberately archive the old local imported sample and rebuild
it; also delete its existing S3 artifact before reimporting, since the import
upload uses `--skip-existing`. Do not delete unrelated artifacts.

`topic-training-all-fr` starts again from vocabulary and eligible extraction and
ends at smoke inference. It does not include the diagnostic review, bundle, or
publication steps, so use this recipe for a reviewed full cycle.
