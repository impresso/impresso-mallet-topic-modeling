#!/usr/bin/env python3
"""Extract eligible MALLET training texts from linguistic-processing JSONL."""

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

try:
    from smart_open import open as smart_open  # type: ignore
except ModuleNotFoundError:
    import bz2
    import builtins

    def smart_open(path: str, mode: str = "r", encoding: str | None = None):
        if path.startswith("s3://"):
            raise RuntimeError("smart_open is required for S3 paths")
        if path.endswith(".bz2"):
            return bz2.open(path, mode) if "b" in mode else bz2.open(path, mode + "t" if "t" not in mode else mode, encoding=encoding)
        return builtins.open(path, mode) if "b" in mode else builtins.open(path, mode, encoding=encoding)


CI_ID_RE = re.compile(r"^(?P<newspaper>.+?)-(?P<year>\d{4})-\d{2}-\d{2}-")


def list_s3(prefix: str, suffix: str) -> list[str]:
    import boto3  # type: ignore

    parsed = urlparse(prefix)
    bucket = parsed.netloc
    key_prefix = parsed.path.lstrip("/")
    client = boto3.client("s3")
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
    vocab: set[str] = set()
    with smart_open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            lemma = line.strip().split("\t", 1)[0]
            if lemma:
                vocab.add(lemma.lower())
    return vocab


def iter_sentences(doc: dict[str, Any], include_titles: bool) -> Iterable[dict[str, Any]]:
    yield from doc.get("sents", [])
    if include_titles:
        yield from doc.get("tsents", [])


def iter_tokens(sent: dict[str, Any]) -> Iterable[dict[str, Any]]:
    tokens = sent.get("tokens")
    if tokens is None:
        tokens = sent.get("tok", [])
    yield from tokens or []


def document_bucket(ci_id: str) -> tuple[str, str]:
    match = CI_ID_RE.match(ci_id)
    if not match:
        return "unknown", "unknown"
    newspaper = match.group("newspaper")
    year = int(match.group("year"))
    return newspaper, f"{year // 10 * 10}s"


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
            lemma = str(token.get("l") or token.get("t") or "").strip().lower()
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
    parser.add_argument("--include-titles", action="store_true")
    parser.add_argument("--output", required=True)
    parser.add_argument("--stats-output", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    inputs = expand_inputs(args.input, args.s3_prefix, args.input_suffix)
    if not inputs:
        print("no input files found", file=sys.stderr)
        return 2

    vocab = load_vocab(args.vocab)
    pos_tags = {tag.strip() for tag in args.pos_tags.split(",") if tag.strip()}

    stats: Counter[str] = Counter()
    strata: Counter[str] = Counter()

    with smart_open(args.output, "w", encoding="utf-8") as out:
        for path in inputs:
            stats["input_files"] += 1
            with smart_open(path, "r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, 1):
                    stats["input_lines"] += 1
                    try:
                        doc = json.loads(line)
                    except json.JSONDecodeError:
                        stats["json_errors"] += 1
                        continue

                    ci_id = str(doc.get("ci_id") or doc.get("id") or "")
                    if not ci_id:
                        stats["missing_ci_id"] += 1
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
    with smart_open(args.stats_output, "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
