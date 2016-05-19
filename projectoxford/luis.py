#-------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation
# All rights reserved.
#
# Distributed under the terms of the MIT License
#-------------------------------------------------------------------------
'''Project Oxford Language Understanding Intelligent Service (LUIS)
Module

This module provides access to Project Oxford LUIS web services.

See https://www.projectoxford.ai/luis to start using LUIS and create a
deployed web service.
'''

import requests
import time
import urllib.parse as parse

class LuisClient(object):
    '''Provides access to a Project Oxford LUIS web service.

    LuisClient(url)

    url:
        The URL provided by LUIS for your service. This URL must be
        complete, including the trailing ``&q=``.
    '''
    def __init__(self, url):
        self.url = url
        if not url.endswith('&q='):
            raise ValueError('url is expected to end with "&q="')

    def query_raw(self, text):
        '''Queries the LUIS web service with the provided text and
        returns the complete response JSON as a dict.

        See https://www.luis.ai/Help for the schema of the response.

        text:
            The text to submit (maximum 500 characters).
        '''
        r = requests.get(self.url + parse.quote(text))
        r.raise_for_status()

        return r.json()

    def query(self, text):
        '''Queries the LUIS web service with the provided text and
        returns a 3-tuple containing the intent, a list of recognized
        entities, and a list of each entity's type.

        text:
            The text to submit (maximum 500 characters).
        '''
        r = self.query_raw(text)
        try:
            intent = r['intents'][0]['intent']
        except LookupError:
            raise ValueError('cannot determine intent')

        names = [e['entity'] for e in r['entities']]
        types = [e['type'] for e in r['entities']]
        return intent, names, types
