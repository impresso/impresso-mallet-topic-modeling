# Topic Labeling with `label_topics.py`

## What it does

`lib/label_topics.py` takes a **topic-description JSONL file** — the output of the
MALLET describe step — and asks an OpenAI model to produce human-readable conceptual
labels for every topic. The result is a **topic-labels JSONL file** where each line
carries a short label, a longer description, a topic-type classification, a confidence
score, a rationale, and a list of representative terms drawn directly from the topic
vocabulary.

## Inputs and outputs

|            | Format                                                                      | Source                     |
| ---------- | --------------------------------------------------------------------------- | -------------------------- |
| **Input**  | `.jsonl.bz2` — one topic per line with `word_probs`, `topic_model`, `lg`, … | MALLET describe step or S3 |
| **Output** | `.jsonl.gz` — one label record per line                                     | local path or S3           |

Both local and `s3://` paths are supported transparently.

## Processing pipeline

```
topic_model_topic_description.jsonl.bz2
        │
        ▼
  read_topics()          – extract top-N terms per topic
        │
        ▼
  make_batches()         – split into prompt-sized chunks
        │  (respects --max-prompt-chars and --max-topics-per-batch)
        ▼
  for each batch:
    build_prompt()       – assemble a structured JSON prompt
        │
        ▼
    call_openai()        – structured-output call with JSON schema enforcement
        │
        ▼
    validate_labels()    – check returned labels against the source vocabulary
        │  retry once with a repair prompt on first failure
        ▼
  write_jsonl()          – append validated labels to output file
```

### Batching

Topics are grouped into batches whose serialised prompt stays below
`--max-prompt-chars` (default 120 000). Already-assigned labels from previous batches
are forwarded in the `already_assigned_labels` field so the model can avoid duplicating
short labels across the whole model.

### Prompt design

The prompt instructs the model to interpret each topic as a cluster of historically
significant newspaper vocabulary and to produce:

- **`label_short`** — a short reusable noun phrase for UI display
- **`label_long`** — a more descriptive phrase with context
- **`topic_type`** — one of a fixed taxonomy (see below)
- **`confidence`** — `high`, `medium`, or `low`
- **`rationale`** — brief justification of the label choice
- **`representative_terms`** — 5–10 terms copied verbatim from the topic's word list

The model is called with OpenAI's **structured output** (JSON schema mode) so the
response is guaranteed to conform to the schema before any Python validation runs.

### Topic-type taxonomy

| Type                    | Meaning                                         |
| ----------------------- | ----------------------------------------------- |
| `theme`                 | General thematic cluster                        |
| `political_news`        | Politics, government, elections                 |
| `local_news`            | Local or regional coverage                      |
| `international_news`    | Foreign affairs                                 |
| `war_military`          | Military events and warfare                     |
| `economy_commerce`      | Trade, finance, industry                        |
| `legal_administrative`  | Law, courts, administration                     |
| `religion`              | Religious life and institutions                 |
| `sports`                | Sport events and clubs                          |
| `culture_entertainment` | Arts, theatre, music, literature                |
| `advertisement`         | Commercial advertising                          |
| `obituary`              | Death notices                                   |
| `family_everyday_life`  | Social and domestic life                        |
| `literary_narrative`    | Serialised fiction or narrative text            |
| `newspaper_genre`       | Recurring newspaper format (e.g. stock tables)  |
| `ocr_noise`             | Broken OCR fragments, not semantically coherent |
| `mixed_uncertain`       | Multiple unrelated domains; no dominant theme   |

### Validation

After every API call `validate_labels()` checks:

1. All expected `topic_id` values are present (no extras, no missing).
2. All required fields are present.
3. `topic_type` and `confidence` are within the allowed sets.
4. `representative_terms` contains 5–10 terms, each of which must appear in the
   source `top_terms` list for that topic. Matching is **normalised** (Unicode NFC,
   whitespace collapse, case-insensitive) so minor formatting differences between the
   source JSONL and the model response are tolerated.

If validation fails the script retries once with a **repair prompt** that explains the
error. If the retry also fails the run aborts.

## CLI reference

```
python lib/label_topics.py \
  --input  <path-or-s3>          # topic description JSONL.BZ2
  --output <path-or-s3>          # label output JSONL.GZ
  --model  gpt-5.5               # OpenAI model (default: gpt-5.5)
  --top-terms 30                 # how many top words to send per topic
  --max-prompt-chars 120000      # approximate batch size cap
  --max-topics-per-batch 0       # explicit batch size; 0 = automatic
  --mock-response <file.json>    # skip API, use saved response (for testing)
  --force-s3-overwrite FALSE     # allow overwriting existing S3 output
  --log-level INFO               # DEBUG shows repr() of unmatched terms
```

## Debugging unmatched terms

Run with `--log-level DEBUG`. For every term that fails validation the script logs:

```
<topic_id>: unmatched term repr='...'  key='...'
  candidate key='...'  source='...'
```

`repr()` exposes invisible characters (non-breaking spaces, combining accents, soft
hyphens) that look identical in plain text but differ as byte sequences.

## Make targets

Post-hoc labeling configs are in `configs/config-topic-labeling-posthoc-*.mk`.
Each defines a single `posthoc-label` target:

```bash
make posthoc-label CFG=configs/config-topic-labeling-posthoc-tm-de-all-v2.0.mk
make posthoc-label CFG=configs/config-topic-labeling-posthoc-tm-fr-all-v2.0.mk
make posthoc-label CFG=configs/config-topic-labeling-posthoc-tm-lb-all-v2.1.mk
```

For models trained through the full pipeline the standard target is:

```bash
make topic-training-label-<lang> CFG=configs/config-topic-training-tm-<lang>-all-v3.0.mk
```
