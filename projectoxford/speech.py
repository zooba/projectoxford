#-------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation 
# All rights reserved. 
# 
# Distributed under the terms of the MIT License
#-------------------------------------------------------------------------
'''Project Oxford Speech Module

This module provides access to the Project Oxford speech APIs.

See https://projectoxford.ai/speech to obtain an API key.
'''

import base64
import requests
import time
import uuid
import sys

import projectoxford.audio as audio

_API_SCOPE = "https://speech.platform.bing.com"

_SYNTHESIZE_TEMPLATE = '''<speak version='1.0' xml:lang='{locale}'>
    <voice xml:lang='{locale}' xml:gender='{gender}' name='{voice}'>{text}</voice>
</speak>'''

VOICES = {
    'de-DE': {
        'Female': "Microsoft Server Speech Text to Speech Voice (de-DE, Hedda)",
        'Male': "Microsoft Server Speech Text to Speech Voice (de-DE, Stefan, Apollo)",
    },
    'en-AU': {
        'Female': "Microsoft Server Speech Text to Speech Voice (en-AU, Catherine)",
    },
    'en-CA': {
        'Female': "Microsoft Server Speech Text to Speech Voice (en-CA, Linda)",
    },
    'en-GB': {
        'Female': "Microsoft Server Speech Text to Speech Voice (en-GB, Susan, Apollo)",
        'Male': "Microsoft Server Speech Text to Speech Voice (en-GB, George, Apollo)",
    },
    'en-IN': {
        'Male': "Microsoft Server Speech Text to Speech Voice (en-IN, Ravi, Apollo)",
    },
    'en-US': {
        'Female': "Microsoft Server Speech Text to Speech Voice (en-US, ZiraRUS)",
        'Male': "Microsoft Server Speech Text to Speech Voice (en-US, BenjaminRUS)",
    },
    'es-ES': {
        'Female': "Microsoft Server Speech Text to Speech Voice (es-ES, Laura, Apollo)",
        'Male': "Microsoft Server Speech Text to Speech Voice (es-ES, Pablo, Apollo)",
    },
    'es-MX': {
        'Male': "Microsoft Server Speech Text to Speech Voice (es-MX, Raul, Apollo)",
    },
    'fr-CA': {
        'Female': "Microsoft Server Speech Text to Speech Voice (fr-CA, Caroline)",
    },
    'fr-FR': {
        'Female': "Microsoft Server Speech Text to Speech Voice (fr-FR, Julie, Apollo)",
        'Male': "Microsoft Server Speech Text to Speech Voice (fr-FR, Paul, Apollo)",
    },
    'it-IT': {
        'Male': "Microsoft Server Speech Text to Speech Voice (it-IT, Cosimo, Apollo)",
    },
    'ja-JP': {
        'Female': "Microsoft Server Speech Text to Speech Voice (ja-JP, Ayumi, Apollo)",
        'Male': "Microsoft Server Speech Text to Speech Voice (ja-JP, Ichiro, Apollo)",
    },
    'pt-BR': {
        'Male': "Microsoft Server Speech Text to Speech Voice (pt-BR, Daniel, Apollo)",
    },
    'ru-RU': {
        'Female': "Microsoft Server Speech Text to Speech Voice (ru-RU, Irina, Apollo)",
        'Male': "Microsoft Server Speech Text to Speech Voice (ru-RU, Pavel, Apollo)",
    },
    'zh-CN': {
        'Female': "Microsoft Server Speech Text to Speech Voice (zh-CN, Yaoyao, Apollo)",
        'Female2': "Microsoft Server Speech Text to Speech Voice (zh-CN, HuihuiRUS)",
        'Male': "Microsoft Server Speech Text to Speech Voice (zh-CN, Kangkang, Apollo)",
    },
    'zh-HK': {
        'Female': "Microsoft Server Speech Text to Speech Voice (zh-HK, Tracy, Apollo)",
        'Male': "Microsoft Server Speech Text to Speech Voice (zh-HK, Danny, Apollo)",
    },
    'zh-TW': {
        'Female': "Microsoft Server Speech Text to Speech Voice (zh-TW, Yating, Apollo)",
        'Male': "Microsoft Server Speech Text to Speech Voice (zh-TW, Zhiwei, Apollo)",
    },
}

LOCALES = [v for v in VOICES]
GENDERS = [g for v in VOICES.values() for g in v]

