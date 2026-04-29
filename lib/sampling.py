#!/usr/bin/python
"""
script to filter texts with the help of a frequency distribution file --> using python 3.6!
"""

import codecs
import argparse
import random

__author__ = "Phillip Ströbel"
__email__ = "pstroebel@cl.uzh.ch"
__organisation__ = "Institute of Computational Linguistics, University of Zurich"
__copyright__ = "UZH, 2018"
__status__ = "development"

random.seed(42)

def filter(jsonfile):
    """
    text file
    :param jsonfile:
    :return:
    """

    input_file = codecs.open(jsonfile, 'r', 'utf-8')

    for_sampling = list()

    for line in input_file.readlines():
        try:
            aid, dummy, text = zip(line.strip().split('\t'))
            if args.maximumLength > len(text[0].split(' ')) >= args.articleLength:
                for_sampling.append('%s\t%s\t%s' % (aid[0], dummy[0], text[0]))
        except ValueError:
            print('Not enough columns for ', line)

    try:
        sampled = random.sample(for_sampling, args.sample)
    except ValueError:
        sampled = for_sampling

    with codecs.open('%s' % args.outputFile, 'a', 'utf-8') as outfile:
        for article in sampled:
            outfile.write('%s\n' % article)

if __name__ == '__main__':
    argparser = argparse.ArgumentParser()
    argparser.add_argument('-i', '--inputFile', help="mallet input file")
    argparser.add_argument('-o', '--outputFile', help="path to file to which sampled articles are saved")
    argparser.add_argument('-a', '--articleLength', help="threshold (int), minimum number of words for article to be processed", type=int, required=False)
    argparser.add_argument('-m', '--maximumLength', help="threshold (int), maximum number of words for article to be processed", type=int)
    argparser.add_argument('-s', '--sample', help="randomly sample specific amount of articles", type=int, required=False)
    args = argparser.parse_args()

    filter(args.inputFile)