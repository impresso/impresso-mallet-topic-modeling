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
from impresso_cookbook import get_transport_params  # type: ignore

# Load S3 credentials from .env file at module level
load_dotenv()


CI_REF_RE = re.compile(r"^(.+?/)?([^/]+?-\d{4}-\d{2}-\d{2}-\w-i\d{4})[^/]*$")


def normalize_ci_ref(value):
    return re.sub(CI_REF_RE, r"\2", value)


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


def read_text_by_ci_ref(filename):
    text_by_ci_ref = {}
    for row in read_tsv_generator(filename):
        if len(row) < 3:
            continue
        text_by_ci_ref[normalize_ci_ref(row[0])] = row[2]
    return text_by_ci_ref


def read_topic_words(filename, word_count=4):
    words_by_topic = {}
    for row in read_tsv_generator(filename):
        if len(row) < 3:
            continue
        try:
            topic_id = int(row[0])
        except ValueError:
            logging.warning("Skipping topickeys row with non-numeric topic id: %s", row)
            continue
        words_by_topic[topic_id] = row[2].split()[:word_count]
    return words_by_topic


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


def topic_entry(topic_id, probability, eps, lang, topic_model, topic_count, numeric_topic_ids, topic_words):
    entry = {
        "t": (
            topic_id
            if numeric_topic_ids
            else format_topic_id(topic_id, topic_model, lang, topic_count)
        ),
        "p": round(probability, math.ceil(abs(math.log10(eps))) + 1),
    }
    if topic_words is not None:
        entry["words"] = topic_words.get(topic_id, [])
    return entry


def parse_matrix_file(row, eps, lang, topic_model, numeric_topic_ids, topic_words=None):
    ci_ref = normalize_ci_ref(row[1])

    topics = row[2:]
    topic_count = len(topics)
    topics = [
        topic_entry(t, fp, eps, lang, topic_model, topic_count, numeric_topic_ids, topic_words)
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


def parse_sparse_file(
    row,
    eps,
    lang,
    topic_model,
    numeric_topic_ids,
    topic_count=None,
    topic_words=None,
):
    ci_ref = normalize_ci_ref(row[1])

    topic_pairs = row[2:]
    topics = []
    inferred_topic_count = topic_count or len(topic_pairs) // 2
    for i in range(0, len(topic_pairs), 2):
        t = int(topic_pairs[i])
        p = float(topic_pairs[i + 1])
        if p >= eps:
            topics.append(
                topic_entry(
                    t,
                    p,
                    eps,
                    lang,
                    topic_model,
                    inferred_topic_count,
                    numeric_topic_ids,
                    topic_words,
                )
            )

    return {
        "topic_model": topic_model,
        "topic_count": inferred_topic_count,
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
    text_by_ci_ref=None,
    topic_words=None,
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
        ci_ref = normalize_ci_ref(row[1])
        if ci_ref in ci_ref_stats:
            ci_ref_stats["DUPLICATE_COUNT"] += 1
            continue
        ci_ref_stats[ci_ref] = 1

        if format_type == "matrix":
            assignment = parse_matrix_file(
                row,
                eps,
                lang,
                topic_model,
                numeric_topic_ids,
                topic_words=topic_words,
            )
        elif format_type == "sparse":
            assignment = parse_sparse_file(
                row,
                eps,
                lang,
                topic_model,
                numeric_topic_ids,
                topic_count=topic_count,
                topic_words=topic_words,
            )
        else:
            continue

        if text_by_ci_ref is not None:
            assignment["original_text"] = text_by_ci_ref.get(ci_ref)
        yield assignment

    logging.info("DUPLICATE-COUNT: %d", ci_ref_stats["DUPLICATE_COUNT"])


def process_file(options):
    """
    Process the file based on the given command line options.

    Args:
        options (argparse.Namespace): Command line arguments.
    """
    text_by_ci_ref = (
        read_text_by_ci_ref(options.text_tsv) if options.text_tsv else None
    )
    topic_words = (
        read_topic_words(options.topic_keys, word_count=options.topic_key_word_count)
        if options.topic_keys
        else None
    )
    for topic_assignment in parse_mallet_file(
        options.args[0],
        eps=options.topic_assignment_threshold,
        lang=options.lang,
        topic_model=options.topic_model,
        numeric_topic_ids=options.numeric_topic_ids,
        format_type=options.format_type,
        topic_count=options.topic_count,
        text_by_ci_ref=text_by_ci_ref,
        topic_words=topic_words,
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
    parser.add_argument(
        "--text-tsv",
        help="Optional TSV with document id in column 1 and original text in column 3.",
    )
    parser.add_argument(
        "--topic-keys",
        help="Optional MALLET topic keys file used to add top words to each topic.",
    )
    parser.add_argument(
        "--topic-key-word-count",
        type=int,
        default=4,
        help="Number of top words to include per topic when --topic-keys is provided.",
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
