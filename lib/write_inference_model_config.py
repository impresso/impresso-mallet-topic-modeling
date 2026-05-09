#!/usr/bin/env python3
"""Write an inference-facing topic-model config JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"expected boolean value, got {value!r}")


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a self-describing config for downstream inference."
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--schema-version", default="3.0")
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--language", required=True)
    parser.add_argument("--topic-count", type=int, required=True)
    parser.add_argument("--mallet-version", required=True)
    parser.add_argument("--mallet-runtime", required=True)
    parser.add_argument("--preprocessing-mode", required=True)
    parser.add_argument("--upos-filter", required=True)
    parser.add_argument("--lowercase-token", type=parse_bool, required=True)
    parser.add_argument("--min-lemma-length", type=int, required=True)
    parser.add_argument("--min-vocab-tokens", type=int, required=True)
    parser.add_argument("--min-unique-lemmas", type=int, required=True)
    parser.add_argument("--include-titles", type=parse_bool, required=True)
    parser.add_argument("--expected-lingproc-run-id", required=True)
    parser.add_argument("--expected-lingproc-s3-base", required=True)
    parser.add_argument("--config-source")
    parser.add_argument("--inferencer", required=True)
    parser.add_argument("--pipe", required=True)
    parser.add_argument("--vocab", required=True)
    parser.add_argument("--char-normalization", required=True)
    parser.add_argument("--topic-description", required=True)
    args = parser.parse_args()

    data = {
        "schema_version": args.schema_version,
        "model_id": args.model_id,
        "language": args.language,
        "topic_count": args.topic_count,
        "mallet": {
            "version": args.mallet_version,
            "runtime": args.mallet_runtime,
            "memory_env": "MALLET_MEMORY",
        },
        "linguistic_preprocessing": {
            "expected_input_run_id": args.expected_lingproc_run_id,
            "expected_s3_base_path": args.expected_lingproc_s3_base,
            "compatibility_note": (
                "This topic model was trained on this linguistic-processing output "
                "family. Apply inference to the same schema/run family unless a new "
                "compatibility check has been done."
            ),
        },
        "preprocessing": {
            "mode": args.preprocessing_mode,
            "upos_filter": split_csv(args.upos_filter),
            "lowercase_token": args.lowercase_token,
            "min_lemma_length": args.min_lemma_length,
            "min_vocab_tokens": args.min_vocab_tokens,
            "min_lemmas": args.min_vocab_tokens,
            "min_unique_lemmas": args.min_unique_lemmas,
            "include_titles": args.include_titles,
        },
        "artifacts": {
            "inferencer": args.inferencer,
            "pipe": args.pipe,
            "vocab": args.vocab,
            "char_normalization": args.char_normalization,
            "topic_description": args.topic_description,
        },
    }
    if args.config_source:
        data["training_config_source"] = args.config_source

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
