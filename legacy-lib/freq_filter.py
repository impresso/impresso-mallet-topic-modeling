#!/usr/bin/python
"""
script to filter texts with the help of a frequency distribution file --> using python 3.6!
"""

import codecs
try:
    import ujson as json  # type: ignore
except ImportError:
    import json
import bz2
import argparse
import logging
import random
import glob
import sys
from collections import defaultdict
from multiprocessing import Pool

from impresso_cookbook import setup_logging  # type: ignore

__author__ = "Phillip Ströbel"
__email__ = "pstroebel@cl.uzh.ch"
__organisation__ = "Institute of Computational Linguistics, University of Zurich"
__copyright__ = "UZH, 2018"
__status__ = "development"

random.seed(42)
log = logging.getLogger(__name__)

def filter(jsonfile):
    """
    text file
    :param jsonfile:
    :return:
    """
    filtered_texts = defaultdict(str)

    try:

        input_file = bz2.BZ2File(jsonfile, 'r')

        for line in input_file.readlines():
            json_line = json.loads(line)

            article_id = json_line['id']
            article = list()
            for sent in json_line['sents']:
                lang = sent['lg']
                if lang == args.language:
                    for index, tok in enumerate(sent['tok']):
                        if 'l' in tok and 'p' in tok:
                            if not lemma_dict:
                                article.append(tok['l'])
                            else:
                                if tok['p'] in args.posFilter and tok['t'] in filter_words and tok['l'] \
                                        not in negative_lemmas and tok['l'].lower() \
                                        not in negative_lemmas and len(tok['l']) > 2:
                                    # if args.multiwordexpressions is True:
                                    #     if 'e' in tok.keys() and tok['e'][0] == 'B':
                                    #         possible_multiword_proper_noun = list()
                                    #         possible_multiword_proper_noun.append(tok['t'])
                                    #         for i, t in enumerate(sent['tok'][index+1:]):
                                    #             if 'e' in t.keys() and t['e'][0] == 'I':
                                    #                 possible_multiword_proper_noun.append(t['t'])
                                    #             else:
                                    #                 article.append('_'.join(possible_multiword_proper_noun))
                                    #                 break
                                    #     elif 'e' in tok.keys() and tok['e'][0] == 'I':
                                    #         continue
                                    #     else:
                                    #         if tok['t'] in lemma_dict.keys():
                                    #             if lang == 'fr':
                                    #                 try:
                                    #                     article.append(lemma_dict[tok['l']][0])
                                    #                 except IndexError:
                                    #                     print('Could not append token %s to text.' % tok['t'])
                                    #             else:
                                    #                 article.append(lemma_dict[tok['l']])
                                    # else:
                                    if tok['t'] in lemma_dict.keys():
                                        if lang == 'fr':
                                            try:
                                                article.append(lemma_dict[tok['l']][0])
                                            except IndexError:
                                                log.warning("Could not append token %s to text.", tok['t'])
                                        else:
                                            article.append(lemma_dict[tok['l']])



                    filtered_texts[article_id] = ' '.join(str(t) for t in article)


        with codecs.open('%s' % args.outputFile, 'a', 'utf-8') as outfile:
            for aid, text in filtered_texts.items():
                outfile.write('%s\tDUMMY\t%s\n' % (aid, text))

    except (EOFError, OSError) as e:
        log.error("Could not process %s: %s", jsonfile, e, exc_info=True)

if __name__ == '__main__':
    argparser = argparse.ArgumentParser()
    argparser.add_argument('-i', '--inputFolder', help="path to jsonl.bz2 files for input")
    argparser.add_argument('-o', '--outputFile', help="path to file to which articles are saved")
    argparser.add_argument('-f', '--freqDist', help="freq dist file in format FREQ TAB WORD")
    argparser.add_argument('-l', '--lowerBound', help="threshold (int), all words below are ignored", type=int)
    argparser.add_argument('-u', '--upperBound', help="threshold (int), allwords above are ignored", type=int)
    argparser.add_argument('-p', '--posFilter', help="PoS tags which should be included in the filtered text", nargs='+', choices=['NOUN', 'PROPN', 'VERB', 'ADJ' ])
    argparser.add_argument('-n', '--negativeList', help="lemmas which should be excluded")
    argparser.add_argument('-L', '--language', help="ISO language two letter, e.g. 'de'")
    argparser.add_argument('-N', '--lemmatisation', help="lemmas to be included", required=False)
    argparser.add_argument('-c', '--cores', help="number of cores to use", type=int)
    argparser.add_argument('-a', '--addLemmas', help="additional lemma lexicon tok\tpos\tlemma")
    argparser.add_argument("--log-file", dest="log_file", help="Write log to FILE", metavar="FILE")
    argparser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: %(default)s)",
    )
    #argparser.add_argument('-m', '--multiwordexpressions', help="define whether multiword expressions should be recognised", default=False, type=bool)
    args = argparser.parse_args()
    setup_logging(args.log_level, args.log_file, logger=log)
    log.info("%s", args)

    #print(args.multiwordexpressions)

    files = glob.glob('%s/*/*.bz2' % args.inputFolder)

    filter_words = set()

    with codecs.open(args.freqDist, 'r', 'utf-8') as f:
        for line in f:
            freq, tok = line.strip().split('\t')
            if args.lowerBound < int(freq) < args.upperBound:
                filter_words.add(tok)

    negative_lemmas = set()

    with codecs.open(args.negativeList, 'r', 'utf-8') as n:
        for line in n:
            negative_lemmas.add(line.strip())

    lemma_dict = defaultdict(str)
    if args.lemmatisation.endswith('.txt'):  # we assume tsv output from gertwol
        with codecs.open(args.lemmatisation, 'r', 'utf-8') as g:
            for line in g:
                tok, pos, lemma = line.strip().split('\t')
                if tok.isalnum():
                    lemma_dict[tok] = lemma
    else:  # we expect a json file
        lemmafile = json.load(open(args.lemmatisation, 'r'))
        for upos in lemmafile:
            if upos in args.posFilter:
                for tok, lemma in lemmafile[upos].items():
                    lemma_dict[tok] = lemma

    with open(args.addLemmas, 'r') as addlemmas:
        for line in addlemmas:
            try:
                tok, pos, lemma = line.strip().split('\t')
                if tok.isalnum():
                    lemma_dict[tok] = lemma
            except ValueError:
                continue

    try:
        with Pool(processes=args.cores) as pool:
            pool.map(filter, files)
            pool.close()
    except Exception as exc:
        log.error("Processing error: %s", exc, exc_info=True)
        sys.exit(1)
