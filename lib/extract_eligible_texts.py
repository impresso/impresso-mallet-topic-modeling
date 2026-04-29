#!/usr/bin/env python3
"""Extract eligible MALLET training texts from linguistic-processing JSONL."""

import argparse
import logging
try:
    import ujson as json  # type: ignore
except ImportError:
    import json
import re
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from smart_open import open as smart_open  # type: ignore

try:
    from impresso_cookbook import (  # type: ignore
        get_s3_client,
        get_timestamp,
        setup_logging,
        get_transport_params,
    )
except ImportError:
    # Fallback for when impresso_cookbook is not available
    def setup_logging(level: str, log_file: str | None = None, logger=None) -> None:
        logging.basicConfig(
            level=getattr(logging, level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stderr),
                *([] if log_file is None else [logging.FileHandler(log_file)])
            ]
        )
    
    def get_transport_params(path: str) -> dict:
        return {}
    
    def get_s3_client():
        import boto3
        return boto3.client('s3')
    
    def get_timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()

log = logging.getLogger(__name__)


CI_ID_RE = re.compile(r"^(?P<newspaper>.+?)-(?P<year>\d{4})-\d{2}-\d{2}-")


def list_s3(prefix: str, suffix: str) -> list[str]:
    """List S3 objects matching a prefix and suffix."""
    parsed = urlparse(prefix)
    bucket = parsed.netloc
    key_prefix = parsed.path.lstrip("/")
    client = get_s3_client()
    paginator = client.get_paginator("list_objects_v2")
    paths: list[str] = []
    for page in paginator.paginate(Bucket=bucket, Prefix=key_prefix):
        for item in page.get("Contents", []):
            key = item["Key"]
            if key.endswith(suffix):
                paths.append(f"s3://{bucket}/{key}")
    return sorted(paths)


def list_local(prefix: str, suffix: str) -> list[str]:
    root = Path(prefix)
    return sorted(str(path) for path in root.rglob(f"*{suffix}") if path.is_file())


def expand_inputs(inputs: list[str], prefixes: list[str], suffix: str) -> list[str]:
    paths = list(inputs)
    for prefix in prefixes:
        if prefix.startswith("s3://"):
            paths.extend(list_s3(prefix, suffix))
        else:
            paths.extend(list_local(prefix, suffix))
    return sorted(dict.fromkeys(paths))


def load_vocab(path: str) -> set[str]:
    """Load vocabulary from a TSV file (first column only)."""
    log.info(f"Loading vocabulary from {path}")
    vocab: set[str] = set()
    with smart_open(path, "r", encoding="utf-8", transport_params=get_transport_params(path)) as handle:
        for line in handle:
            lemma = line.strip().split("\t", 1)[0]
            if lemma:
                vocab.add(lemma.lower())
    log.info(f"Loaded {len(vocab):,} unique lemmas")
    return vocab


def iter_sentences(doc: dict[str, Any], include_titles: bool) -> Iterable[dict[str, Any]]:
    yield from doc.get("sents", [])
    if include_titles:
        yield from doc.get("tsents", [])


def iter_tokens(sent: dict[str, Any]) -> Iterable[dict[str, Any]]:
    # Get tokens array (try "tok" first, then "tokens")
    tokens = sent.get("tok")
    if tokens is None:
        tokens = sent.get("tokens", [])
    yield from tokens or []


def document_bucket(ci_id: str) -> tuple[str, str]:
    match = CI_ID_RE.match(ci_id)
    if not match:
        return "unknown", "unknown"
    newspaper = match.group("newspaper")
    year = int(match.group("year"))
    return newspaper, f"{year // 10 * 10}s"


def is_s3_path(path: str) -> bool:
    """Check if a path is an S3 URI."""
    return path.startswith("s3://")


