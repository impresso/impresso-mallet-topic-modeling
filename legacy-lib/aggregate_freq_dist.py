#!/usr/bin/python
"""
script to create freq dist over corpora --> using python 3.6!
"""

import operator
import os
import glob
import argparse
import logging
import sys
from collections import defaultdict

from impresso_cookbook import setup_logging  # type: ignore


__author__ = "Phillip Ströbel"
__email__ = "pstroebel@cl.uzh.ch"
__organisation__ = "Institute of Computational Linguistics, University of Zurich"
__copyright__ = "UZH, 2018"
__status__ = "development"

log = logging.getLogger(__name__)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i",
        "--input-dir",
        default="resources/freqdists",
        help="Input directory containing frequency distribution files.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default="resources/aggregated",
        help="Output directory for aggregated frequency distributions.",
    )
    parser.add_argument("--log-file", dest="log_file", help="Write log to FILE", metavar="FILE")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: %(default)s)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    setup_logging(args.log_level, args.log_file, logger=log)
    log.info("%s", args)

    files = glob.glob('%s/*' % args.input_dir)
    freq_dist = defaultdict(lambda: defaultdict(int))

    for f in files:
        log.info("Processing file: %s", f)
        with open(f, 'r') as f_open:
            lines = f_open.readlines()
        lang = f.split('/')[-1].split('.')[0]
        for line in lines:
            count, token = zip(line.strip().split('\t'))
            freq_dist[lang][token[0]] += int(count[0])

    os.makedirs(args.output_dir, exist_ok=True)
    for language, freqs in freq_dist.items():
        output_path = os.path.join(args.output_dir, '%s.txt' % language)
        log.info("Writing %s", output_path)
        with open(output_path, 'w') as outfile:
            sorted_freq = sorted(freqs.items(), key=operator.itemgetter(1), reverse=True)
            for tok in sorted_freq:
                outfile.write('%s\t%s\n' % (str(tok[1]), tok[0]))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        log.error("Processing error: %s", exc, exc_info=True)
        sys.exit(2)
