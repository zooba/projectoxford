# Main functionality is from:
#   https://github.com/Microsoft/ProjectOxford-ClientSDK/blob/master/Emotion/Python/Jupyter%20Notebook/Emotion%20Analysis%20Example.ipynb

import time, requests, cv2, operator
import matplotlib.pyplot as plt
import numpy as np

from .utils import image_to_binary
from .variables import EMOTION_ENDPOINT, MAX_NUM_RETRIES


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


    def _renderResultOnImage(self, result, img):
        """
            Display the obtained results onto the input image
        """

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


    def process_image(self, img_path, local=True, show=False):
        """
            Processes emotions in image.

            Parameters:
                img_path: Path to target image either in local form '/path/to/image' or remote form 'http://path/to/image.jpg'
                local: Boolean flag to determine whether image is in local storage or not. Default is set to True (local).
                show: Boolean flag. If set JSON response is not returned and processed image is shown.
        """

        assert img_path is not None and isinstance(img_path, str), 'Image path should be a valid string.'
        assert isinstance(local, bool), 'Locality or Non-locality should a boolean attribute.'

        headers = dict()
        headers['Ocp-Apim-Subscription-Key'] = self.key
        return self._process_local_image(headers, img_path, show) if local else self._process_remote_image(headers, img_path, show)


    def _process_local_image(self, headers, img_path, show):
        """
            Processes emotions in local image.
        """

        headers['Content-Type'] = 'application/octet-stream'
        binary = image_to_binary(img_path)
        result = self._processRequest(None, binary, headers)
        if not show:
            return result
        self._show(result, bytearray(binary))

    def _process_remote_image(self, headers, img_url, show):
        """
            Processes emotions in remote image.
        """

        headers['Content-Type'] = 'application/json'
        json = {'url': img_url}
        result = self._processRequest(json, None, headers)
        if not show:
            return result
        self._show(result, bytearray(requests.get(img_url).content))


    def _show(self, result, content):
        """
            Shows the result of image processing.
        """

        arr = np.asarray(content, dtype=np.uint8)
        img = cv2.cvtColor(cv2.imdecode(arr, -1), cv2.COLOR_BGR2RGB)
        self._renderResultOnImage(result, img)
        ig, ax = plt.subplots(figsize=(15, 20))
        ax.imshow(img)
        plt.show()