def join_and(items, sep=', ', last_sep=' and '):
    '''Joins a sequence of strings together using commas and the word
    "and" between the last two items.

    items:
        Sequence of strings to join.
    sep:
        The separator to use between all but the last items.
    last_sep:
        The separator to use between the last items.
    '''
    if not items:
        return ''
    if len(items) == 1:
        return items[0]
    return sep.join(items[:-1]) + last_sep + items[-1]

def join_or(items, sep=', ', last_sep=' or '):
    '''Joins a sequence of strings together using commas and the word
    "or" between the last two items.

    items:
        Sequence of strings to join.
    sep:
        The separator to use between all but the last items.
    last_sep:
        The separator to use between the last items.
    '''
    return join_and(items, sep, last_sep)


class LowConfidenceError(ValueError):
    '''Thrown when a speech recognition operation returned with low
    confidence. ``args[0]`` contains the best guess at what was said.
    '''
    pass

class SpeechClient(object):
    '''Provides access to the Project Oxford Speech APIs.

    SpeechClient(key, locale='en-US', gender='Female', tee_print=sys.stdout)

    key:
        The API key for your subscription. Visit
        https://projectoxford.ai/speech to obtain one.
    locale:
        The locale for both voice and speech recognition. This value
        can be overridden on individual calls to `say`.
    gender:
        The gender of the voice. This value can be overridden on
        individual calls to `say`.
    '''

    def __init__(self, key, locale='en-US', gender='Female'):
        self.key = key
        self.client_id = uuid.uuid4().hex
        self.token = None
        self.token_expires = None
        self.locale = locale
        self.gender = gender

        self.quiet_threshold = None

    def _get_token(self):
        if self.token is None or self.token_expires < time.clock():
            r = requests.post(
                'https://oxford-speech.cloudapp.net/token/issueToken',
                data={
                    'grant_type':'client_credentials',
                    'client_id': self.client_id,
                    'client_secret': self.key,
                    'scope': _API_SCOPE
                }
            )
            try:
                r.raise_for_status()
            except requests.HTTPError:
                raise RuntimeError('unable to obtain authorization token')

            self.token = r.json()
            try:
                self.token['access_token']
                self.token_expires = time.clock() + int(self.token['expires_in'])
            except (ValueError, LookupError):
                self.token = None
                self.token_expires = None
                raise RuntimeError('unable to obtain authorization token')

        return self.token['access_token']

    def calibrate_audio_recording(self):
        '''Determines the quiet threshold for the current user's
        microphone and room. The user should be quiet for one second
        while this is called.

        This will be called automatically if needed before the first
        call to `recognize`.
        '''
        self.quiet_threshold = 1.1 * audio.get_quiet_threshold()

    def print(self, *text, sep=' ', end='\n', file=sys.stdout, flush=True):
        '''Prints the provided items and also says them using the
        default voice.

        This function is intended as a drop-in replacement for the
        builtin print function.
        '''
        print(*text, sep=sep, end=end, file=file, flush=flush)
        self.say(sep.join(str(t) for t in text) + end)

    def input(self, prompt=""):
        '''Prints and says the prompt, if any, and waits for the user
        to respond. If the response is not of high confidence, the
        user will be prompted again or asked to confirm what was
        heard.

        This function is intended as a drop-in replacement for the
        builtin input function.

        Note that this function may produce multiple lines of output
        and calls to the speech API. To avoid these calls, you should
        use `recognize` directly from your code.
        '''
        while True:
            try:
                if prompt:
                    self.print(prompt, end='')
                return self.recognize()
            except LowConfidenceError as ex:
                self.print()
                self.print("I didn't quite catch that. Did you say {}?".format(ex.args[0]))
                try:
                    if self.recognize(require_high_confidence=False).lower().startswith('ye'):
                        return ex.args[0]
                except ValueError:
                    pass
            except ValueError:
                self.print()
                self.print("I didn't quite catch that.")
            finally:
                if prompt:
                    self.print()

    def say(self, text, locale=None, gender=None):
        '''Converts the provided text to speech and plays it over the
        user's default audio device.

        text:
            The text to say.
        locale:
            The locale to use. If omitted, uses the default for this
            client.
        gender:
            The gender to use. If omitted, uses the default for this
            client.
        '''
        if text.strip():
            audio.play(self.say_to_wav(text, locale, gender))

    def say_to_wav(self, text, locale=None, gender=None, filename=None):
        '''Converts the provided text to speech and returns the
        contents of a wave file as bytes.

        text:
            The text to say.
        locale:
            The locale to use. If omitted, uses the default for this
            client.
        gender:
            The gender to use. If omitted, uses the default for this
            client.
        filename:
            Path to a file to write the wave file to. If omitted, no
            file is written.
        '''
        if locale is None:
            locale = self.locale
        if gender is None:
            gender = self.gender

        if locale not in LOCALES:
            raise ValueError('unsupported locale: ' + locale)
        if gender not in GENDERS:
            raise ValueError('unsupported gender: ' + gender)
        try:
            voice = VOICES[locale][gender]
        except LookupError:
            raise ValueError('no voice available for {} {}'.format(gender, locale))

        r = requests.post(
            _API_SCOPE + '/synthesize',
            data=_SYNTHESIZE_TEMPLATE.format(locale=locale, gender=gender, voice=voice, text=text),
            headers={
                'Content-Type': 'text/ssml+xml',
                'X-Microsoft-OutputFormat': 'riff-16khz-16bit-mono-pcm',
                'X-Search-AppId': '40c496aba8e54b429be4429db5caf4a1',
                'X-Search-ClientID': self.client_id,
                'Authorization': 'Bearer ' + self._get_token(),
            },
        )
        r.raise_for_status()

        wav = r.content

        if filename:
            with open(filename, 'wb') as f:
                f.write(wav)

        return wav

    def recognize(self, wav=None, locale=None, require_high_confidence=True):
        '''Converts a wave file to text. If no file is provided, the
        user's default microphone will record up to 30 seconds of
        audio. Returns a string containing the recognized text.

        wav:
            An open `wave.Wave_read` object, a `bytes` object
            containing a wave file, or a valid argument to
            `wave.open`. If omitted, a beep will be played and the
            user's default microphone will record up to 30 seconds of
            audio.
        locale:
            The locale to use. If omitted, uses the default for this
            client.
        require_high_confidence:
            If True, raises `LowConfidenceError` when the result is
            not of high confidence. The first argument of the
            exception contains the text that was heard. Otherwise,
            low confidence results will be returned as normal.
        '''
        if not wav:
            if self.quiet_threshold is None:
                self.calibrate_audio_recording()
            audio.play(_BEEP_WAV)
            wav = audio.record(seconds=30, quiet_seconds=1, quiet_threshold=self.quiet_threshold)
        res = self.recognize_raw(wav, locale)
        try:
            best = res['results'][0]
            if best['properties'].get('HIGHCONF'):
                return best['name']
            if best['properties'].get('MIDCONF') or best['properties'].get('LOWCONF'):
                if require_high_confidence:
                    raise LowConfidenceError(best['name'])
                return best['name']
        except LookupError:
            pass
        raise ValueError('unable to recognize speech')

    def recognize_raw(self, wav, locale=None):
        '''Converts a wave file to text, and returns the complete
        response JSON as a dictionary from the server.
        
        See https://www.projectoxford.ai/doc/speech/REST/Recognition#VoiceRecognitionResponses
        for the schema of the response.

        wav:
            An open `wave.Wave_read` object, a `bytes` object
            containing a wave file, or a valid argument to
            `wave.open`.
        locale:
            The locale to use. If omitted, uses the default for this
            client.
        '''
        if locale is None:
            locale = self.locale
        if locale not in LOCALES:
            raise ValueError('unsupported locale: ' + locale)

        with audio._open_wav(wav) as w:
            if w.getnchannels() != 1:
                raise ValueError('can only recognize single channel audio')

            content_type = '; '.join((
                'audio/wav',
                'codec="audio/pcm"',
                'samplerate=8000',
                'sourcerate={}'.format(w.getframerate()),
                'trustsourcerate=true'
            ))

        params = '&'.join((
            'scenarios=ulm',
            'appid=D4D52672-91D7-4C74-8AD8-42B1D98141A5',
            'locale={}'.format(locale),
            'device.os="Windows OS"',
            'version=3.0',
            'format=json',
            'instanceid=565D69FF-E928-4B7E-87DA-9A750B96D9E3',
            'requestid={}'.format(uuid.uuid4())
        ))

        r = requests.post(
            _API_SCOPE + '/recognize?' + params,
            data=wav,
            headers={
                'Content-Type': content_type,
                'Accept': 'application/json;text/xml',
                'Authorization': 'Bearer ' + self._get_token(),
            },
        )
        r.raise_for_status()

        return r.json()

