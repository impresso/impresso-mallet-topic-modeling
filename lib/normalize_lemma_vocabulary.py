#!/usr/bin/env python3
"""
Normalize unnormalized lemma counts using a character normalization table.
After character normalization, boundary punctuation is stripped and internal
periods/apostrophes/hyphens are deleted before validating the final core as ASCII
letters only.

Input frequency JSON:
{
  "char_freqs": {...},
  "freqs": {
    "économie": 123,
    "-accidents": 34,
    "''''''ssbbi": 1
  }
}

Input normalization JSON:
{
  "char_normalization": {
    "é": "e",
    "œ": "oe",
    "’": "'",
    "—": "-"
  }
}

Output JSON:
{
  "metadata": {...},
  "normalized_freqs": {
    "economie": 123,
    "accidents": 34
  },
  "diagnostics": {...}
}
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    from smart_open import open as smart_open  # type: ignore
except ImportError:  # pragma: no cover - exercised only in minimal envs
    smart_open = None

try:
    from impresso_cookbook import get_transport_params  # type: ignore
except ImportError:  # pragma: no cover - exercised only in minimal envs
    get_transport_params = None

try:
    from s3_overwrite import (  # type: ignore
        add_force_s3_overwrite_argument,
        assert_can_write_uri,
    )
except ImportError:  # pragma: no cover - exercised only in minimal envs
    add_force_s3_overwrite_argument = None
    assert_can_write_uri = None

log = logging.getLogger(__name__)


def parse_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(
        f"expected TRUE/FALSE for --force-s3-overwrite, got {value!r}"
    )


def add_local_force_s3_overwrite_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--force-s3-overwrite",
        type=parse_bool,
        default=False,
        metavar="TRUE/FALSE",
        help="Allow overwriting existing s3:// outputs. Defaults to FALSE.",
    )


def setup_local_logging(log_level: str, log_file: str | None = None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
    )


VALID_CORE_RE = re.compile(r"^[a-z]+$")
DEFAULT_BOUNDARY_CHARS = (
    " \t\n\r"
    ".,;:!?()[]{}"
    "\"'"
    "-_\\/|~^=+*@#$%&§°£€¥¢©®™"
    "•■□▲►▼★♦✓†‡¶"
)


def open_text(path: str, mode: str):
    if path.startswith("s3://"):
        if smart_open is None or get_transport_params is None:
            raise RuntimeError(
                "Reading or writing s3:// paths requires smart-open[s3] and "
                "impresso-cookbook. Install the project dependencies first."
            )
        return smart_open(
            path,
            mode,
            encoding="utf-8",
            transport_params=get_transport_params(path),
        )
    if smart_open is not None:
        transport_params = get_transport_params(path) if get_transport_params else None
        return smart_open(
            path,
            mode,
            encoding="utf-8",
            transport_params=transport_params,
        )
    return Path(path).open(mode, encoding="utf-8")


def load_freqs(path: str) -> dict[str, int]:
    with open_text(path, "r") as f:
        data = json.load(f)

    if "freqs" not in data:
        raise ValueError("Input JSON must contain a 'freqs' object.")

    freqs = data["freqs"]
    if not isinstance(freqs, dict):
        raise ValueError("'freqs' must be a JSON object.")

    return {lemma: int(count) for lemma, count in freqs.items()}


def load_translation_table(path: str) -> dict[int, str | None]:
    with open_text(path, "r") as f:
        data = json.load(f)

    if "char_normalization" not in data:
        raise ValueError("Normalization JSON must contain 'char_normalization'.")

    raw_table = data["char_normalization"]
    if not isinstance(raw_table, dict):
        raise ValueError("'char_normalization' must be a JSON object.")

    table: dict[int, str | None] = {}
    for source, target in raw_table.items():
        if len(source) != 1:
            raise ValueError(f"Source key must be one character: {source!r}")
        if target is not None and not isinstance(target, str):
            raise ValueError(
                f"Replacement for {source!r} must be string or null, got {target!r}"
            )
        table[ord(source)] = target
    return table


def count_ascii_letters(text: str) -> int:
    return sum("a" <= ch <= "z" for ch in text)


class LemmaNormalizer:
    def __init__(
        self,
        translation_table: dict[int, str | None],
        boundary_chars: str = DEFAULT_BOUNDARY_CHARS,
        min_alpha: int = 3,
        min_alpha_ratio: float = 0.75,
        cache_size: int = 2_000_000,
    ) -> None:
        self.translation_table = translation_table
        self.boundary_chars = boundary_chars
        self.min_alpha = min_alpha
        self.min_alpha_ratio = min_alpha_ratio
        self.normalize = lru_cache(maxsize=cache_size)(self._normalize_uncached)

    def normalize_chars(self, lemma: str) -> str:
        return lemma.lower().translate(self.translation_table)

    def _normalize_uncached(self, lemma: str) -> str | None:
        base = self.normalize_chars(lemma).strip()
        if not base:
            return None

        # We are not doing number-shape normalization here.
        if any(ch.isdigit() for ch in base):
            return None

        candidate = base.strip(self.boundary_chars)
        if not candidate:
            return None
        candidate = candidate.replace(".", "")
        candidate = candidate.replace("-", "")
        candidate = candidate.replace("'", "")
        if not candidate:
            return None
        if VALID_CORE_RE.fullmatch(candidate) is None:
            return None

        alpha_len = count_ascii_letters(candidate)
        if alpha_len < self.min_alpha:
            return None
        if alpha_len / len(base) < self.min_alpha_ratio:
            return None

        return candidate


def normalize_freqs(
    freqs: dict[str, int],
    normalizer: LemmaNormalizer,
    max_examples_per_norm: int = 10,
    progress_interval: int = 100_000,
) -> dict[str, Any]:
    normalized_freqs: Counter[str] = Counter()
    removed_freq = 0
    removed_types = 0
    changed_freq = 0
    changed_types = 0
    raw_examples: dict[str, list[tuple[str, int]]] = defaultdict(list)
    removed_examples: Counter[str] = Counter()

    total_types = len(freqs)
    for index, (raw, count) in enumerate(freqs.items(), 1):
        norm = normalizer.normalize(raw)
        if norm is None:
            removed_freq += count
            removed_types += 1
            removed_examples[raw] += count
        else:
            normalized_freqs[norm] += count
            if norm != raw:
                changed_freq += count
                changed_types += 1
                if len(raw_examples[norm]) < max_examples_per_norm:
                    raw_examples[norm].append((raw, count))

        if progress_interval > 0 and index % progress_interval == 0:
            log.info(
                "Normalized %d/%d vocab items; kept=%d removed=%d changed=%d",
                index,
                total_types,
                len(normalized_freqs),
                removed_types,
                changed_types,
            )

    normalized_freqs_sorted = dict(
        sorted(normalized_freqs.items(), key=lambda x: (-x[1], x[0]))
    )
    raw_examples_sorted = {
        norm: sorted(examples, key=lambda x: (-x[1], x[0]))
        for norm, examples in sorted(
            raw_examples.items(),
            key=lambda x: (-normalized_freqs[x[0]], x[0]),
        )
    }
    diagnostics = {
        "input_num_types": len(freqs),
        "input_total_freq": sum(freqs.values()),
        "normalized_num_types": len(normalized_freqs),
        "normalized_total_freq": sum(normalized_freqs.values()),
        "removed_num_types": removed_types,
        "removed_total_freq": removed_freq,
        "changed_num_types": changed_types,
        "changed_total_freq": changed_freq,
        "most_common_removed": removed_examples.most_common(100),
        "raw_examples_by_normalized_form": raw_examples_sorted,
    }
    return {
        "normalized_freqs": normalized_freqs_sorted,
        "diagnostics": diagnostics,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_freqs_json", help="Input frequency JSON path, local or s3:// URI.")
    parser.add_argument(
        "char_normalization_json",
        help="Character normalization JSON path, local or s3:// URI.",
    )
    parser.add_argument("output_json", help="Output JSON path, local or s3:// URI.")
    parser.add_argument(
        "--min-alpha",
        type=int,
        default=3,
        help="Minimum number of ASCII alphabetic characters in the normalized core.",
    )
    parser.add_argument(
        "--min-alpha-ratio",
        type=float,
        default=0.75,
        help=(
            "Minimum ratio: alphabetic characters in final core / "
            "length after character normalization before boundary stripping."
        ),
    )
    parser.add_argument(
        "--cache-size",
        type=int,
        default=2_000_000,
    )
    parser.add_argument(
        "--progress-interval",
        type=int,
        default=100_000,
        help=(
            "Log progress every N input vocab items. Use 0 to disable. "
            "Default: %(default)s."
        ),
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: %(default)s)",
    )
    parser.add_argument(
        "--log-file", dest="log_file", help="Write log to FILE", metavar="FILE"
    )
    if add_force_s3_overwrite_argument is not None:
        add_force_s3_overwrite_argument(parser)
    else:
        add_local_force_s3_overwrite_argument(parser)
    args = parser.parse_args()
    setup_local_logging(args.log_level, args.log_file)

    if assert_can_write_uri is not None:
        assert_can_write_uri(
            args.output_json,
            force_s3_overwrite=getattr(args, "force_s3_overwrite", False),
        )

    log.info("Loading frequencies from %s", args.input_freqs_json)
    freqs = load_freqs(args.input_freqs_json)
    log.info("Loaded %d input vocab items", len(freqs))
    log.info("Loading character normalization table from %s", args.char_normalization_json)
    translation_table = load_translation_table(args.char_normalization_json)
    log.info("Loaded %d character normalization mappings", len(translation_table))
    normalizer = LemmaNormalizer(
        translation_table=translation_table,
        min_alpha=args.min_alpha,
        min_alpha_ratio=args.min_alpha_ratio,
        cache_size=args.cache_size,
    )
    result = normalize_freqs(
        freqs,
        normalizer,
        progress_interval=args.progress_interval,
    )
    log.info(
        "Finished normalization: input=%d normalized=%d removed=%d changed=%d",
        result["diagnostics"]["input_num_types"],
        result["diagnostics"]["normalized_num_types"],
        result["diagnostics"]["removed_num_types"],
        result["diagnostics"]["changed_num_types"],
    )
    output = {
        "metadata": {
            "description": (
                "Normalized lemma frequencies produced by character-based "
                "normalization, boundary stripping, lexical validation, and "
                "frequency aggregation."
            ),
            "min_alpha": args.min_alpha,
            "min_alpha_ratio": args.min_alpha_ratio,
            "allowed_core_pattern": VALID_CORE_RE.pattern,
            "digits": "rejected",
        },
        **result,
    }

    with open_text(args.output_json, "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, sort_keys=True)

    log.info("Wrote normalized vocabulary to %s", args.output_json)
    log.info(
        "Types: %d -> %d",
        result["diagnostics"]["input_num_types"],
        result["diagnostics"]["normalized_num_types"],
    )
    log.info(
        "Total frequency: %d -> %d",
        result["diagnostics"]["input_total_freq"],
        result["diagnostics"]["normalized_total_freq"],
    )


if __name__ == "__main__":
    main()