def upload_to_s3(local_path: str, s3_path: str) -> None:
    """Upload a local file to S3."""
    log.info(f"Uploading {local_path} to {s3_path}")
    parsed = urlparse(s3_path)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    client = get_s3_client()
    client.upload_file(local_path, bucket, key)
    log.info(f"Successfully uploaded to {s3_path}")


def extract_doc_lemmas(
    doc: dict[str, Any],
    *,
    language: str,
    pos_tags: set[str],
    min_lemma_length: int,
    vocab: set[str],
    include_titles: bool,
) -> list[str]:
    lemmas: list[str] = []
    for sent in iter_sentences(doc, include_titles):
        if sent.get("lg") != language:
            continue
        for token in iter_tokens(sent):
            if token.get("p") not in pos_tags:
                continue
            # Get lemma (try "l" first if non-empty, then fall back to "t")
            lemma_raw = token.get("l") or ""
            if not lemma_raw.strip():
                lemma_raw = token.get("t") or ""
            lemma = lemma_raw.strip().lower()
            if len(lemma) < min_lemma_length:
                continue
            if lemma not in vocab:
                continue
            lemmas.append(lemma)
    return lemmas


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create eligible MALLET TSV rows from lingproc JSONL files."
    )
    parser.add_argument("--input", action="append", default=[], help="Input JSONL.bz2")
    parser.add_argument(
        "--s3-prefix",
        action="append",
        default=[],
        help="S3/local prefix to scan for input JSONL.bz2 files",
    )
    parser.add_argument("--input-suffix", default=".jsonl.bz2")
    parser.add_argument("--vocab", required=True)
    parser.add_argument("--language", required=True)
    parser.add_argument("--pos-tags", default="PROPN,NOUN")
    parser.add_argument("--min-lemma-length", type=int, default=2)
    parser.add_argument("--min-vocab-tokens", type=int, default=10)
    parser.add_argument("--min-unique-lemmas", type=int, default=5)
    parser.add_argument("--max-tokens", type=int, default=1500)
    parser.add_argument("--include-titles", action="store_true", default=True)
    parser.add_argument("--no-include-titles", dest="include_titles", action="store_false")
    parser.add_argument("--output", required=True)
    parser.add_argument("--stats-output", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--log-file",
        help="Write log to FILE",
        metavar="FILE",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: %(default)s)",
    )
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level, args.log_file, logger=log)
    log.info(f"Arguments: {args}")

    inputs = expand_inputs(args.input, args.s3_prefix, args.input_suffix)
    if not inputs:
        log.error("No input files found")
        return 2
    
    log.info(f"Processing {len(inputs)} input file(s)")

    vocab = load_vocab(args.vocab)
    pos_tags = {tag.strip() for tag in args.pos_tags.split(",") if tag.strip()}
    log.info(f"Filtering for POS tags: {sorted(pos_tags)}")
    log.info(f"Language: {args.language}")
    log.info(f"Min lemma length: {args.min_lemma_length}")
    log.info(f"Min vocab tokens: {args.min_vocab_tokens}, Max tokens: {args.max_tokens}")

    stats: Counter[str] = Counter()
    strata: Counter[str] = Counter()

    # Determine output paths (use temp files for S3 destinations)
    output_path = args.output
    stats_output_path = args.stats_output
    output_is_s3 = is_s3_path(args.output)
    stats_is_s3 = is_s3_path(args.stats_output)
    
    temp_output = None
    temp_stats = None
    
    try:
        if output_is_s3:
            temp_output = tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix='.txt')
            output_path = temp_output.name
            log.info(f"Writing output to temporary file {output_path} (will upload to {args.output})")
        else:
            log.info(f"Writing output to {args.output}")
        
        if stats_is_s3:
            temp_stats = tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix='.json')
            stats_output_path = temp_stats.name
            log.info(f"Writing statistics to temporary file {stats_output_path} (will upload to {args.stats_output})")

        with smart_open(output_path, "w", encoding="utf-8", transport_params=get_transport_params(output_path)) as out:
            for path in inputs:
                stats["input_files"] += 1
                log.debug(f"Processing file {stats['input_files']}/{len(inputs)}: {path}")
                with smart_open(path, "r", encoding="utf-8", transport_params=get_transport_params(path)) as handle:
                    for line_number, line in enumerate(handle, 1):
                        stats["input_lines"] += 1
                        try:
                            doc = json.loads(line)
                        except json.JSONDecodeError as e:
                            stats["json_errors"] += 1
                            log.debug(f"JSON decode error at {path}:{line_number}: {e}")
                            continue

                        ci_id = str(doc.get("ci_id") or doc.get("id") or "")
                        if not ci_id:
                            stats["missing_ci_id"] += 1
                            log.debug(f"Missing ci_id at {path}:{line_number}")
                            continue

                        lemmas = extract_doc_lemmas(
                            doc,
                            language=args.language,
                            pos_tags=pos_tags,
                            min_lemma_length=args.min_lemma_length,
                            vocab=vocab,
                            include_titles=args.include_titles,
                        )
                        stats["docs_seen"] += 1
                        stats["accepted_vocab_tokens"] += len(lemmas)

                        if stats["docs_seen"] % 10000 == 0:
                            total_rejected = stats['rejected_too_short'] + stats['rejected_too_few_unique'] + stats['rejected_too_long']
                            log.info(f"Progress: {stats['docs_seen']:,} documents processed, "
                                    f"{stats['docs_written']:,} written, {total_rejected:,} rejected")

                        unique_count = len(set(lemmas))
                        if len(lemmas) < args.min_vocab_tokens:
                            stats["rejected_too_short"] += 1
                            continue
                        if unique_count < args.min_unique_lemmas:
                            stats["rejected_too_few_unique"] += 1
                            continue
                        if len(lemmas) > args.max_tokens:
                            stats["rejected_too_long"] += 1
                            continue

                        newspaper, decade = document_bucket(ci_id)
                        strata[f"{newspaper}\t{decade}"] += 1
                        stats["docs_written"] += 1
                        out.write(f"{ci_id}\tDUMMY\t{' '.join(lemmas)}\n")
        
        log.info(f"Processing complete: {stats['docs_seen']:,} documents processed, "
                f"{stats['docs_written']:,} written, "
                f"{stats['rejected_too_short'] + stats['rejected_too_few_unique'] + stats['rejected_too_long']:,} rejected")

        metadata = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "run_id": args.run_id,
            "language": args.language,
            "inputs": inputs,
            "vocab": args.vocab,
            "criteria": {
                "pos_tags": sorted(pos_tags),
                "min_lemma_length": args.min_lemma_length,
                "min_vocab_tokens": args.min_vocab_tokens,
                "min_unique_lemmas": args.min_unique_lemmas,
                "max_tokens": args.max_tokens,
                "include_titles": args.include_titles,
            },
            "counts": dict(stats),
            "strata": dict(sorted(strata.items())),
        }
        
        with smart_open(stats_output_path, "w", encoding="utf-8", transport_params=get_transport_params(stats_output_path)) as handle:
            json.dump(metadata, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        
        # Upload to S3 if needed
        if output_is_s3:
            upload_to_s3(output_path, args.output)
        
        if stats_is_s3:
            upload_to_s3(stats_output_path, args.stats_output)
        
        log.info("Extraction complete")
        return 0
    
    finally:
        # Clean up temporary files
        if temp_output:
            temp_output.close()
            try:
                Path(output_path).unlink()
                log.debug(f"Cleaned up temporary file {output_path}")
            except Exception as e:
                log.warning(f"Failed to clean up temporary file {output_path}: {e}")
        
        if temp_stats:
            temp_stats.close()
            try:
                Path(stats_output_path).unlink()
                log.debug(f"Cleaned up temporary file {stats_output_path}")
            except Exception as e:
                log.warning(f"Failed to clean up temporary file {stats_output_path}: {e}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        log.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(2)
