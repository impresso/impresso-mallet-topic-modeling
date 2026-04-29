#!/usr/bin/env python3
"""
Token Extractor for Linguistic Processing Data

This module extracts tokens from linguistically processed (lingproc) JSONL data with
filtering capabilities based on POS tags and languages. It demonstrates best practices
for processing large-scale corpus data in the Impresso project ecosystem.

Key Features:
1. **POS Tag Filtering**: Extract only tokens with specified part-of-speech tags
   (e.g., NOUN, VERB, ADJ) for focused topic modeling or analysis.

2. **Language Filtering**: Process multi-lingual corpora by filtering documents to
   specific languages (e.g., de, fr, en).

3. **S3 Integration**: Seamlessly reads from both local files and S3 URIs using
   smart_open and impresso_cookbook utilities.

4. **Streaming Processing**: Memory-efficient generator-based processing suitable
   for large datasets.

5. **TSV Output Format**: Produces tab-separated output with document ID, language,
   and space-separated tokens suitable for MALLET topic modeling.

Input Format:
    Lingproc JSONL with structure:
    {
        "ci_id": "doc-id",
        "sents": [
            {
                "lg": "de",
                "tok": [
                    {"t": "token", "p": "NOUN", "l": "lemma"}
                ]
            }
        ]
    }

Output Format:
    TSV with columns: document_id\tlanguage\ttoken1 token2 token3 ...

Example Usage:
    # Extract nouns from German documents
    $ python token_extractor.py -i lingproc.jsonl.bz2 \
        --pos-tags NOUN --languages de -o tokens.txt
    
    # Extract multiple POS tags from S3
    $ python token_extractor.py -i s3://bucket/lingproc.jsonl \
        --pos-tags NOUN VERB ADJ -o output.txt
    
    # Extract all POS tags (no language filter)
    $ python token_extractor.py -i input.jsonl \
        --pos-tags NOUN VERB ADJ PROPN --log-level DEBUG

Integration with impresso_cookbook:
    - Uses get_s3_client() for S3 operations
    - Uses get_timestamp() for consistent timestamping
    - Uses setup_logging() for standardized logging configuration
    - Uses get_transport_params() for automatic S3/local file handling
"""

try:
    import ujson as json  # type: ignore
except ImportError:
    import json
import argparse
import logging
import sys
from typing import Generator, Set, Optional, List
from smart_open import open as smart_open  # type: ignore
from dotenv import load_dotenv

from impresso_cookbook import (  # type: ignore
    get_s3_client,
    get_timestamp,
    setup_logging,
    get_transport_params,
)

log = logging.getLogger(__name__)
load_dotenv()


def parse_arguments(args: Optional[List[str]] = None) -> argparse.Namespace:
    """
    Parse command-line arguments.

    Args:
        args: Command-line arguments (uses sys.argv if None)

    Returns:
        argparse.Namespace: Parsed arguments with pos_tags, languages,
            input, output, etc.
    """
    parser = argparse.ArgumentParser(
        description="Extract tokens with specific POS tags from lingproc JSONL data."
    )
    parser.add_argument(
        "--log-file", dest="log_file", help="Write log to FILE", metavar="FILE"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: %(default)s)",
    )
    parser.add_argument(
        "-i",
        "--input",
        dest="input",
        help="Input lingproc JSONL file (local path or s3:// URI, required)",
        required=True,
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="output",
        help="Output TSV file (default: stdout)",
    )
    parser.add_argument(
        "--pos-tags",
        nargs="+",
        required=True,
        help="POS tags to extract (e.g., NOUN VERB ADJ PROPN)",
    )
    parser.add_argument(
        "--languages",
        nargs="+",
        help=(
            "Languages to filter (e.g., de fr en). "
            "If not specified, all languages are included."
        ),
    )
    parser.add_argument(
        "--min-length",
        type=int,
        default=3,
        help="Minimum lemma length in characters (default: %(default)s)",
    )
    return parser.parse_args(args)


