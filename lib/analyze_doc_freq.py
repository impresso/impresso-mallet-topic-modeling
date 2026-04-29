#!/usr/bin/env python3
"""Analyze document frequency in eligible MALLET training TSV files."""

import argparse
import json
import logging
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from smart_open import open as smart_open  # type: ignore

from s3_overwrite import add_force_s3_overwrite_argument, assert_can_write_uri
from impresso_cookbook import get_s3_client, get_timestamp, get_transport_params, setup_logging  # type: ignore

log = logging.getLogger(__name__)


def smart_open_text(path: str, *, raw: bool = False):
    tp = get_transport_params(path)
    if not raw:
        return smart_open(path, "r", encoding="utf-8", transport_params=tp)
    try:
        return smart_open(path, "r", encoding="utf-8", compression="disable", transport_params=tp)
    except TypeError:
        return smart_open(path, "r", encoding="utf-8", ignore_ext=True, transport_params=tp)


def list_s3(prefix: str, suffix: str) -> list[str]:
    """List S3 objects with the given prefix and suffix.
    
    Uses impresso_cookbook get_s3_client() which loads credentials from .env file.
    """
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


def iter_rows_from_path(path: str, *, raw: bool = False) -> Iterable[tuple[str, list[str]]]:
    with smart_open_text(path, raw=raw) as handle:
        for line_number, line in enumerate(handle, 1):
            row = line.rstrip("\n")
            if not row:
                continue
            fields = row.split("\t", 2)
            if len(fields) != 3:
                print(
                    f"skipping malformed row in {path}:{line_number}",
                    file=sys.stderr,
                )
                continue
            doc_id, _, text = fields
            lemmas = [lemma for lemma in text.split() if lemma]
            yield doc_id, lemmas


def iter_eligible_rows(paths: Iterable[str]) -> Iterable[tuple[str, list[str]]]:
    for path in paths:
        rows_yielded = 0
        try:
            for item in iter_rows_from_path(path):
                rows_yielded += 1
                yield item
        except (OSError, EOFError) as exc:
            if path.endswith(".bz2") and rows_yielded == 0:
                print(
                    f"warning: {path} is not valid bzip2; retrying as plain text",
                    file=sys.stderr,
                )
                try:
                    yield from iter_rows_from_path(path, raw=True)
                    continue
                except (OSError, EOFError) as raw_exc:
                    raise RuntimeError(f"failed reading {path}: {raw_exc}") from raw_exc
            raise RuntimeError(f"failed reading {path}: {exc}") from exc


def write_rows(
    path: str | None,
    rows: Iterable[tuple[str, int, int, str]],
    *,
    header: bool,
) -> None:
    if not path:
        out = sys.stdout
        if header:
            out.write("lemma\tdocument_frequency\ttotal_frequency\tdocument_ids\n")
        for lemma, document_frequency, total_frequency, doc_ids in rows:
            out.write(f"{lemma}\t{document_frequency}\t{total_frequency}\t{doc_ids}\n")
        return

    with smart_open(path, "w", encoding="utf-8", transport_params=get_transport_params(path)) as out:
        if header:
            out.write("lemma\tdocument_frequency\ttotal_frequency\tdocument_ids\n")
        for lemma, document_frequency, total_frequency, doc_ids in rows:
            out.write(f"{lemma}\t{document_frequency}\t{total_frequency}\t{doc_ids}\n")


def write_words(path: str, rows: Iterable[tuple[str, int, int, str]]) -> None:
    with smart_open(path, "w", encoding="utf-8", transport_params=get_transport_params(path)) as out:
        for lemma, _, _, _ in rows:
            out.write(f"{lemma}\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Report lemmas with low document frequency across eligible MALLET "
            "TSV shards."
        )
    )
    parser.add_argument(
        "--input",
        action="append",
        default=[],
        help="Eligible TSV file, local or s3://. Can be provided multiple times.",
    )
    parser.add_argument(
        "--s3-prefix",
        "--prefix",
        dest="prefixes",
        action="append",
        default=[],
        help="S3 or local prefix to scan for eligible TSV files.",
    )
    parser.add_argument("--input-suffix", default=".eligible.tsv.bz2")
    parser.add_argument(
        "--output",
        help="Output TSV path. Defaults to stdout. Supports local, .bz2, and s3://.",
    )
    parser.add_argument(
        "--word-output",
        help="Optional one-lemma-per-line output for use as a negative lemma list.",
    )
    parser.add_argument(
        "--metadata-output",
        help="Optional JSON metadata path. Supports local, .bz2, and s3://.",
    )
    parser.add_argument(
        "--max-document-frequency",
        type=int,
        default=1,
        help="Report lemmas appearing in at most this many documents.",
    )
    parser.add_argument("--no-header", action="store_true")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: %(default)s)",
    )
    parser.add_argument(
        "--log-file", dest="log_file", help="Write log to FILE", metavar="FILE"
    )
    add_force_s3_overwrite_argument(parser)
    args = parser.parse_args()
    setup_logging(args.log_level, args.log_file, logger=log)
    if args.max_document_frequency < 1:
        parser.error("--max-document-frequency must be >= 1")

    inputs = expand_inputs(args.input, args.prefixes, args.input_suffix)
    if not inputs:
        print("no eligible files found", file=sys.stderr)
        return 2

    assert_can_write_uri(args.output, force_s3_overwrite=args.force_s3_overwrite)
    assert_can_write_uri(args.word_output, force_s3_overwrite=args.force_s3_overwrite)
    assert_can_write_uri(
        args.metadata_output, force_s3_overwrite=args.force_s3_overwrite
    )

    doc_freq: Counter[str] = Counter()
    total_freq: Counter[str] = Counter()
    doc_ids_by_lemma: dict[str, list[str]] = {}
    document_count = 0
    token_count = 0

    for doc_id, lemmas in iter_eligible_rows(inputs):
        document_count += 1
        token_count += len(lemmas)
        counts = Counter(lemmas)
        for lemma, count in counts.items():
            total_freq[lemma] += count
            seen_doc_ids = doc_ids_by_lemma.setdefault(lemma, [])
            if doc_id in seen_doc_ids:
                continue
            doc_freq[lemma] += 1
            if len(seen_doc_ids) <= args.max_document_frequency:
                seen_doc_ids.append(doc_id)

    rows = [
        (
            lemma,
            count,
            total_freq[lemma],
            ",".join(doc_ids_by_lemma.get(lemma, [])[: args.max_document_frequency]),
        )
        for lemma, count in doc_freq.items()
        if count <= args.max_document_frequency
    ]
    rows.sort(key=lambda item: (item[1], -item[2], item[0]))

    write_rows(args.output, rows, header=not args.no_header)
    if args.word_output:
        write_words(args.word_output, rows)

    if args.metadata_output:
        metadata = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "inputs": inputs,
            "counts": {
                "input_files": len(inputs),
                "documents": document_count,
                "tokens": token_count,
                "vocabulary_size": len(doc_freq),
                "reported_lemmas": len(rows),
            },
            "criteria": {
                "input_suffix": args.input_suffix,
                "max_document_frequency": args.max_document_frequency,
            },
        }
        with smart_open(args.metadata_output, "w", encoding="utf-8", transport_params=get_transport_params(args.metadata_output)) as handle:
            json.dump(metadata, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
