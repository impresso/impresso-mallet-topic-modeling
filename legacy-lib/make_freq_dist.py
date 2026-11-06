#!/usr/bin/python
"""
script to create freq dist over corpora --> using python 3.6!
"""

import operator
try:
    import ujson as json  # type: ignore
except ImportError:
    import json
import bz2
import os
import logging
import sys
from collections import defaultdict, Counter
import string
import argparse
import glob
from multiprocessing import Pool

from impresso_cookbook import setup_logging  # type: ignore

__author__ = "Phillip Ströbel"
__email__ = "pstroebel@cl.uzh.ch"
__organisation__ = "Institute of Computational Linguistics, University of Zurich"
__copyright__ = "UZH, 2018"
__status__ = "development"

PUNCT = string.punctuation
log = logging.getLogger(__name__)


def process(jsonfile):
    log.info("Processing file: %s", jsonfile)

    fname = jsonfile.split('/')[-1].split('.')[0]

    freq_dict = defaultdict(Counter)

    input_file = bz2.BZ2File(jsonfile, 'rb')

    tags = {'NOUN', 'PROPN'}

    for line in input_file.readlines():
        json_line = json.loads(line)
        for sent in json_line['sents']:
            lang = sent['lg']
            try:
                for tok in sent['tok']:
                    if tok['p'] in tags and 'l' in tok:
                        if tok['l'][0] not in PUNCT:
                            if len(tok['l']) > 2:
                                freq_dict[lang][tok['l']] += 1

            except KeyError:
                continue

    for lang, tok_count in freq_dict.items():
        if lang in args.langs:
            outfile = open(os.path.join(args.outputfolder, '%s.%s.txt' % (lang, fname)), 'w')
            for tok, count in sorted(tok_count.items(), key=operator.itemgetter(1), reverse=True):
                outfile.write(str(count) + '\t' + tok + '\n')
            outfile.close()

if __name__ == '__main__':

    argumentparser = argparse.ArgumentParser()
    argumentparser.add_argument('-f', '--files', help='folder where collections within which we find json.bz2 files')
    argumentparser.add_argument('-o', '--outputfolder', help='output folder for freqdist', type=str)
    argumentparser.add_argument('-l', '--langs', help='languages to extract', type=str, nargs='+')
    argumentparser.add_argument('-c', '--cores', help='number of cores', type=int)
    argumentparser.add_argument("--log-file", dest="log_file", help="Write log to FILE", metavar="FILE")
    argumentparser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: %(default)s)",
    )
    args = argumentparser.parse_args()
    setup_logging(args.log_level, args.log_file, logger=log)
    log.info("%s", args)

    files = glob.glob('%s/*/*.bz2' % args.files)


    try:
        with Pool(processes=args.cores) as pool:
            pool.map(process, files)
            pool.close()
    except Exception as exc:
        log.error("Processing error: %s", exc, exc_info=True)
        sys.exit(1)
