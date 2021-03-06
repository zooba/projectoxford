projectoxford
=============

Python client library for [Project Oxford](https://www.projectoxford.ai/) APIs.

Microsoft Project Oxford is a collection of artificial intelligence tools made available as online services. This library provides easy use of the Project Oxford APIs from Python.

Currently only the speech recognition, synthesis and [LUIS](https://luis.ai/) APIs are implemented.

If you were using the previous version of this library, which only provided the vision APIs, install ``projectoxford<=0.2`` to continue to use that version.

# Table of Contents
1. [Installation](#installation)
2. [Speech API](#speech-api)
3. [Emotion API](#emotion-api)


## Installation
------------

To install, use pip:

```
pip install projectoxford
```

This library is in an early stage of development. We strongly recommend pinning all references to the specific version you are using.

## Speech API
---------------

To use text to speech or speech recognition, you'll need to [obtain a subscription key](https://www.projectoxford.ai/speech).

```python
from projectoxford.speech import SpeechClient
sc = SpeechClient("YOUR-KEY-GOES-HERE", gender='Male', locale='en-US')
```

You can use `sc.say_to_wav` to create a wave file containing synthesized speech, or `sc.say` to immediately play the speech.

```python
data = sc.say_to_wav("Hello. I have been written to a file.", filename="test.wav")
sc.say("I am being read out loud, right now.")
```

You can use `sc.recognize` to convert speech in a wave file into text, or without providing a file to record up to 30 seconds from the user's default microphone.

If the response indicates that it does not have high confidence in the result, a `LowConfidenceError` is raised. `args[0]` on the error contains the best guess at the text. If no result can be determined at all, `ValueError` is raised.

The `recognize_raw` method returns the JSON response from the service, which contains more information than is available from `recognize`.

```python
from projectoxford.speech import LowConfidenceError
text = sc.recognize('some_speech.wav')

try:
    text = sc.recognize()
except LowConfidenceError as err:
    text = err.args[0]

json_data = sc.recognize_raw()
```

Functions `sc.print` and `sc.input` can be used to override the builtin `print` and `input` functions to easily convert existing code.

```python
print = sc.print
input = sc.input

print("Welcome to my application.")
name = input("What is your name?")
```

Audio playback and recording is performed by the `projectoxford.audio` module. Currently, only Windows is supported, and the user's default device is always used.

By default, `record` waits for some sound to be heard, then records until one second of silence. Use the `quiet_threshold` argument to adjust sensitivity, and the `get_quiet_threshold` function can to obtain this value by recording a short period of silence.

The `play` function takes a filename or the raw contents of a wave file and plays the entire sound before returning.

```python
from projectoxford.audio import play, record
wave_file_contents = record()
play(wave_file_contents)

# Record for 5 seconds
data = record(seconds=5, quiet_seconds=0, wait_for_sound=False)
```

Use `help(record)` to review other arguments.


## Emotion API
---------------

This API analyzes faces to detect a range of feelings in an image. To use emotion APIs, you'll need to [obtain a subscription key](https://www.projectoxford.ai/emotion).

### Requirements
In order to render emotions on image "emotion_result.render_emotion()" you need to have these packages installed:
```
numpy
matplotlib
OpenCV (cv2)
```


### Usage
```python
>>> from projectoxford.emotion.api import EmotionClient
>>> ec = EmotionClient('YOUR-EMOTION-API-KEY-GOES-HERE')
# For local images:
>>> er = ec.process_image_from_path('/path/to/image')
# For remote images:
>>> er = ec.process_image_from_url('http://example.com/path/to/image')
>>> er.get_raw_result()
>>> [{'scores': {'disgust': 1.65423147e-10, 'neutral': 2.67820988e-09, 'surprise': 4.2763566e-09, 'fear': 6.918734e-11, 'happiness': 1.0, 'sadness': 4.156868e-09, 'anger': 3.50509538e-10, 'contempt': 4.948203e-10}, 'faceRectangle': {'left': 216, 'width': 141, 'top': 143, 'height': 141}}, {'scores': {'disgust': 0.000125725681, 'neutral': 0.5974805, 'surprise': 0.1454401, 'fear': 0.05481965, 'happiness': 0.000100017438, 'sadness': 0.2018231, 'anger': 7.945149e-05, 'contempt': 0.000131502544}, 'faceRectangle': {'left': 378, 'width': 139, 'top': 239, 'height': 139}}]
>>> er.get_strongest_emotion()
>>> ['happiness', 'neutral']
>>> er.render_emotion()
# Renders emotions on image and shows them.
```


Contributing
------------

Over time we hope to add the full range of Project Oxford APIs to this library. Contributions are welcome.

Licence
-------

This Project Oxford client library is distributed under the MIT license. See LICENSE for full details.
