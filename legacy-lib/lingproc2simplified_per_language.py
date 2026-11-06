#!/usr/bin/env python3
"""
Read jsonl.bz2 lingproc files from s3 and extract the simplified version of the text for
a specific each language.

input looks like this:
{"id":"actionfem-1927-11-15-a-i0007","ts":"2024-11-27T22:32:11Z","sents":[{"lg":"de","tok":[{"t":"In","p":"ADP","o":0,"l":"in"},{"t":"jeder","p":"DET","o":3},{"t":"Monatsversammlung","p":"NOUN","o":9},{"t":"ist","p":"AUX","o":27,"l":"sein"},{"t":"beim","p":"ADP","o":31,"l":"bei"},{"t":"Tiireingang","p":"NOUN","o":36},{"t":"Gelegenheit","p":"NOUN","o":48},{"t":"neue","p":"ADJ","o":60,"l":"neu"},{"t":"Mitglieder","p":"NOUN","o":65,"l":"Mitglied"},{"t":"einzuschreiben","p":"VERB","o":76},{"t":".","p":"PUNCT","o":90,"l":"--"}]}],"model_id":"spacy@3.6.0:de_core_news_md@3.6.0:sentencizer|tok2vec|tagger|morphologizer|lemmatizer|attribute_ruler|ner","lid_path":"s3://42-processed-data-final/langident/langident_v1-4-4/actionfem/actionfem-1927.jsonl.bz2","lingproc_git":"v2024.11.27-1-ged88e44","char_count":92,"min_chars":50,"max_chars":50000}

Output should look like this: 
{"id":"actionfem-1927-11-15-a-i0007",
"tokens": SYNCED LIST OF all tokens in the text (overall sentences)
"pos_tags": SYNCED LIST OF all pos tags in the text (overall sentences)
"lemmas": SYNCED LIST OF all lemmas in the text (overall sentences)
..} 

Usage:
    python3 lingproc2simplified_per_language.py --s3-prefix s3://your-bucket/your-prefix --language de --output s3://your-output-bucket/output-prefix

Example:
    python3 lib/lingproc2simplified_per_language.py --s3-prefix s3://41-processed-data-staging/lingproc/lingproc-pos-spacy_v3.6.0-multilingual_v2-0-0/actionfem/actionfem-1927.jsonl.bz2 --language de --output out.jsonl

"""

import argparse
try:
    import ujson as json  # type: ignore
except ImportError:
    import json
import logging
from collections import Counter
from typing import Dict, Any, Optional, Sequence

from smart_open import open as smart_open
import sys
import re
from impresso_mallet_lda.s3_to_local_stamps import get_s3_client
from impresso_cookbook import setup_logging  # type: ignore

log = logging.getLogger(__name__)


def list_s3_files_with_prefix(bucket: str, prefix: str) -> Sequence[str]:
    """List all files in an S3 bucket with a given prefix.

    Args:
        bucket (str): S3 bucket name.
        prefix (str): Prefix to filter files.

    Returns:
        Sequence[str]: List of file keys.
    """
    s3 = get_s3_client()
    response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
    files = [content["Key"] for content in response.get("Contents", [])]
    return [file for file in files if file.endswith("jsonl.bz2")]


def process_lingproc_file(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Process a single lingproc JSON object and extract relevant information.

    Args:
        data (Dict[str, Any]): A dictionary representing a single lingproc JSON object.

    Returns:
        Optional[Dict[str, Any]]: A dictionary containing the extracted information, or None if the input is invalid.
    """
    try:
        tokens = []
        pos_tags = []
        lemmas = []

        for sent in data["sents"]:
            tokens.extend([tok["t"] for tok in sent["tokens"]])
            pos_tags.extend([tok["p"] for tok in sent["tokens"]])
            lemmas.extend([tok.get("l",tok["t"]) for tok in sent["tokens"]])

        return {
            "ci_id": data["ci_id"],
            "lg": data["sents"][0]["lg"],
            "length": len(tokens),
            "tokens": tokens,
            "pos_tags": pos_tags,
            "lemmas": lemmas,
        }
    except KeyError as e:
        log.warning("Missing key in data: %s. Skipping this entry.", e)
        return None


def process_s3_files(bucket: str, prefix: str, language: str, output_path: str) -> None:
    """Process JSONL.bz2 files in an S3 bucket, extract data, and write to an output file (local or S3).

    Args:
        bucket (str): S3 bucket name.
        prefix (str): Prefix to filter files.
        language (str): Language to filter by.
        output_path (str): Path to the output file (local or S3).
    """
    files = list_s3_files_with_prefix(bucket, prefix)
    s3 = get_s3_client()
    transport_params = {"client": s3}
    total_lines = 0
    processed_count = 0

    with smart_open(output_path, "w", encoding="utf-8") as outfile:
        for file_key in files:
            log.info("Processing file: %s", file_key)
            with smart_open(
                f"s3://{bucket}/{file_key}",
                "rb",
                transport_params=transport_params,
            ) as infile:
                for line in infile:
                    total_lines += 1
                    try:
                        data = json.loads(line)
                        if data.get("sents") and data.get("sents")[0].get("lg") == language:
                            processed_data = process_lingproc_file(data)
                            if processed_data:
                                outfile.write(json.dumps(processed_data, ensure_ascii=False) + "\n")
                                processed_count += 1
                    except json.JSONDecodeError:
                        log.error("Could not decode JSON from line: %s", line.strip())
                    except Exception as e:
                        log.error("An error occurred: %s", e, exc_info=True)

    log.info("Total lines read: %d", total_lines)
    log.info("Total items processed and written: %d", processed_count)


def parse_arguments(args: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        args (Optional[Sequence[str]]): Command-line arguments.

    Returns:
        argparse.Namespace: Parsed argument namespace.
    """
    parser = argparse.ArgumentParser(
        description="Extract simplified text from JSONL.bz2 files in S3, filtering by language.",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "-o",
        "--output",
        type=str,
        required=True,
        help="Path to store the output JSONL file (local or S3).  Example: s3://your-bucket/output-prefix/output.jsonl",
    )

    parser.add_argument(
        "-l",
        "--language",
        type=str,
        required=True,
        help="Language for which the statistics should be collected",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: %(default)s)",
    )
    parser.add_argument("--log-file", dest="log_file", help="Write log to FILE", metavar="FILE")
    parser.add_argument(
        "--s3-prefix",
        type=str,
        required=True,
        help="S3 path prefix (s3://BUCKET/PREFIX) to read JSONL.bz2 files",
    )
    return parser.parse_args(args)


def main(args: Optional[Sequence[str]] = None) -> None:
    """Main function to run the data extraction and simplification process.

    Args:
        args (Optional[Sequence[str]]): Command-line arguments.
    """

    if args is None:
        args = sys.argv[1:]
    options = parse_arguments(args)

    setup_logging(options.log_level, options.log_file, logger=log)
    log.info("%s", options)
    log.info("Processing S3 prefix: %s", options.s3_prefix)
    match = re.match(r"s3://([^/]+)/(.+)", options.s3_prefix)
    if not match:
        log.error("Invalid S3 prefix format. Expected s3://BUCKET/PREFIX")
        sys.exit(1)
    bucket, prefix = match.groups()

    output_match = re.match(r"s3://([^/]+)/(.+)", options.output)
    if not output_match and options.output.startswith("s3://"):
        log.error("Invalid S3 output format. Expected s3://BUCKET/PREFIX")
        sys.exit(1)

    process_s3_files(bucket, prefix, options.language, options.output)

    log.info("Processing complete. Results saved to %s", options.output)


if __name__ == "__main__":
    main()
