# GitHub Copilot Instructions for impresso-mallet-topic-modeling

## Project Overview

Topic modeling toolkit for historical newspaper data using MALLET. Processes linguistically annotated (POS-tagged) newspaper content from the Impresso corpus, trains LDA topic models, and converts MALLET outputs to JSON formats. This is a **focused topic modeling repo** that depends on the broader impresso-make-cookbook build system for data pipeline orchestration.

## Core Architecture

### Two-Repository Structure

1. **This repository**: Topic modeling utilities and MALLET integration
   - Python scripts for token extraction, frequency analysis, and MALLET output conversion
   - MALLET binary distribution (in `mallet/`)
   - Cookbook integration via `cookbook/` subdirectory (git submodule)

2. **impresso-make-cookbook** (submodule at `cookbook/`):
   - Make-based build system for distributed NLP processing
   - S3 integration, stamp-based progress tracking
   - Multi-stage pipeline orchestration

### Data Flow

```
S3 (lingproc/*.jsonl.bz2)
  ↓
token_extractor.py → tokens.txt (TSV: doc_id\tlang\ttoken1 token2...)
  ↓
MALLET import-file → corpus.mallet
  ↓
MALLET train-topics → doc-topics.txt, topic-keys.txt, topic-state.gz
  ↓
mallet2topic_*.py → assignments.jsonl, topics.json
  ↓
S3 (topics/*.jsonl.bz2)
```

**Key insight**: Input is POS-tagged lingproc data, not raw text. Extract tokens with `--pos-tags NOUN VERB ADJ` filters.

## Technology Stack

- **Python 3.11** (enforced in Pipfile)
- **MALLET** (Java-based, wrapper script in `mallet/bin/mallet`)
- **Dependencies**:
  - `impresso-mallet-lda` (git dependency from impresso org, installed via Pipfile)
  - `smart-open[s3]` for transparent local/S3 file I/O
  - `boto3==1.35.95` (pinned version for S3 operations)
- **Build System**: GNU Make (via cookbook submodule)

## Critical Conventions

### Python Code Patterns

1. **S3 Integration**: Always use `impresso_cookbook` utilities:
   ```python
   from impresso_cookbook import (
       get_s3_client,           # Configured S3 client
       get_transport_params,    # For smart_open S3 params
       setup_logging,           # Standard logging setup
       get_timestamp            # Consistent timestamping
   )
   ```
   See [token_extractor.py](../lib/token_extractor.py) as the reference implementation.

2. **File I/O Pattern**:
   ```python
   from smart_open import open as smart_open
   
   # Works for both local and S3 paths
   with smart_open(path, transport_params=get_transport_params(path)) as f:
       # Process file
   ```

3. **Lingproc Data Structure** (input format):
   ```json
   {
     "ci_id": "doc-id",
     "sents": [
       {
         "lg": "de",
         "tok": [{"t": "token", "p": "NOUN", "l": "lemma"}]
       }
     ]
   }
   ```
   Always extract from `tok` array using POS tag (`p`) and lemma (`l`) fields.

4. **Output Formats**:
   - **Token extractor**: TSV with `doc_id\tlanguage\tspace-separated-tokens`
   - **Topic assignments**: JSONL with `{"id": "doc-id", "topics": [{"topic_id": 5, "prob": 0.4}]}`

### MALLET Integration

- **Memory Configuration**: Set `export MEMORY=4g` before running MALLET (default: 1g)
- **Common Commands**:
  ```bash
  # Import
  ./mallet/bin/mallet import-file --input tokens.txt --output corpus.mallet
  
  # Train (always use --optimize-interval for better models)
  ./mallet/bin/mallet train-topics --input corpus.mallet --num-topics 50 \
    --optimize-interval 10 --num-threads 4
  ```
- **Key Files**:
  - `mallet/lib/mallet.jar` (2.2 MB) - core library
  - `mallet/lib/mallet-deps.jar` (2.6 MB) - dependencies

### Cookbook/Makefile Integration

When working with the build system (in `cookbook/`):

1. **Path Variables**: End with `_DIR`, `_PATH`, or `_FILE`
2. **User Variables**: Use `?=` assignment (e.g., `PARALLEL_JOBS ?= $(NPROC)`)
3. **Internal Variables**: Use `:=` for immediate expansion
4. **Logging**: Always use `$(call log.info,...)` instead of raw `echo`
5. **Stamp Files**: Use `.d/` extension for progress tracking (e.g., `build.d/stamps/`)

Example from [processing_topics.mk](../cookbook/processing_topics.mk):
```makefile
$(LOCAL_PATH_TOPICS)/%.jsonl.bz2: $(LOCAL_PATH_LINGPROC)/%.jsonl.bz2
    python lib/mallet_topic_inferencer.py \
      --input $(call LocalToS3,$<) \
      --s3-output-path $(call LocalToS3,$@)
```

