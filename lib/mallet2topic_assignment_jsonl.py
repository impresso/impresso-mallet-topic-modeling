#!/usr/bin/env python3

import logging
import argparse
import math
try:
    import ujson as json  # type: ignore
except ImportError:
    import json
import re
import collections

from dotenv import load_dotenv
from smart_open import open

try:
    from impresso_cookbook import get_transport_params  # type: ignore
except ImportError:
    def get_transport_params(path: str) -> dict:
        return {}


def read_tsv_generator(filename):
    """
    Generator to read a TSV file line by line, yielding values as a list.

    Args:
        filename (str): Path to the input TSV file.

    Yields:
        list: A list of values from each non-comment line in the TSV file.
    """
    line_count = 0
    with open(filename, "r", encoding="utf-8", transport_params=get_transport_params(filename)) as file:
        for line in file:
            line_count += 1
            if not line.startswith("#"):
                yield line.strip().split("\t")
            if line_count % 1000 == 0:
                logging.info(f"Processed {line_count} lines.")


def format_topic_id(tpid, topic_model, lang, topic_count, separator="_"):
    """
    Format the topic ID with a given template.

    Args:
        tpid (int): Topic ID.
        topic_model (str): Topic model identifier.
        lang (str): Language code.
        topic_count (int): Total number of topics.
        separator (str): Separator for the topic ID components.

    Returns:
        str: Formatted topic ID.
    """
    return f"{topic_model}{separator}tp{tpid:0{math.ceil(math.log10(topic_count))}d}{separator}{lang}"


def parse_matrix_file(row, eps, lang, topic_model, numeric_topic_ids):
    ci_ref = re.sub(
        r"^(.+?/)?([^/]+?-\d{4}-\d{2}-\d{2}-\w-i\d{4})[^/]*$", r"\2", row[1]
    )

    topics = row[2:]
    topic_count = len(topics)
    if numeric_topic_ids:
        topics = [
            {"t": t, "p": round(fp, math.ceil(abs(math.log10(eps))) + 1)}
            for t, p in enumerate(topics)
            if (fp := float(p)) >= eps
        ]
    else:
        topics = [
            {
                "t": format_topic_id(t, topic_model, lang, topic_count),
                "p": round(fp, math.ceil(abs(math.log10(eps))) + 1),
            }
            for t, p in enumerate(topics)
            if (fp := float(p)) >= eps
        ]

    return {
        "topic_model": topic_model,
        "topic_count": topic_count,
        "lang": lang,
        "ci_ref": ci_ref,
        "topics": topics,
        "min_p": eps,
    }


def parse_sparse_file(row, eps, lang, topic_model, numeric_topic_ids, topic_count=None):
    ci_ref = re.sub(
        r"^(.+?/)?([^/]+?-\d{4}-\d{2}-\d{2}-\w-i\d{4})[^/]*$", r"\2", row[1]
    )

    topic_pairs = row[2:]
    topics = []
    for i in range(0, len(topic_pairs), 2):
        t = int(topic_pairs[i])
        p = float(topic_pairs[i + 1])
        if p >= eps:
            if numeric_topic_ids:
                topics.append(
                    {"t": t, "p": round(p, math.ceil(abs(math.log10(eps))) + 1)}
                )
            else:
                topics.append(
                    {
                        "t": format_topic_id(
                            t, topic_model, lang, len(topic_pairs) // 2
                        ),
                        "p": round(p, math.ceil(abs(math.log10(eps))) + 1),
                    }
                )

    return {
        "topic_model": topic_model,
        "topic_count": topic_count,
        "lang": lang,
        "ci_ref": ci_ref,
        "topics": topics,
        "min_p": eps,
    }


