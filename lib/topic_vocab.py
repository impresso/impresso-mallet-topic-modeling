#!/usr/bin/env python3
"""Create a topic-model vocabulary from aggregated lemma frequencies."""

import argparse
import bz2
import hashlib
try:
    import ujson as json  # type: ignore
except ImportError:
    import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

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


def read_word_file(path: str | None, lower: bool = True) -> set[str]:
    if not path:
        return set()
    if not path.startswith("s3://") and not Path(path).exists():
        return set()

    words: set[str] = set()
    with smart_open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            word = line.strip().split("\t", 1)[0]
            if word:
                words.add(word.lower() if lower else word)
    return words


def sha256_path(path: str | None) -> str | None:
    if not path:
        return None
    if not path.startswith("s3://") and not Path(path).exists():
        return None

    digest = hashlib.sha256()
    with smart_open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_vocab(
    freqs: dict[str, int],
    *,
    min_freq: int,
    max_freq: int,
    min_length: int,
    negative_words: set[str],
    include_words: set[str],
    exclude_words: set[str],
) -> Iterable[tuple[str, int]]:
    for lemma, count in freqs.items():
        normalized = lemma.strip().lower()
        if not normalized:
            continue
        if len(normalized) < min_length:
            continue
        if count < min_freq or count > max_freq:
            continue
        if normalized in negative_words or normalized in exclude_words:
            continue
        if include_words and normalized not in include_words:
            continue
        yield normalized, int(count)


def write_vocab(path: str, rows: list[tuple[str, int]]) -> None:
    with smart_open(path, "w", encoding="utf-8") as handle:
        for lemma, count in rows:
            handle.write(f"{lemma}\t{count}\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Trim an aggregated lemmafreq JSON file into a topic vocabulary."
    )
    parser.add_argument("--lemmafreq", required=True, help="Aggregated lemmafreq JSON.bz2")
    parser.add_argument("--language", required=True, help="Language code")
    parser.add_argument("--min-frequency", type=int, required=True)
    parser.add_argument("--max-frequency", type=int, required=True)
    parser.add_argument("--min-length", type=int, default=3)
    parser.add_argument("--negative-list", help="Words to exclude")
    parser.add_argument("--include-vocab", help="Optional allow-list")
    parser.add_argument("--exclude-vocab", help="Optional deny-list")
    parser.add_argument("--output", required=True, help="Output vocab TSV")
    parser.add_argument("--metadata-output", required=True, help="Output metadata JSON")
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    negative_words = read_word_file(args.negative_list)
    include_words = read_word_file(args.include_vocab)
    exclude_words = read_word_file(args.exclude_vocab)

    with smart_open(args.lemmafreq, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    freqs = data.get("freqs")
    if not isinstance(freqs, dict):
        print("lemmafreq file does not contain a freqs object", file=sys.stderr)
        return 2

    rows = sorted(
        iter_vocab(
            {str(k): int(v) for k, v in freqs.items()},
            min_freq=args.min_frequency,
            max_freq=args.max_frequency,
            min_length=args.min_length,
            negative_words=negative_words,
            include_words=include_words,
            exclude_words=exclude_words,
        ),
        key=lambda item: (-item[1], item[0]),
    )
    write_vocab(args.output, rows)

    metadata = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_id": args.run_id,
        "language": args.language,
        "source_lemmafreq": args.lemmafreq,
        "source_lemmafreq_sha256": sha256_path(args.lemmafreq),
        "source_metadata": {k: v for k, v in data.items() if k != "freqs"},
        "criteria": {
            "min_frequency": args.min_frequency,
            "max_frequency": args.max_frequency,
            "min_length": args.min_length,
            "negative_list": args.negative_list,
            "negative_list_sha256": sha256_path(args.negative_list),
            "include_vocab": args.include_vocab,
            "include_vocab_sha256": sha256_path(args.include_vocab),
            "exclude_vocab": args.exclude_vocab,
            "exclude_vocab_sha256": sha256_path(args.exclude_vocab),
        },
        "counts": {
            "source_vocab_size": len(freqs),
            "output_vocab_size": len(rows),
            "negative_words": len(negative_words),
            "include_words": len(include_words),
            "exclude_words": len(exclude_words),
        },
    }

    with smart_open(args.metadata_output, "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
