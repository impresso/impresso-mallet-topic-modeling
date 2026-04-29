#!/usr/bin/env python3
"""Create a deterministic stratified sample from eligible MALLET TSV shards."""

import argparse
import heapq
import hashlib
try:
    import ujson as json  # type: ignore
except ImportError:
    import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from dotenv import load_dotenv

from s3_overwrite import add_force_s3_overwrite_argument, assert_can_write_uri

try:
    from impresso_cookbook import get_s3_client  # type: ignore
except ImportError:
    def get_s3_client():
        import boto3
        import os
        return boto3.client(
            "s3",
            aws_access_key_id=os.environ.get("SE_ACCESS_KEY"),
            aws_secret_access_key=os.environ.get("SE_SECRET_KEY"),
            endpoint_url=os.environ.get("SE_HOST_URL")
        )

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


def stratum_for_ci_id(ci_id: str, fields: set[str]) -> str:
    match = CI_ID_RE.match(ci_id)
    newspaper = "unknown"
    decade = "unknown"
    year = "unknown"
    if match:
        newspaper = match.group("newspaper")
        year_int = int(match.group("year"))
        year = str(year_int)
        decade = f"{year_int // 10 * 10}s"

    parts: list[str] = []
    if "newspaper" in fields:
        parts.append(newspaper)
    if "year" in fields:
        parts.append(year)
    if "decade" in fields:
        parts.append(decade)
    return "|".join(parts) if parts else "all"


def score_line(seed: int, ci_id: str) -> int:
    digest = hashlib.blake2b(f"{seed}\t{ci_id}".encode("utf-8"), digest_size=8)
    return int.from_bytes(digest.digest(), "big")


def iter_rows(paths: Iterable[str]) -> Iterable[tuple[str, str]]:
    for path in paths:
        with smart_open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                row = line.rstrip("\n")
                if not row:
                    continue
                fields = row.split("\t", 2)
                if len(fields) != 3:
                    continue
                yield fields[0], row


def main() -> int:
    load_dotenv()  # Load S3 credentials from .env file
    
    parser = argparse.ArgumentParser(
        description="Sample eligible MALLET TSV rows with deterministic stratification."
    )
    parser.add_argument("--input", action="append", default=[])
    parser.add_argument("--s3-prefix", action="append", default=[])
    parser.add_argument("--input-suffix", default=".eligible.tsv.bz2")
    parser.add_argument("--sample-size", type=int, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--strata", default="newspaper,decade")
    parser.add_argument("--min-per-stratum", type=int, default=0)
    parser.add_argument("--max-per-stratum", type=int)
    parser.add_argument("--output", required=True)
    parser.add_argument("--manifest-output", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--language", required=True)
    add_force_s3_overwrite_argument(parser)
    args = parser.parse_args()

    inputs = expand_inputs(args.input, args.s3_prefix, args.input_suffix)
    if not inputs:
        print("no input files found", file=sys.stderr)
        return 2

    assert_can_write_uri(args.output, force_s3_overwrite=args.force_s3_overwrite)
    assert_can_write_uri(
        args.manifest_output, force_s3_overwrite=args.force_s3_overwrite
    )

    stratum_fields = {field.strip() for field in args.strata.split(",") if field.strip()}
    heaps: dict[str, list[tuple[int, str]]] = defaultdict(list)
    stratum_counts: Counter[str] = Counter()
    malformed = 0

    # Keep the best max_per_stratum rows per stratum if configured. Otherwise
    # keep all rows per stratum and trim globally later.
    stratum_limit = args.max_per_stratum
    for ci_id, row in iter_rows(inputs):
        stratum = stratum_for_ci_id(ci_id, stratum_fields)
        stratum_counts[stratum] += 1
        score = score_line(args.seed, ci_id)
        heap = heaps[stratum]
        item = (-score, row)
        if stratum_limit:
            if len(heap) < stratum_limit:
                heapq.heappush(heap, item)
            elif item > heap[0]:
                heapq.heapreplace(heap, item)
        else:
            heap.append(item)

    candidates: list[tuple[int, str, str]] = []
    selected_by_stratum: Counter[str] = Counter()

    for stratum, heap in heaps.items():
        rows = sorted(((-score, row) for score, row in heap), key=lambda item: item[0])
        guaranteed = rows[: args.min_per_stratum] if args.min_per_stratum else []
        for score, row in guaranteed:
            candidates.append((score, stratum, row))
            selected_by_stratum[stratum] += 1
        for score, row in rows[len(guaranteed) :]:
            candidates.append((score, stratum, row))

    # Deduplicate rows that may have appeared through overlapping inputs, then
    # keep the globally best scoring rows.
    seen: set[str] = set()
    unique_candidates: list[tuple[int, str, str]] = []
    for score, stratum, row in sorted(candidates, key=lambda item: item[0]):
        ci_id = row.split("\t", 1)[0]
        if ci_id in seen:
            continue
        seen.add(ci_id)
        unique_candidates.append((score, stratum, row))

    selected = unique_candidates[: args.sample_size]
    selected_by_stratum = Counter(stratum for _, stratum, _ in selected)

    with smart_open(args.output, "w", encoding="utf-8") as out:
        for _, _, row in selected:
            out.write(row)
            out.write("\n")

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_id": args.run_id,
        "language": args.language,
        "inputs": inputs,
        "criteria": {
            "sample_size": args.sample_size,
            "seed": args.seed,
            "strata": sorted(stratum_fields),
            "min_per_stratum": args.min_per_stratum,
            "max_per_stratum": args.max_per_stratum,
        },
        "counts": {
            "input_rows": sum(stratum_counts.values()),
            "malformed_rows": malformed,
            "candidate_rows": len(unique_candidates),
            "sample_rows": len(selected),
        },
        "stratum_counts": dict(sorted(stratum_counts.items())),
        "selected_by_stratum": dict(sorted(selected_by_stratum.items())),
    }
    with smart_open(args.manifest_output, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