def parse_mallet_file(
    filename,
    eps=0.005,
    lang="unk",
    topic_model="tm000",
    numeric_topic_ids=False,
    format_type="matrix",
    topic_count=None,
):
    """
    Process the Mallet topic word weights file and yield topic assignments in JSON format.

    Args:
        filename (str): Path to the input file.
        eps (float): Minimum probability for inclusion in the output.
        lang (str): Language code.
        topic_model (str): Topic model identifier.
        numeric_topic_ids (bool): Use numeric topic IDs if True.
        format_type (str): Format of the input file, either 'matrix' or 'sparse'.

    Yields:
        dict: Topic assignment for each row in the input file.
    """
    ci_ref_stats = collections.Counter()

    for row in read_tsv_generator(filename):
        ci_ref = re.sub(
            r"^(.+?/)?([^/]+?-\d{4}-\d{2}-\d{2}-\w-i\d{4})[^/]*$", r"\2", row[1]
        )
        if ci_ref in ci_ref_stats:
            ci_ref_stats["DUPLICATE_COUNT"] += 1
            continue
        ci_ref_stats[ci_ref] = 1

        if format_type == "matrix":
            yield parse_matrix_file(row, eps, lang, topic_model, numeric_topic_ids)
        elif format_type == "sparse":
            yield parse_sparse_file(
                row, eps, lang, topic_model, numeric_topic_ids, topic_count=topic_count
            )

    logging.info("DUPLICATE-COUNT: %d", ci_ref_stats["DUPLICATE_COUNT"])


def process_file(options):
    """
    Process the file based on the given command line options.

    Args:
        options (argparse.Namespace): Command line arguments.
    """
    for topic_assignment in parse_mallet_file(
        options.args[0],
        eps=options.topic_assignment_threshold,
        lang=options.lang,
        topic_model=options.topic_model,
        numeric_topic_ids=options.numeric_topic_ids,
        format_type=options.format_type,
        topic_count=options.topic_count,
    ):
        print(json.dumps(topic_assignment, ensure_ascii=False, separators=(",", ":")))


def setup_logging(options):
    """
    Set up logging configuration based on command line options.

    Args:
        options (argparse.Namespace): Command line arguments.
    """
    log_level = logging.DEBUG if options.debug else logging.INFO
    logging.basicConfig(
        level=log_level, filename=options.logfile if options.logfile else None
    )


def main():
    """
    Main entry point for the script.
    """
    load_dotenv()  # Load S3 credentials from .env file
    
    parser = argparse.ArgumentParser(
        usage="%(prog)s [OPTIONS] [ARGS...]",
        description="Calculate topic assignments from topic modeling output.",
        epilog="Contact simon.clematide@uzh.ch for more information.",
    )

    parser.add_argument("--version", action="version", version="0.99")
    parser.add_argument("-l", "--logfile", help="Write log to FILE", metavar="FILE")
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Do not print status messages to stderr",
    )
    parser.add_argument(
        "-d", "--debug", action="store_true", help="Print debug information"
    )
    parser.add_argument("-L", "--lang", default="und", help="ISO 639 language code")
    parser.add_argument(
        "-M",
        "--topic_model",
        default="tm000",
        help="Topic model identifier, e.g., tm001",
    )
    parser.add_argument(
        "-N",
        "--numeric_topic_ids",
        action="store_true",
        help="Use numeric topic IDs in the topic assignment",
    )
    parser.add_argument(
        "-T",
        "--topic_assignment_threshold",
        type=float,
        default=0.005,
        help="Minimum probability for inclusion in the output",
    )
    parser.add_argument(
        "-F",
        "--format_type",
        choices=["matrix", "sparse"],
        default="matrix",
        help="Format of the input file: 'matrix' or 'sparse'",
    )
    parser.add_argument(
        "--topic_count",
        type=int,
        help=(
            "Needed if the format type is 'sparse' and the topic count is not given in"
            " the file"
        ),
    )
    parser.add_argument("args", nargs="*")

    options = parser.parse_args()
    if options.format_type == "sparse" and not options.topic_count:
        parser.error(
            "The --topic_count option is required when using the 'sparse' format"
        )
    setup_logging(options)

    try:
        process_file(options)
    except Exception as e:
        logging.error("Processing failed: %s", e)
        if options.debug:
            raise


if __name__ == "__main__":
    main()
