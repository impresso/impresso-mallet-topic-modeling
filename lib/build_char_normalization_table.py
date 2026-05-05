#!/usr/bin/env python3
"""
Build a character normalization table from a corpus character-frequency JSON.

Input JSON:
{
  "char_freqs": {
    "é": 331754,
    "’": 141036
  },
  "freqs": {
    ...
  }
}

Output JSON:
{
  "metadata": {...},
  "char_normalization": {
    "é": "e",
    "’": "'",
    "—": "-",
    "œ": "oe"
  }
}
"""

from __future__ import annotations

import argparse
import json
import unicodedata
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


MANUAL_CHAR_MAP: dict[str, str | None] = {
    # Ligatures and special Latin letters
    "œ": "oe",
    "Œ": "oe",
    "æ": "ae",
    "Æ": "ae",
    "ß": "ss",
    "þ": "th",
    "Þ": "th",
    "ð": "d",
    "Ð": "d",
    "ø": "o",
    "ı": "i",
    "ł": "l",
    "ӧ": "o",
    # Spacing diacritics should not introduce spaces inside tokens.
    "¨": None,
    "¯": None,
    "¸": None,
    "˜": None,
    # Apostrophe variants
    "’": "'",
    "‘": "'",
    "ʼ": "'",
    "ʻ": "'",
    "`": "'",
    "´": "'",
    "′": "'",
    # Hyphen/dash variants
    "‐": "-",
    "-": "-",
    "‒": "-",
    "–": "-",
    "—": "-",
    "−": "-",
    "⸗": "-",
    # Quote variants
    "«": '"',
    "»": '"',
    "“": '"',
    "”": '"',
    "„": '"',
    "‟": '"',
    "‹": "'",
    "›": "'",
    # Decorative symbols
    "™": None,
    # Explicitly remove replacement character if present
    "�": None,
}


def ascii_fold_char(ch: str) -> str | None:
    """
    Return an ASCII replacement for a single character.

    None means no replacement should be proposed. This is used only to build
    the table; production normalization can then use str.translate().
    """
    if ch in MANUAL_CHAR_MAP:
        return MANUAL_CHAR_MAP[ch]

    # Keep ordinary ASCII unchanged; no need to include it in the table.
    if ch.isascii():
        return None

    decomposed = unicodedata.normalize("NFKD", ch)
    folded = "".join(c for c in decomposed if not unicodedata.combining(c))
    if folded and folded.isascii() and folded != ch:
        return folded.lower()
    return None


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


def load_char_freqs(path: str) -> dict[str, int]:
    with open_text(path, "r") as f:
        data = json.load(f)

    if "char_freqs" not in data:
        raise ValueError("Input JSON must contain a 'char_freqs' object.")

    char_freqs = data["char_freqs"]
    if not isinstance(char_freqs, dict):
        raise ValueError("'char_freqs' must be a JSON object.")

    for ch in char_freqs:
        if len(ch) != 1:
            raise ValueError(f"Character key must have length 1: {ch!r}")

    return {ch: int(count) for ch, count in char_freqs.items()}


def build_table(
    char_freqs: dict[str, int],
    min_count: int = 1,
) -> dict[str, str | None]:
    table: dict[str, str | None] = {}
    for ch, count in sorted(char_freqs.items(), key=lambda x: (-x[1], x[0])):
        if count < min_count:
            continue
        if ch in MANUAL_CHAR_MAP:
            table[ch] = MANUAL_CHAR_MAP[ch]
            continue
        replacement = ascii_fold_char(ch)
        if replacement is not None:
            table[ch] = replacement
    return table


def char_report_entry(ch: str, count: int, replacement: str | None) -> dict[str, Any]:
    return {
        "char": ch,
        "codepoint": f"U+{ord(ch):04X}",
        "unicode_name": unicodedata.name(ch, "<no name>"),
        "unicode_category": unicodedata.category(ch),
        "count": count,
        "replacement": replacement,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_json", help="Input JSON path, local or s3:// URI.")
    parser.add_argument("output_json", help="Output JSON path, local or s3:// URI.")
    parser.add_argument(
        "--min-count",
        type=int,
        default=1,
        help="Only propose mappings for characters with at least this count.",
    )
    parser.add_argument(
        "--report-json",
        default=None,
        help=(
            "Optional diagnostic report of mapped and unmapped non-ASCII "
            "characters, local or s3:// URI."
        ),
    )
    if add_force_s3_overwrite_argument is not None:
        add_force_s3_overwrite_argument(parser)
    else:
        add_local_force_s3_overwrite_argument(parser)
    args = parser.parse_args()

    force_s3_overwrite = getattr(args, "force_s3_overwrite", False)
    if assert_can_write_uri is not None:
        assert_can_write_uri(args.output_json, force_s3_overwrite=force_s3_overwrite)
        assert_can_write_uri(args.report_json, force_s3_overwrite=force_s3_overwrite)

    char_freqs = load_char_freqs(args.input_json)
    table = build_table(char_freqs, min_count=args.min_count)
    output = {
        "metadata": {
            "description": (
                "Character-level normalization table for lemma normalization. "
                "Values are used with str.translate(); null means delete."
            ),
            "min_count": args.min_count,
            "num_input_chars": len(char_freqs),
            "num_mapped_chars": len(table),
        },
        "char_normalization": table,
    }

    with open_text(args.output_json, "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, sort_keys=True)

    if args.report_json is not None:
        report = []
        for ch, count in sorted(char_freqs.items(), key=lambda x: (-x[1], x[0])):
            replacement = table.get(ch)
            if not ch.isascii() or replacement is not None:
                report.append(char_report_entry(ch, count, replacement))
        with open_text(args.report_json, "w") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"Wrote character normalization table to {args.output_json}")


if __name__ == "__main__":
    main()
