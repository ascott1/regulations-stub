#!/usr/bin/env python
from __future__ import print_function

import sys
import os
import argparse
import logging
import urlparse
import json

import requests

from bs4 import BeautifulSoup

logging.basicConfig(
        format='%(asctime)s %(levelname)s: %(message)s', 
        datefmt='%m/%d/%Y %I:%M:%S %p')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handle_error(response):
    try:
        soup = BeautifulSoup(response.text, 'html.parser')

        exception = soup.select("#summary h1")[0].text
        exception_value = soup.select(
                "#summary .exception_value")[0].text

        logger.error("error sending {}: {}, {}".format(
            response.status_code, exception, exception_value))
    except:
        logger.error("error getting {}: {} {}".format(
            response.request.url, response.status_code, response.reason))
    


def determine_regulation_paths(api_base, regulation):
    """
    Discover all JSON paths in the `api_base` belonging to the given
    `regulation`. Returns a list of paths relative to api_base.
    """

    # To determine which files we need for this regulation, we need to 
    # know what notices it has. We have to query /regulation first, get
    # the list of notices, then we should be able to assembly the rest
    # of the paths.
    reg_url = urlparse.urljoin(api_base, 'regulation/' + regulation)
    r = requests.get(reg_url)
    if r.status_code != 200:
        handle_error(r)

    # This should be the list of notices that make up this regulation
    notices = [d['version'] for d in r.json()['versions']]

    # We need to assemble paths for the following:
    #   regulation/
    #       [regulation part number]/
    #           [notice number]
    #           ...
    #   notice/
    #       [notice number]
    #       ...
    #   layer/
    #       [layer name]/
    #           [regulation part number]/
    #               [notice number]
    #               ...
    #   diff/
    #       [regulation part number]/
    #           [notice number]/
    #               [notice number]
    #               ...

    regulation_paths = []
    
    # Get the regulation JSON 
    logger.info("generating paths for regulation {}...".format(regulation))
    regulation_base = os.path.join('regulation', regulation)
    regulation_paths.extend([os.path.join(regulation_base, n) 
        for n in notices])

    # Get notice JSON
    logger.info("generating notice paths for regulation {}...".format(regulation))
    regulation_paths.extend([os.path.join('notice', n) for n in notices])
    
    # Get layer JSON
    logger.info("generating layer paths for regulation {}...".format(regulation))
    for layer in [
            'analyses', 
            'external-citations', 
            'formatting',
            'graphics', 
            'internal-citations', 
            'interpretations', 
            'keyterms',
            'meta', 
            'paragraph-markers', 
            'terms', 
            'toc']:
        regulation_paths.extend([os.path.join('layer', layer, regulation, n) 
            for n in notices])

    # Get diff JSON
    logger.info("generating diff paths for regulation {}...".format(regulation))
    for notice in notices:
        regulation_paths.extend([os.path.join('diff', regulation,
            notice, n) for n in notices])

    return regulation_paths


def get_from_server(api_base, stub_base, path):
    """
    Get the file at the given `api_base` and save to `stub_base`. Path
    components will be appended to the `api_base` and are presumed to
    match.
    """

    reg_url = urlparse.urljoin(api_base, path)
    r = requests.get(reg_url)

    if r.status_code != 200:
        return handle_error(r)

    file_path = os.path.join(stub_base, path)
    logger.info('getting {}'.format(file_path))

    # Check that the dirname exists. create it if not
    directory = os.path.dirname(file_path)
    if not os.path.exists(directory):
        os.makedirs(directory)

    # Write out the file
    with open(file_path, 'w') as outfile:
        json.dump(r.json(), outfile)


if __name__ == '__main__':

    parser = argparse.ArgumentParser()

    # We can get from the regulations-core API 
    parser.add_argument('-a', '--api-base', action='store',
            help='the regulations-core API URL')

    # We need to know where the JSON is going to 
    parser.add_argument('-s', '--stub-base', action='store',
            default=os.path.join(os.getcwd(), 'stub'), 
            help='the base filesystem path for regulations JSON (default: ./stub)')

    # We need to know what we're fetching, either a whole regulation's
    # worth of JSON or a specific file or files
    parser.add_argument('-r', '--regulation', nargs='?', action='store',
            help='the specific regulation part number to get (eg: 1026)')
    parser.add_argument('-p', '--paths', nargs='*', action='store',
            default=[], help='specific JSON paths to get')

    args = parser.parse_args()

    # We need a destination
    if args.api_base is None:
        logger.error("ERROR: -a api_base is required.")
        parser.print_help()
        sys.exit(1)

    if args.regulation is not None:
        # If we're going to fetch all the JSON for a single regulation, 
        # we need to fetch those paths.
        args.paths = determine_regulation_paths(args.api_base, args.regulation)

    else:
        logger.error("no paths or regulation to get. Use -r or -p to specify.")
        parser.print_help()
        sys.exit(1)

    [get_from_server(args.api_base, args.stub_base, f) for f in args.paths]