class TokenExtractor:
    """
    Extracts tokens from lingproc JSONL data with POS tag and language filtering.

    This processor reads linguistically processed newspaper data and extracts tokens
    matching specified criteria. It's designed for preparing input data for topic
    modeling with MALLET or other text analysis tools.
    """

    def __init__(
        self,
        input_file: str,
        output_file: Optional[str],
        pos_tags: Set[str],
        languages: Optional[Set[str]] = None,
        min_length: int = 3,
        log_level: str = "INFO",
        log_file: Optional[str] = None,
    ) -> None:
        """
        Initializes the TokenExtractor with explicit parameters.

        Args:
            input_file (str): Path to the input lingproc JSONL file (local or S3)
            output_file (Optional[str]): Path to output TSV file (None for stdout)
            pos_tags (Set[str]): Set of POS tags to extract (e.g., {'NOUN', 'VERB'})
            languages (Optional[Set[str]]): Set of languages to filter (None for all)
            min_length (int): Minimum lemma length in characters (default: 3)
            log_level (str): Logging level (default: "INFO")
            log_file (Optional[str]): Path to log file (default: None)
        """
        self.input_file = input_file
        self.output_file = output_file
        self.pos_tags = pos_tags
        self.languages = languages
        self.min_length = min_length
        self.log_level = log_level
        self.log_file = log_file

        # Configure the module-specific logger
        setup_logging(self.log_level, self.log_file, logger=log)

        # Initialize S3 client and timestamp
        self.s3_client = get_s3_client()
        self.timestamp = get_timestamp()

        log.info(
            f"Initialized TokenExtractor: POS tags={sorted(self.pos_tags)}, "
            f"Languages={sorted(self.languages) if self.languages else 'all'}"
        )

    def run(self) -> None:
        """
        Runs the token extraction process, reading from input and writing to output.

        Processes each document in the input JSONL file, extracting tokens that match
        the specified POS tags and languages, then writes results in TSV format.
        """
        try:
            doc_count = 0
            token_count = 0

            # Handle stdout vs file output
            if self.output_file:
                output_stream = smart_open(
                    self.output_file,
                    "w",
                    encoding="utf-8",
                    transport_params=get_transport_params(self.output_file),
                )
            else:
                output_stream = sys.stdout

            try:
                for doc_id, lang, tokens in self.extract_tokens():
                    output_stream.write(f"{doc_id}\t{lang}\t{' '.join(tokens)}\n")
                    doc_count += 1
                    token_count += len(tokens)

                    if doc_count % 1000 == 0:
                        log.info(
                            f"Processed {doc_count} documents, "
                            f"{token_count} tokens extracted"
                        )

                log.info(
                    f"Extraction complete: {doc_count} documents, "
                    f"{token_count} total tokens"
                )
            finally:
                # Only close if it's a file (not stdout)
                if self.output_file:
                    output_stream.close()

        except Exception as e:
            log.error(f"Error during token extraction: {e}", exc_info=True)
            sys.exit(1)

    def extract_tokens(self) -> Generator[tuple[str, str, list[str]], None, None]:
        """
        Generator that yields tuples of (document_id, language, tokens).

        Reads the input lingproc JSONL file line by line, filtering tokens based on
        POS tags and languages, and yields documents with their extracted tokens.

        Yields:
            tuple[str, str, list[str]]: (document_id, language, list of tokens)

        Raises:
            KeyError: If required fields are missing from input data
            json.JSONDecodeError: If input is not valid JSON
        """
        current_doc: Optional[str] = None
        current_lang: Optional[str] = None
        current_tokens: list[str] = []

        with smart_open(
            self.input_file,
            "r",
            encoding="utf-8",
            transport_params=get_transport_params(self.input_file),
        ) as f:
            for line_num, line in enumerate(f, 1):
                try:
                    data = json.loads(line)
                    document_id = data["ci_id"]

                    for sent in data.get("sents", []):
                        language = sent.get("lg")

                        # Skip if language doesn't match filter
                        if self.languages and language not in self.languages:
                            continue

                        # Start new document if ID changes
                        if current_doc != document_id:
                            if current_doc is not None and current_lang is not None:
                                yield current_doc, current_lang, current_tokens
                            current_doc = document_id
                            current_lang = language
                            current_tokens = []

                        # Extract tokens matching POS tags
                        for token in sent.get("tok", sent.get("tokens", [])):
                            if token.get("p") in self.pos_tags:
                                lemma = (
                                    token["l"] if "l" in token else token["t"]
                                ).lower()
                                if len(lemma) >= self.min_length:
                                    current_tokens.append(lemma)

                except (json.JSONDecodeError, KeyError) as e:
                    log.warning(f"Skipping line {line_num}: {e}")
                    continue

            # Yield the last document
            if current_doc is not None and current_lang is not None:
                yield current_doc, current_lang, current_tokens


def main(args: Optional[List[str]] = None) -> None:
    """
    Main function to run the Token Extractor.

    Args:
        args: Command-line arguments (uses sys.argv if None)
    """
    # Load environment variables from .env file
    load_dotenv()

    options: argparse.Namespace = parse_arguments(args)

    processor: TokenExtractor = TokenExtractor(
        input_file=options.input,
        output_file=options.output,
        pos_tags=set(options.pos_tags),
        languages=set(options.languages) if options.languages else None,
        min_length=options.min_length,
        log_level=options.log_level,
        log_file=options.log_file,
    )

    # Log the parsed options after logger is configured
    log.info("%s", options)

    processor.run()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log.error(f"Processing error: {e}", exc_info=True)
        sys.exit(2)