_BEEP_WAV = base64.b64decode(
    b'UklGRiIaAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0Yf4ZAAAAAAAABAAIACAADwAiAAIA'
    b'BQDw/+P/1v/U/9L/4//q/wQAGgAtAEEARABDACwAIADo/+j/pf+0/5D/sf/A/+z/DAA9AGEAfgB9AHYA'
    b'PgApANf/sv9v/2P/Wv+E/6T/7f8nAHMAsQC9AM0AlQBqABUAs/9u/xz/Fv8V/1T/lf/9/1kAvwAHASUB'
    b'AgHfAGAADABv/yD/rv7F/sf+Kv+d/woAtgALAX8BegFZAfYAbgDU/yX/pf5H/lT+kf4G/6T/SwAAAZ0B'
    b'3wHtAZUBDgFjAIL/vP4e/s797f1Q/gD/sP+sAG4BJQJiAlACzwEZATIAF/9E/nr9X/2L/SP+Af/o/xoB'
    b'/gG9AvACrQL9AQ8B3f+f/pP94/zQ/DD9Gf7//mYAigG1AmEDbQMAAxoC4QB3/wH+5fw8/Ej8+Pz3/T3/'
    b'5wBgAqkDbgRKBIYDagJ+ALj+wPxi+7/6KPsj/JX96f+OAScEVgUIBokFnwQWAksAe/2/+gr64/j5+Zv7'
    b'6v3g/yME9wRxB/AHlAYmBDkEcP3U+xj7x/TA+X/41frw/UoDdAINCTwKdwZpCl0E8ABt/s/6JvSJ+HX1'
    b'ePYm/t/8KgM0CH4J6wlUDXAG5gT1AhT5sPiq9RTyjfWA+Zn43QHWBcsGYg4pDfMJqAoABVv8ufzG87Dw'
    b'8/Ro8pf2e/4vAFAG6w7UCysP7g5DBjQECP9Y9Cbz5/Hl7Jb1LvhV+icGGQrRC+ATaBCjCjUMaQDa+B73'
    b'2+0W7DjypPB59gUC9AIuDOQSyQ3hDegOWQdyBWX8Au6k8qz1xPYw/+cB+wJAER8UexFJFmAMxwQAAPbw'
    b'TOar5UjcRN9H6XjqgviUBnEMYRixIoMdLiFDHAkO2wmv/dbwu/AS7gbqq/ST9eD6Swa8Bg8IJQvEAR/8'
    b'S/rq6vnn4ucz4/XqufXL+WYI9hWIGQslOyWdH9Ad4RJMA3z8k/DF5M/p/uTf6OzzNPfDANAK8ApFDJoO'
    b'gQF1/jb3c+qq50fo9+Vf8LD5ZP99EN0YJx7LJfAjBxrcGEMIVPvS81rnsOJX5uDleevo+Fr86wjUD/EP'
    b'XA/GDWkCa/u58/zmPee05gfpXPMP/RQE2RQzHCof0SWVHpQXyxDIAfX0o+6M4zbjeuji6FLz7P3KA80M'
    b'fxS1D8cQmQoV/Xj3Pu2x5KHmRek86gf51v9yCvoZAR6EIfciDBswENEKefjo737qK+J15FfqLe2c+FEF'
    b'dAcIEzETxQ/DDaQG0Pn28+3rq+Oo6njqdfKo/XgGhQ9CG+YdFB4VH9ETHQy7AGzz2Oob6Jnjp+fs7gzz'
    b'pwDeCIwP5BSIFVYPrgslAjX2evCt52Hmbek57nv0zwENCc8TGBwMHAUdvBcXD4MEEfsX7lPqsOZd5zPt'
    b'kPPV+yQG0g6REvQWMhNADh0IK/x98qPsSOZW5mrsOvAG+tQFUA02GJocNhvEG9UTsQieAEH1oepi6ifo'
    b'EOqb81z4fgKvDX8RnxT0FrsQ1gntAkH1Ku+Y6XPkwOkM76P0SgABC+cRIxt5HDEaPRjjDiQDKvtf8Azp'
    b'H+oE6UfvT/ha/SIG1hGNFLgVthPgCmAHDP5x8DHqTui75lXtH/Kw94YGhg79E6cbUhqjFtQSsQdA/EP2'
    b'ruvY6JvsvetW88H82gGGCwMUDRNAFlcScginAh75be2g6rLoMOi78FD17f28CYQRkhTrGoAXORIfD5UB'
    b'JPph9FDt+eoQ7+buD/bh/2kCpAwzEkERSBI8D0UGZAAp+BLuWu437IHss/Os+Pj/rwqODzoSHxdTEXsN'
    b'RwiD/bD1//AJ613rg/Ae8fb6igKpBwIQdxNIEUcRjAzOAuj9qfQg7lruzu0T8L/2rvydA7QLAhABEaUS'
    b'Dg6/CMQB5Plt8onu2u047VLzQ/cm/7oG0gxDERcT+hFyDQYJwf8e+UXymO7P7cfvGfNS+S8AeAZYDc0P'
    b'/xAyD50LvwQq/iz2EvHK7o/u8vC89YL78AIkCp4O3xHhEQ8PdgoQBP37zPWz8Lzudu+X8vT1mP0YA4gJ'
    b'KA6mD4wP4wymCEYBbfyx9CryXfBY8c3z+/hM/UYEbgksC+oRBBDkCRIMw/wuAtzy0O7h/EbjQADE8z39'
    b'6gmAApsUTwQ9FkACtQfYA5bwiv+V6UH4gO+i99f8l/tzEDEAqRijCtILOBDb/a4EDvTh/N/oVfk874n1'
    b'kgND8iYXaPq0F6wHzAjvESfzWA536IX9uvHK7bH/Zu0FCgv41RGwBywJexhk+zgVj/VnArD0vPC7+Qno'
    b'xAO46w4I8AD2A3gUjQB7FygAygq//rT3qf166cAArepQ/TP9OPr8Dmf/MRSmBoEOTwhWAPsFZu+I/lvu'
    b'y/Su9+LzrAGa/KgKkQWqDfQLWwaVDJ/9JgGB+Dr19vew8Rz7nvV5Acj98QfoCuUBlxS8/70M8/+L/B3/'
    b'ge8g/1LutPxl+YX6uQfL/rcO1QN9DQEIPAF2CMv0UgDj8oL31fhO9BoBoPhCCmoBygqtDBEDvA4a/T8F'
    b'u/hI+In5SPLD/dXxTQLI/CsCKAp3AfkNmAJVCcUBvv5l/3b0Mf968dz7hfq2+G0ErP78ChgFTQsfCGkE'
    b'6wV3+FMCpPXK82b88PRH+xv/pwYNAIcP4AgQA8gO3fz+/yr+fffZ8+v+E/S/+GwEHvnnAtoJxvyHCwoI'
    b'i/0JDBT+dv8q/R//Z/Sz/XL7l/IoCH75AgbBC/AD4AvgCOkDT/3hALry8vVC+6/tGABV/A3+lgpkBqsH'
    b'SAmqCKv9EgUn/HL25gLn9YD+lgFh/FMA3QKAAA39Rgit+7sD3Adu++sIhvyj/o3+Tvjl+M/2IPzn910F'
    b'vQI3B1oPuwYvC10FX/0k++z2jPXo82T95fl2AicKRwKqD5YDEQW7ALT81fh9+JT9z/VrBHL+sAA6BOX/'
    b'r/+G/8j+Pv2LA7AE9QCIC0UD3QG6BQH4x/pI9bP36PSEAn3/qAWcETcGqA1tBlT+Pfek+HTu/PMe+0L3'
    b'8wQZCwIGDA8OCo0AlAQr+l33Vvmj/BL4xAZvA0oBYAvm/LL/Cf1o+K/4tQBr/w4CNA0LBN8HlwZM+qv5'
    b'N/ac7nf2FPvF/csHwg/ACl4S0gq4/esCxexY9XPzCvWL/CYDGQocCQARdAW0AkIAcvOe9J74ku1uB/cE'
    b'OAjzDR0Pdw4XA+ICD/Mr/in0wvijAKT/G/4RCL75xPol+q7rYPi78r8E7QSeGEEXaBtSH6cM3wiG+ujn'
    b'h+ml47bf6vSe7Y0CogEDCz8E3AWuBJX2pga0+7YILA98EjQVEhrRB7UJmvcA7P7mVeD46Mzlnv7i9usM'
    b'+AkbCDoKFwDf+bP6vPnd/TwMvgs1HfkU1xvyB90Fn/F84w3kONlq5ifrNvmLAwwRqAyJFS0G6AaX+sX6'
    b'7/oZ/KkLGgbDGScO+w7+A4v3tuqZ5PTeCucX7pD7BgmwEP4alRD8Feb++/268DfwRfWS+0gGEBChFjwT'
    b'pxGl//j3UOO+5A7cLeol8DT+9hBPEjgc7RPvDRAAv/nM7xj2u/bYA/QJ1BXhFOkQwApF9fbwidsl4V/g'
    b'te3O+GYKoxVnGrgbGRBsBpX2m/FQ6Jr0ZvRVB/EQGhpwG2oUtgn19hLt39wZ4SHikvH0+hQQCRM+G48W'
    b'FAr5Afjv2O8R61/3PfvFDEMUNRq3FsgNVf8l8c3lEN/V5v7pS/2DB+0WWxnHGusQkARc9xXrt+lv6tH0'
    b'wf7fD58UoxxfFToN3P4p7x3mKuKc56burP6cCRIVzRY5FZMK5QC98mXu7u1w8pf+8AcRFoAYABpaDssE'
    b'oPIJ6LPgpuIZ6rb1sAVNEPMa+BZeFeAFNPvk7TvrT+sV9AIAqwtCGJAZRRrYDVgEqvDS6pLj++cO76L6'
    b'LwecEHUVqhDqDPL8DvYN7KzvDvGC/hwHYhQUGyQZvxVgBiH7tenq53nhEO2c9A8DQg/jFoEXCBK2Ca34'
    b'iPGL6L3s4/DH/lgIrxV2GFkZYhE9ByP4furd6xDnOvHl97EJiQx6FKUTfgupAaP0WvAW623yqffhBmEO'
    b'9xjZF0EVPglv/F/ueuUB55PoO/fW/ggQ8BIUGUMREAtN/ajxqO0o6rfyoPdyBxkM4hgjFJYSxAYV+zDx'
    b'H+sY7mrvGv1KA9IP8A84E1sJCQOt9I3vbO1a7kf5s/6CDiYRFxlHELkMM/7582Xss+lh7rv03wGXCSUV'
    b'nRIOFHIIDACC8QHuq+oU7qb3xP53DHsPSxVODjQLGvwG95Lv5+8p9Mz5DgSHCRgRtAyZDKcABPnI8L7v'
    b'Gu+r9k3+yQfgEMERkxKPCSIDCfTG8XTrOPCA9eH9OQllDwwUaA9zDEz+Z/fv7YrskO0Y9SD9qQYYD/kP'
    b'WBHKCBcCvPe+9FjxsPXS+ZMBrgm5DCkOOgqMBFr5sPUN7+zxnfWa/LsFwQwREFcPwQtxAKj5LPHi7urv'
    b'jvY0/N0HdQ1+EN4QTwswA4/5gfPT7lLyRvTA/LUEjQvTDcMOFAkjAV/6I/Ml80T0TfiM/zEGUQs/DJkK'
    b'VAW//q/07vOR8qH1t/zrAZMMoAsFEb8IMQXb+sn0RfKV8Wj2s/rwBSkJgRDyDBQMRwLS+1zz5fCd8iPz'
    b'GvxUAjIJjwxQDiAJ+ASV/KH3pfbM9Ir6cf5XBT4JBwuzCRsFzf6e95/0CvO99rr4IgKcBZQL5gyKCeMF'
    b'xvyQ+D/0dfXF9n/8ZwPvCQoNrA5aCWUF2vs69tvy5/Bb9WH4igGfBFkL7Ao2CngEz/2u+Qn3dPci+V3/'
    b'0wL/CCUKvwkRB/0ALPu59s71M/ZN+QH/OANyCMUIOQiFBL/94vga9sP0Hvd6+6oBlgc4C5IMzwnxBiD+'
    b'zfoS9sf0Hvf7+nIA4AVdCQsK7gjbA9n+OvnD9xH1/PiI+l4ALgW+BkkITQXyAW785/kS+GX5j/syAAwF'
    b'FgntCcUJ6AWRABv89/fP9nb3t/rt/mYEKQd6CSUIvwTd/gv6J/et9E/4rPhAAJ8DtAc9C1gHqAYz/7v8'
    b'f/hr+IL5PPsQAQYEbQebCDoH2ANJ/zz8cPn4+QX7JP0mAmMD1QVSBXMDBP4s+xX38fYL+Gf6VgClA9YI'
    b'LwnxCnEGyAIT/m76cfm4+AP7I/8/AwkGHwifBvkEoP+P/Iz3WPnp9ob6ff4hAPkFaQTtBy4C+AHL/Cf9'
    b'd/tL/Db/3QFWBaEF+ge0A+ACmPw/+zj4xvnN+TL/ogHLBOEHFwYRBvz/1/01+Ln55Paf+pr9zQCcBXgG'
    b'OwhfBUgDP/7B/Ij6S/qf+0j/FgFXBWMFfQU7BCgAUf4T+xX7GfqU/Wb+7AEqAzwDpQNkABD+eftH+xX6'
    b'lvw3/3cCqAWQB+gHlwbhAvH+Cf1h+sX5JvrU/JH/CwS+BFUG9QTKAYz/GvxJ+wH5PftW/N7/TAIcBCAF'
    b'/wMkArL/2P6w/HH9JP69AAwCHwTgA28EFAJo/rb8iPqu+rP6vv1O/y8DRATABfsEWAKu/y39pPv5+UP7'
    b'XPxYAGQC7AQKBgYGaQPlAF/+HPz7+r36GPz6/b8A1wFFBAYD3QGgAIz+Of6w/Q3+Sv/oAf8BqAP2A3sB'
    b'4/+L/ZP7m/sh+5n8d/+8AawDvgWXBVQDAAIr/rr8cPuu+gX8If7bAF8CbAV7BLADwgEg/639Ifw3+3r8'
    b'Pf6y/4MC0QN+A0oDHQGa/0P/Hv1D/pb+6//JAD8CkwJZAS0A7vyT/Cf7PPtv/LL+qwBAA9kFAQVIBfEC'
    b'owCa/hf8jfsQ/Pr8Qv94AS8DSQOuA0UBBQCY/sv7Uvya+zz+tP6XAfcCTwOfA1gBZAFd/uv9Mv3N/aP+'
    b'ZwA6AZcBBAI6AHf/dP0r/bj8x/2A/7cBawNFBXwFhQVJAm0AK/7X+or6uPhz+z/8yv86AZYDbgR8Ao0D'
    b'MwA+/5L9tv1Q/gUAQgExA5oD9gKdAXIBtv/h/Kr9NfxO/kb/SQDJAboBRABAAKX+WP0f/eD8mf75/+AC'
    b'bQNyBogEawOjASL+I/2L+jf6i/qr/LT+8wGWA2gE2QOkA7oAGgDc/Sr8s/3T/Db/zgDSAfMBQgKzADAA'
    b'eP7m/YL9C//E/+b/XwM4AeUCsQDO/hb+LvyF/OH8Nv/P/xcDqgTPBJoElQLw//b+BPvh+hX7r/yB/gkB'
    b'9gN6A0UFeAKBAnX/fv3p+zH8afy2/eMACAC9AlsBWAGxAIj/gv66/kD/zf+lAfoCvgJXA5EBaP+6/6P7'
    b'If35+6P9R/9JAZ4DLQPKBN8AkQEE/lT8hPup+hf8j/0zAT0CZQVsBMYDkANkAF//sv3U/Iz93f38/7wA'
    b'jAJQAd0AVQH+/Vv/1fy8/gD/yP8fAowBmgNlAHgBWf7E/Ln8dPvc/ZD+PAFbA9cEsQSEAxQDzf9G/t/8'
    b'VvsP/QH9QgCsAWUDmwM5AwMDa/+0/7/7evyX/N38Mv/J/+MBqADbAtcAGgAcAMD9/f/k//AA1gJgA4oD'
    b'fwLMAb/+Ev6U/A77MP33/Jr/ZAH+AggD3AITAmP/xv7t+5j8+fyG/UIAgQHhAyIEBAQyA3kBaQB5/XP+'
    b'mfw9/aj/Hf+SAfQARAHaAGgAQ/5d/mn/Ov6fALMB5QG8AiYCrwAfAAH+4PwL/QL9zv0hAIIBcAIFBKsC'
    b'IwJIAWD+gv18/eT8Ef6h/1cBOwOZAxsD/QLCAXj/mv5//WD8ef20/dT+QQBeAPYAhwBcAHn/y/+e/8f/'
    b'rwFuAQwDOAPSAdIBGACk/hr9Mf25/Mj9ev8PAH4CggIyAncCnwD2/uT9J/24/Pv9/f44AA0CcgIwAvoB'
    b'xwGr/3L/iP7f/SP/Sv+uAAQBEQGgAdkA5QAi/4H/uf71/jEAg/9TAXgAmgA2AEb/ZP6u/aL9qv3k/or/'
    b'3ADQAhMDpQJAA0cBngDe/6z+iP7+/rH+KQACAbAAbQFBAJz/0f5Q/tz86/0i/u/9nwBQAO8AXAJgAfgA'
    b'KwFHAKb/NQATABkAvAEvAOMA+wAx/1j/YP70/bD9Zf+t/nQAZwHUAMYB8wA2AJD/Gf/u/af+6P4e/7oA'
    b'DwEYAWQCRwECAegAQP8q/4f/Lv8B/4wAFwCcALUAoP8BAFD/tv5T/2T/8v6TAMcAuwALAfMAUgA+AMf/'
    b'Gf8BAFT/BACQAJsAhgAKAcD/9P97/03+/P6y/jj/Xv/WAEUAiAFFAbQAJgExAO7/sv9Z//D+1v+q/yIA'
    b'HwA0AKT/iABr/0z/SwAK/2AA5v+bADcAbwAeAPr/RQAZ/+P/wf8UAEsAfACHANQAfQCr/4P/Tf9r/hT/'
    b'Cv/V/n8A0P/kANcAwgCRAKQA1P+9/6MAVf92AMb/TgDe/y4An/+c/wkA9f7Q/9n/s/9AAIUAPgCRABkA'
    b'2P+J/6D/Kv/W/9f/6f/PAGcApABGAG0AtP/w/1X/bf/L/9r/TgA0ACABzQARAWkAAgDH/23/If9R/w3/'
    b'if9N/6f/mv9c/9j/Sv8OAKP/oQDEAP8AiQFQAZUB5wDQAOP/5f8o/0r/C/9Q/2r/r//t/87/z/8z/2P/'
    b'C/9m/0f/AAAeAPYA5wBVAXUBxADbAAsANABp/w8Ar//F//v/AQD7//b/dv9Y/2X/Lf+Z/7P/QgBNAN0A'
    b'ZgDcAGMA1f/X/2r/dP+o/8L/0v+uAFAAogBaAAkA9P9k/1j/6P6R/5j/HgDqAFMAAgHgAHsAawDO/4L/'
    b'TP+1/zj/ov8CAHv/QQCX/4//sf9F/5T/xP8tAFsAJwHyAAsB7wBjAA0AnP9B/xn/cP8u/wsASQArANsA'
    b'hwBYANj/ev8+/yD/gv94/2gAPgBCAOwA+P+DAOH/l//y/6b/8/8WAGQAjACKAMAA0P/0/2D/B/9u/wv/'
    b'lP8fAE0AbgDwALYAcQBeAL3/hP+Z/6T/rv9pABoAeQCeAOr/BQBw/zH/+v4s/wP/lf9PAHkAOAFeAQMB'
    b'NQGtAN//NQBk/73/tv/Y/7X/v//K/z7/jP/+/vn+Kf8c/7L/dgCwAEsBmQFMATwBvQAUAMv/x/9F/5j/'
    b'yv+y/xYANgCm/wcAdf8V/2n/8P5o/+z/NAC+ACABJgEHARoBcwDa/woAO/9y/7v/W/8OAO7/CQDc/+j/'
    b'df+Z/6r/df82ADUAbwDuAK4AvACiABQAuP+Z/yL/P/+i/6D/JABTAF0AdABxAOj/7v+H/0L/of+M/83/'
    b'WQBPALAAswCYAD0AJADD/47/1P+z//b/OgD9/zsAWADY//n/u/9W/6f/xv+n/00AZgBZAJoATQAGAP3/'
    b'if97/7f/rf/r/2UAaQCWAMUAdgBEAAAAiP9u/2T/OP+a//r/AwBVAHkANgBsAAUA7//V/8D/mP/p/wYA'
    b'6/95ABIAOgA4AOD/9f/o//f/EQBqAGEAdwCDABAAAACp/0z/Wf9J/0z/n//l//r/cgBwAGAAfgD+/+r/'
    b'0f+d/7P/6v8TADwAkgBeAIwAVwAWAOz/1f+L/77/s/+x/+H/9v/+//f/BACx/9//tf/J/xMA/P88AEAA'
    b'YwAxAFIA9v/q/97/w//p/xQAKwBRAI0AVgBmADwA4v+1/4P/U/9u/2X/l//S/wEAFAA5ADgAFQAyAP7/'
    b'//8UAAQASwBBAFoASQBXABsADgDq/8X/vP/J/7z/4P/g/+D/+f/f/87/1f/A/83/9//x/z4AQgBlAGYA'
    b'VABFABYA8v/K/8P/rv+7/+X//v8YADIANgAtACcAEQD2//P/yP/e/+X/3//z//z/+P8IAO//9//Q/wwA'
    b'4f8iABcAGwA2ACUAHwANAA0A5v8BAOL/8/8UAAEAGwAgAAgAFADj/+v/vf/b/7r/3f/t/+r/JgAOADYA'
    b'IQAzAAAAKADt/xIA5/8RAOb/FwD5//r/DwDs//z//f/m/wIA///4/xUA+v8OAAMA/P/8//j//f/u/woA'
    b'8v8WAP//DAAPAP//DAD3//v/AADw/wQA/P/4/w0A9v8OAPb/BgA='
)