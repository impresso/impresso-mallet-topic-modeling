#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import argparse
import os
import sys
import codecs
import pandas as pd
import math
try:
    import ujson as json  # type: ignore
except ImportError:
    import json
import re
import collections
from impresso_cookbook import setup_logging  # type: ignore

"""
Module for XXX

Matrix File format: ID FILE {TOPIC_ID PROBABILITY *}

0	file:/mnt/storage/karr/projects/climpresso/topicmodeling/letemps/letemps_prep/GDL/1940/GDL-1940-03-26-a-i0009.txt	1.8214936247723133E-4	0.0020036429872495446	1.8214936247723133E-4	1.8214936247723133E-4	0.14043715846994534	1.8214936247723133E-4	1.8214936247723133E-4	1.8214936247723133E-4	1.8214936247723133E-4	0.007468123861566484	1.8214936247723133E-4	0.0020036429872495446	1.8214936247723133E-4	1.8214936247723133E-4	1.8214936247723133E-4	1.8214936247723133E-4	1.8214936247723133E-4	0.009289617486338797	1.8214936247723133E-4	0.003825136612021858	1.8214936247723133E-4	1.8214936247723133E-4	1.8214936247723133E-4	1.8214936247723133E-4	0.06211293260473589	1.8214936247723133E-4	1.8214936247723133E-4	1.8214936247723133E-4	0.009289617486338797	1.8214936247723133E-4	0.05846994535519126	0.15683060109289618	1.8214936247723133E-4	1.8214936247723133E-4	0.0020036429872495446	0.0785063752276867	0.07486338797814208	1.8214936247723133E-4	1.8214936247723133E-4	0.003825136612021858	1.8214936247723133E-4	1.8214936247723133E-4	0.11311475409836066	0.26429872495446266	1.8214936247723133E-4	1.8214936247723133E-4	1.8214936247723133E-4	1.8214936247723133E-4	1.8214936247723133E-4	0.005646630236794172
1	file:/mnt/storage/karr/projects/climpresso/topicmodeling/letemps/letemps_prep/GDL/1940/GDL-1940-07-13-a-i0008.txt	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406	0.030434782608695653	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406	0.610144927536232	0.0014492753623188406	0.030434782608695653	0.24782608695652175	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406	0.01594202898550725	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406	0.0014492753623188406



Sparse File format: ID FILE { TOPIC_ID PROBABILITY }*


0	actionfem-1936-02-15-a-i0001	56	0.3638636363636785	653	0.060833333333340366	718	0.035580808080812196	551	0.035580808080812196	98	0.02042929292
9295288	371	0.015378787878789655	965	0.015378787878789654	831	0.010328282828284022	713	0.010328282828284022	148	0.010328282828284022	351	0.01032828282


"""


sys.stderr = codecs.getwriter("UTF-8")(sys.stderr.buffer)
sys.stdout = codecs.getwriter("UTF-8")(sys.stdout.buffer)
sys.stdin = codecs.getreader("UTF-8")(sys.stdin.buffer)

log = logging.getLogger(__name__)

# def normalize(r):
#    r


def format_explicit_topic_id(tpid, topic_model, lang, topic_count, separator="_"):
    return f"{topic_model}{separator}tp{tpid:0{math.ceil(math.log(topic_count,10))}d}{separator}{lang}"


def mallet_topic_word_weights_file2topic_assignment(
    filename,
    eps=0.005,
    options=None,
    lang="unk",
    topic_model="tm000",
    numeric_topic_ids=False,
):
    """ """
    #    df = pd.read_table(filename, sep='\t',header=None,names=["ID",'FILE','SCORE'], encoding="utf-8")
    df = pd.read_table(
        filename, sep="\t", header=None, names=None, encoding="utf-8", comment="#"
    )
    # we sometimes have duplicate entries in our output. We take the first instance.
    ci_ref_stats = collections.Counter()
    for row in df.itertuples(index=False, name=None):
        ci_ref = re.sub(
            r"^(.+?/)?([^/]+?-\d{4}-\d{2}-\d{2}-\w-i\d{4})[^/]*$", r"\2", row[1]
        )
        if ci_ref in ci_ref_stats:
            ci_ref_stats["DUPLICATE_COUNT"] += 1
            continue
        else:
            ci_ref_stats[ci_ref] = 1
        topics = row[2:]
        topic_count = len(topics)
        if numeric_topic_ids:
            topics = [
                {"t": t, "p": round(p, math.ceil(abs(math.log(eps, 10))) + 1)}
                for t, p in enumerate(topics)
                if p >= eps
            ]
        else:
            topics = [
                {
                    "t": format_explicit_topic_id(t, topic_model, lang, topic_count),
                    "p": round(p, math.ceil(abs(math.log(eps, 10))) + 1),
                }
                for t, p in enumerate(topics)
                if p >= eps
            ]
        topics.sort(key=lambda topic: topic["p"], reverse=True)

        topic_assignment = {
            "topic_model": topic_model,
            "topic_count": topic_count,
            "lang": lang,
            "ci_ref": ci_ref,
            "topics": topics,
            "min_p": eps,
        }
        print(json.dumps(topic_assignment, ensure_ascii=False, separators=(",", ":")))

    log.info("DUPLICATE-COUNT: %d", ci_ref_stats["DUPLICATE_COUNT"])
    return


def process(options):
    """
    Do the processing
    """
    mallet_topic_word_weights_file2topic_assignment(
        options.args[0],
        lang=options.lang,
        eps=options.topic_assignment_threshold,
        topic_model=options.topic_model,
        numeric_topic_ids=options.numeric_topic_ids,
    )


def main():
    """
    Invoke this module as a script
    """
    parser = argparse.ArgumentParser(
        usage="%(prog)s [OPTIONS] [ARGS...]",
        description="Calculate something",
        epilog="Contact simon.clematide@uzh.ch",
    )
    parser.add_argument("--version", action="version", version="0.99")
    parser.add_argument(
        "-l",
        "--logfile",
        "--log-file",
        dest="log_file",
        help="Write log to FILE",
        metavar="FILE",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: %(default)s)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        dest="quiet",
        default=False,
        help="do not print status messages to stderr",
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        dest="debug",
        default=False,
        help="print debug information",
    )
    parser.add_argument(
        "-L",
        "--lang",
        action="store",
        dest="lang",
        default="und",  # https://en.wikipedia.org/wiki/List_of_ISO_639-2_codes undetermined language
        help="iso 639 language code",
    )
    parser.add_argument(
        "-M",
        "--topic_model",
        action="store",
        dest="topic_model",
        default="tm000",
        help="topic model identifier, e.g. tm001",
    )
    parser.add_argument(
        "-N",
        "--numeric_topic_ids",
        action="store_true",
        dest="numeric_topic_ids",
        default=False,
        help="only store the numeric ids of the topics in the topic assignment",
    )
    parser.add_argument(
        "-T",
        "--topic_assignment_threshold",
        action="store",
        dest="topic_assignment_threshold",
        default=0.005,
        type=float,
        help="minimal probability for inclusion in the output",
    )

    parser.add_argument("args", nargs="*")
    options = parser.parse_args()
    log_level = "DEBUG" if options.debug else options.log_level
    setup_logging(log_level, options.log_file, logger=log)
    log.info("%s", options)

    try:
        process(options)
    except Exception as exc:
        log.error("Could not process data: %s", exc, exc_info=True)
        if options.debug:
            raise
        sys.exit(1)


if __name__ == "__main__":
    main()
