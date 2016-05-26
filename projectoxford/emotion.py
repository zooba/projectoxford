#-------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation
# All rights reserved.
#
# Distributed under the terms of the MIT License
#-------------------------------------------------------------------------
'''Project Oxford Emotion Module

This module provides access to the Project Oxford Emotion APIs.

See https://www.projectoxford.ai/emotion to obtain an API key.
'''

import time, requests, os
from .endpoints import EMOTION_ENDPOINT


MAX_NUM_RETRIES = 10    # Maximum number of retries to fetch results.


def image_to_binary(img_path):
    """
        Returns contents of the given image in binary stream.
    """

    if img_path is None or not os.path.exists(img_path) or not isinstance(img_path, str):
        raise ValueError('Image path should be a valid string and pointing to an existing file.')

    with open(img_path, 'rb') as image_file:
        return image_file.read()


def check_rendering_requirements():
    """
        Checks to see if requirements for rendering result image are satisfied, If not
            informs user.
    """

    try:
        import numpy
    except ImportError:
        raise ImportError('Package numpy is not installed.')

    try:
        import matplotlib.pyplot
    except ImportError:
        raise ImportError('Package matplotlib is not installed.')

    try:
        import cv2
    except ImportError:
        raise ImportError('Package opencv for python is not installed')


class EmotionClient:
    """
        Provides access to the Project Oxford Emotion APIs.

            EmotionClient(key)

        key:
            The API key for your subscription. Visit https://www.projectoxford.ai/emotion to obtain one.
    """

    def __init__(self, key=None):
        assert key is not None or isinstance(key, str), 'API subscription key should be a valid string.'
        self.key = key


    def _processRequest(self, json, data, headers):
        """
            Helper function to process the request to Project Oxford

            Parameters:
                json: Used when processing images from its URL. See API Documentation
                data: Used when processing image read from disk. See API Documentation
                headers: Used to pass the key information and the data type request
        """

        retries, result = 0, None

        while True:
            response = requests.request('POST', EMOTION_ENDPOINT, json=json, data=data, headers=headers, params=None)
            if response.status_code == 429:
                print('POST Attempt Failed.\nMessage: {0}'.format(response.json()['error']['message']))
                if retries <= MAX_NUM_RETRIES:
                    time.sleep(1)
                    retries += 1
                    continue
                else:
                    raise RuntimeError('Maximum number of retries reached.')
            elif response.status_code == 200 or response.status_code == 201:
                if 'content-length' in response.headers and int(response.headers['content-length']) == 0:
                    result = None
                elif 'content-type' in response.headers and isinstance(response.headers['content-type'], str):
                    if 'application/json' in response.headers['content-type'].lower():
                        result = response.json() if response.content else None
                    elif 'image' in response.headers['content-type'].lower():
                        result = response.content
                return result
            else:
                raise RuntimeError('Error Code: {0}\nMessage: {1}'.format(response.status_code, response.json()['error']['message']))

    def _make_headers(self, local):
        """
            Makes correct HTTP headers for Emotion API call request.

            Parameters:
                local: Boolean flag to determine whether image is in local storage or not.

            Returns:
                A dictionary of HTTP headers for Emotion API call request.
        """

        headers = dict()
        headers['Ocp-Apim-Subscription-Key'] = self.key
        if local:
            headers['Content-Type'] = 'application/octet-stream'
        else:
            headers['Content-Type'] = 'application/json'
        return headers


    def process_image_from_path(self, img_path):
        """
            Processes emotions in local image.

            Parameters:
                img_path: path to local image, '/path/to/image'.

            Returns:
                EmotionResult object representing emotions present in target image.
        """

        assert img_path is not None and isinstance(img_path, str), 'Image path should be a valid string.'
        binary = image_to_binary(img_path)
        result = self._processRequest(None, binary, self._make_headers(local=True))
        return EmotionResult(result, bytearray(binary))


    def process_image_from_url(self, img_url):
        """
            Processes emotions in remote image.

            Parameters:
                img_url: path to remote image, 'http://example.com/path/to/image'.

            Returns:
                EmotionResult object representing emotions present in target image.
        """

        assert img_url is not None and isinstance(img_url, str), 'Image url should be a valid string.'
        result = self._processRequest({'url': img_url}, None, self._make_headers(local=False))
        return EmotionResult(result, bytearray(requests.get(img_url).content))


class EmotionResult:
    """
        Represents processed result of an image received from Project Oxford Emotion APIs.

            EmotionResult(raw_result, content)

        raw_result:
            Raw JSON result received from Project Oxford Emotion APIs.
        content:
            Content of the target image in bytearray format.
    """

    def __init__(self, raw_result, content):
        assert raw_result is not None, 'Raw result should not be None'
        assert content is not None, 'Image content should not be None'

        self.raw_result = raw_result
        self.content = content


    def __repr__(self):
        return str(self.raw_result)


    def get_raw_result(self):
        """
            Returns:
                Raw processed result of the given image.
        """

        return self.raw_result


    def get_strongest_emotion(self):
        """
            Returns:
                The strongest emotion in image or if there's multiple faces a list representing
                    strongest emotion in each face is returned.
        """

        num_faces, res = len(self.get_raw_result()), self.get_raw_result()
        if num_faces < 1:
            return None
        elif num_faces == 1:
            return max(res[0]['scores'], key=(lambda s: res[0]['scores'][s]))
        else:
            return [max(face['scores'], key=(lambda s: face['scores'][s])) for face in res]


    def render_emotion(self):
        """
            Renders emotion results on the target image.
        """

        check_rendering_requirements()

        import matplotlib.pyplot as plt
        import numpy as np

        arr = np.asarray(self.content, dtype=np.uint8)
        img = self._renderResultOnImage(self.raw_result, arr)
        ig, ax = plt.subplots(figsize=(15, 20))
        ax.imshow(img)
        plt.show()


    def _renderResultOnImage(self, result, arr):
        """
            Draws boxes and text representing each face's emotion.
        """

        import operator, cv2

        img = cv2.cvtColor(cv2.imdecode(arr, -1), cv2.COLOR_BGR2RGB)

        for currFace in result:
            faceRectangle = currFace['faceRectangle']
            cv2.rectangle(img,(faceRectangle['left'],faceRectangle['top']),
                               (faceRectangle['left']+faceRectangle['width'], faceRectangle['top'] + faceRectangle['height']),
                               color = (255,0,0), thickness = 5)

        for currFace in result:
            faceRectangle = currFace['faceRectangle']
            currEmotion = max(iter(currFace['scores'].items()), key=operator.itemgetter(1))[0]

            textToWrite = '{0}'.format(currEmotion)
            cv2.putText(img, textToWrite, (faceRectangle['left'],faceRectangle['top']-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,0,0), 1)

        return img
