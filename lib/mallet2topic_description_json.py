#!/usr/bin/env python3
"""Convert MALLET topic-word weights to Impresso topic description JSONL."""

import argparse
try:
    import ujson as json  # type: ignore
except ImportError:
    import json
import math
from operator import itemgetter
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


def format_topic_id(topic: int, topic_model: str, lang: str, topic_count: int) -> str:
    width = max(1, math.ceil(math.log10(topic_count)))
    return f"{topic_model}_tp{topic:0{width}d}_{lang}"


def iter_topic_records(path: str, min_score: float) -> Iterable[list[list[object]]]:
    current_topic: int | None = None
    records: list[list[object]] = []

    with smart_open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            fields = line.rstrip("\n").split("\t")
            if len(fields) != 3:
                continue
            topic = int(fields[0])
            word = fields[1]
            score = float(fields[2])
            if score <= min_score:
                continue

            if current_topic is None:
                current_topic = topic
            if topic != current_topic:
                if records:
                    yield records
                records = []
                current_topic = topic
            records.append([topic, word, score])

    if records:
        yield records


def normalize(records: list[list[object]], min_probability: float) -> list[list[object]]:
    total = sum(float(record[2]) for record in records)
    if total <= 0:
        return []
    normalized = []
    for topic, word, score in records:
        probability = float(score) / total
        if probability >= min_probability:
            normalized.append([topic, word, probability])
    return sorted(normalized, key=itemgetter(2), reverse=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert MALLET topic-word weights to topic description JSONL."
    )
    parser.add_argument("input")
    parser.add_argument("-L", "--lang", default="und")
    parser.add_argument("-M", "--topic-model", default="tm000")
    parser.add_argument("-N", "--number-of-topics", type=int, required=True)
    parser.add_argument("-W", "--max-words", type=int, default=200)
    parser.add_argument("--min-score", type=float, default=0.01)
    parser.add_argument("--min-probability", type=float, default=0.0001)
    parser.add_argument("-o", "--output", help="Output JSONL path, default stdout")
    args = parser.parse_args()

    round_digits = math.ceil(abs(math.log10(args.min_probability))) + 1
    out = (
        smart_open(args.output, "w", encoding="utf-8")
        if args.output
        else None
    )
    try:
        handle = out
        for records in iter_topic_records(args.input, args.min_score):
            normalized = normalize(records, args.min_probability)
            if not normalized:
                continue
            topic = int(normalized[0][0])
            item = {
                "topic": topic,
                "lg": args.lang,
                "topic_model": args.topic_model,
                "id": format_topic_id(
                    topic, args.topic_model, args.lang, args.number_of_topics
                ),
                "word_probs": [
                    {"word": str(word), "prob": round(float(prob), round_digits)}
                    for _, word, prob in normalized[: args.max_words]
                ],
            }
            line = json.dumps(item, ensure_ascii=False, separators=(",", ":"))
            if handle:
                handle.write(line)
                handle.write("\n")
            else:
                print(line)
    finally:
        if out:
            out.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