## Development Workflows

### Environment Setup

```bash
# Install dependencies
pipenv install  # Uses Python 3.11, installs impresso-mallet-lda from git

# Verify MALLET
./mallet/bin/mallet --help

# Configure S3 (if using cookbook)
cp cookbook/dotenv.sample .env
# Edit .env with SE_ACCESS_KEY, SE_SECRET_KEY, SE_HOST_URL
make -C cookbook create-aws-config
```

### Testing Changes

```bash
# Test token extraction (local file)
python lib/token_extractor.py -i test.jsonl --pos-tags NOUN VERB -o tokens.txt

# Test with S3 input (requires .env)
python lib/token_extractor.py -i s3://bucket/file.jsonl.bz2 \
  --pos-tags NOUN --languages de -o output.txt

# Debug logging
python lib/token_extractor.py --log-level DEBUG ...
```

### Common Workflows

**Full Pipeline (Manual)**:
```bash
# 1. Extract tokens from lingproc
python lib/token_extractor.py -i lingproc.jsonl.bz2 --pos-tags NOUN VERB ADJ -o tokens.txt

# 2. Import to MALLET
./mallet/bin/mallet import-file --input tokens.txt --output corpus.mallet

# 3. Train model
./mallet/bin/mallet train-topics --input corpus.mallet --num-topics 50 \
  --num-iterations 1000 --output-doc-topics doc-topics.txt \
  --output-topic-keys topic-keys.txt --optimize-interval 10

# 4. Convert to JSON
python lib/mallet2topic_assignment_jsonl.py -i doc-topics.txt -o assignments.jsonl
python lib/mallet2topic_description_json.py -i topic-keys.txt -o topics.json
```

**Using Make (Automated)**:
```bash
cd cookbook
make newspaper NEWSPAPER=example-1927  # Process single newspaper
make LOGGING_LEVEL=DEBUG  # Enable debug output
```

## Project-Specific Details

### File Organization

- **`lib/*.py`**: Standalone Python utilities (no cookbook dependency)
- **`cookbook/lib/*.py`**: Cookbook-specific utilities (uses `impresso_cookbook`)
- **`mallet/`**: MALLET distribution (committed to repo, not gitignored)
- **`s3_*.py`**: Root-level S3 aggregation scripts (legacy, prefer cookbook patterns)

### Dependencies Management

- **Pinned**: `boto3==1.35.95` (for S3 API stability)
- **Git Dependency**: `impresso-mallet-lda` from `impresso/impresso-mallet-topic-inference` repo
- **Development**: No dev-packages currently defined

### Legacy vs Modern Patterns

**Legacy** (avoid in new code):
- `freq_filter.py`, `sampling.py` - use old-style codecs, no S3 integration
- Direct file paths without smart_open

**Modern** (follow in new code):
- `token_extractor.py` - type hints, impresso_cookbook, smart_open, comprehensive docstrings
- S3-first design with transparent local fallback

## Important Constraints

1. **Never modify MALLET binaries** - committed distribution is tested/verified
2. **Always filter by POS tags** - raw token extraction produces noise for topic modeling
3. **Use lemmas not tokens** - lingproc provides `l` (lemma) field, prefer over `t` (token)
4. **Respect S3 immutability** - use `PROCESSING_QUIT_IF_S3_OUTPUT_EXISTS_OPTION` in makefiles
5. **Maintain backward compatibility** - many scripts have no tests, preserve existing interfaces

## Key Files to Reference

- [token_extractor.py](../lib/token_extractor.py) - Best practice Python/S3 integration example
- [processing_topics.mk](../cookbook/processing_topics.mk) - Makefile processing rules pattern
- [cookbook/.github/copilot-instructions.md](../cookbook/.github/copilot-instructions.md) - Comprehensive cookbook documentation
- [README.md](../README.md) - Full usage examples and API documentation

## Debugging Tips

1. **MALLET errors**: Check Java heap size (`MEMORY` env var), verify input format
2. **S3 access**: Test with `aws s3 ls s3://bucket/` or `make test-aws` in cookbook
3. **Import errors**: Verify `pipenv install` completed, check `impresso-mallet-lda` git dependency
4. **Empty outputs**: Check POS tag filters (`--pos-tags`), language filters (`--languages`)
5. **Makefile issues**: Use `LOGGING_LEVEL=DEBUG`, check `$(call LocalToS3,...)` path conversion

## Contributing

- Follow patterns from `token_extractor.py` for new utilities
- Add type hints and comprehensive docstrings
- Test with both local and S3 inputs
- Update README.md with usage examples
- For cookbook changes, see `cookbook/.github/copilot-instructions.md`
