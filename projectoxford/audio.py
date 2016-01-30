#-------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation 
# All rights reserved. 
# 
# Distributed under the terms of the MIT License
#-------------------------------------------------------------------------
'''Project Oxford Audio Module

This module provides cross-platform functionality to perform simple
audio operations, such as playing and recording wave files.
'''

import array
import contextlib
import math
import sys
import wave

from io import BytesIO

__all__ = ['play', 'record', 'get_quiet_threshold',
           'get_playback_devices', 'get_recording_devices']

if sys.platform == 'win32':
    from ._audio_win32 import _get_playback_devices, PlaybackDevice
    from ._audio_win32 import _get_recording_devices, RecordingDevice
    
    def _play(device_id, wav):
        with contextlib.closing(PlaybackDevice(
            device_id,
            wav.getnchannels(),
            wav.getframerate(),
            wav.getsampwidth(),
        )) as pd:
            pd.play(lambda: wav.readframes(wav.getframerate() // 2))
    
    def _record(device_id, wav, seconds_per_chunk, on_chunk):
        with contextlib.closing(RecordingDevice(
            device_id,
            wav.getnchannels(),
            wav.getframerate(),
            wav.getsampwidth(),
        )) as rd:
            rd.record(int(seconds_per_chunk * wav.getframerate()), on_chunk)

else:
    def _get_playback_devices():
        return []

    def _play(device_id, wav):
        raise NotImplementedError('play is not implemented for platform {}'.format(sys.platform))

    def _get_recording_devices():
        return []

    def _record(device_id, wav, seconds_per_chunk, on_chunk):
        raise NotImplementedError('record is not implemented for platform {}'.format(sys.platform))

@contextlib.contextmanager
def _open_wav(wav):
    '''Internal helper function to open an unknown parameter as a
    wave file.

    wav:
        An open `wave.Wave_read` object, a `bytes` object containing
        a wave file, or a valid argument to `wave.open`.
    '''
    if isinstance(wav, wave.Wave_read):
        yield wav
        return

    if isinstance(wav, bytes) and wav[:4] == b'RIFF':
        w = wave.open(BytesIO(wav), 'rb')
    else:
        w = wave.open(wav, 'rb')
    yield w
    w.close()

def get_playback_devices():
    '''Returns a list of available playback devices.
    
    Each item is a tuple of a display name and a unique identifier.
    Pass the identifier to `play` to specify the device.
    
    The first item, if any, is the recommended default.
    '''
    return _get_playback_devices()

def get_recording_devices():
    '''Returns a list of available recording devices.
    
    Each item is a tuple of a display name and a unique identifier.
    Pass the identifier to `record` to specify the device.
    
    The first item, if any, is the recommended default.
    '''
    return _get_recording_devices()

def play(wav, device_id=None):
    '''Plays a wave file using a playback device.
    The function will block until playback is complete.

    wav:
        An open `wave.Wave_read` object, a `bytes` object containing
        a wave file, or a valid argument to `wave.open`.
    device_id:
        The device to play over. Defaults to the first available.
    '''
    if device_id is None:
        device_id = get_playback_devices()[0][1]
    
    with _open_wav(wav) as w:
        return _play(device_id, w)

class _RecordStatus(object):
    def __init__(
        self,
        target_wav,
        bits_per_sample,
        sample_rate,
        quiet_threshold,
        max_seconds=0,
        max_quiet_seconds=0,
        lstrip_quiet=True,
        on_call=None
    ):
        self.target_wav = target_wav
        self.max_seconds = max_seconds
        self.max_quiet_seconds = max_quiet_seconds
        self.seconds = 0
        self.quiet_seconds = 0
        self.lstrip_quiet = lstrip_quiet

        self.bytes_per_second = bits_per_sample * sample_rate / 8
        self.quiet_threshold = quiet_threshold
        self.on_call = on_call

        if bits_per_sample == 8:
            self.is_quiet = self._is_quiet_8
        elif bits_per_sample == 16:
            self.is_quiet = self._is_quiet_16
        else:
            raise ValueError('cannot record {} bits per sample'.format(bits_per_sample))


    def _is_quiet_8(self, data):
        mean_square = sum(((d - 128) / 256) ** 2 for d in data) / len(data)
        return mean_square < self.quiet_threshold ** 2

    def _is_quiet_16(self, data):
        arr = array.array('h', data)
        mean_square = sum((d / 32768) ** 2 for d in arr) / len(arr)
        return mean_square < self.quiet_threshold ** 2

    def __call__(self, chunk):
        if self.on_call:
            self.on_call(chunk)

        if self.lstrip_quiet:
            if self.is_quiet(chunk):
                return True
            self.lstrip_quiet = False
        
        if self.target_wav:
            self.target_wav.writeframes(chunk)

        s = len(chunk) / self.bytes_per_second
        self.seconds += s
        if self.max_seconds > 0 and self.seconds >= self.max_seconds:
            return False

        if self.max_quiet_seconds <= 0:
            return True

        if self.is_quiet(chunk):
            self.quiet_seconds += s
        else:
            self.quiet_seconds = 0
        return self.quiet_seconds < self.max_quiet_seconds


def record(
    wav=None,
    channels=1,
    sample_rate=11025,
    bits_per_sample=8,
    seconds=-1,
    quiet_seconds=1,
    quiet_threshold=0.005,
    seconds_per_chunk=0.5,
    wait_for_sound=True,
    on_chunk=None,
    device_id=None,
):
    '''Records a short period of audio into the provided wave file or
    a newly created buffer using the user's default recording device.

    If `wav` is not provided, the return value is the recorded sound
    as bytes.

    wav:
        A writable wave file, opened with `wave.open`. If ``None``,
        a new wave file will be created using the values provided
        for `channels`, `sample_rate` and `bits_per_sample`.
    channels:
        The number of channels to record. Must be either 1 or 2.
        Ignored when `wav` is provided.
    sample_rate:
        Number of samples to record each second. Typically one of
        8000, 11025, 16000, 22050, or 44100. Ignored when `wav` is
        provided.
    bits_per_sample:
        Number of bits of information to record each sample. Must
        be either 8 or 16. Ignored when `wav` is provided.
    seconds:
        Number of seconds to record before stopping. If zero or less,
        this limit is not used.
    quiet_seconds:
        Number of seconds of continuous silence to record before
        stopping. If zero or less, this limit is not used.
    quiet_threshold:
        Average RMS volume of each recorded chunk that counts as
        silence. If the volume of a chunk is below this value, it is
        counted towards `quiet_seconds`. Whenever a chunk is above
        this value, the count resets.
    seconds_per_chunk:
        Number of seconds to record into each chunk. This will
        determine the actual resolution of the `seconds` and
        `quiet_seconds` values.
    wait_for_sound:
        When ``True``, chunks are discarded until the volume exceeds
        `quiet_threshold` and do not count towards any limits. Once a
        chunk has met the threshold, all chunks are counted.
    on_chunk:
        Optional callback to be invoked on the raw data recorded each
        chunk. This callback should return within `seconds_per_chunk`
        seconds to avoid recording failures.
    device_id:
        The device to record using. If omitted, defaults to the first
        available recording device.
    '''
    if device_id is None:
        device_id = get_playback_devices()[0][1]

    if wav:
        result = None
        channels = wav.getnchannels()
        sample_rate = wav.getframerate()
        bits_per_sample = wav.getsampwidth() * 8
    else:
        result = BytesIO()
        wav = wave.open(result, 'wb')
        wav.setnchannels(channels)
        wav.setframerate(sample_rate)
        wav.setsampwidth(bits_per_sample // 8)

    _on_chunk = _RecordStatus(
        wav,
        bits_per_sample,
        sample_rate,
        quiet_threshold,
        seconds,
        quiet_seconds,
        wait_for_sound,
        on_chunk
    )
    try:
        _record(device_id, wav, seconds_per_chunk, _on_chunk)
    finally:
        if result:
            wav.close()

    if result:
        return result.getvalue()

def get_quiet_threshold(sample_rate=11025, bits_per_sample=8):
    '''Records a short period of time and calculates the RMS volume
    of the clip. This is the same calculation that is used in `record`
    as `quiet_threshold` to determine when silence is being recorded.

    sample_rate:
        Number of samples to record each second. Typically one of
        8000, 11025, 16000, 22050, or 44100.
    bits_per_sample:
        Number of bits of information to record each sample. Must
        be either 8 or 16.
    '''
    rms = [1.0]
    if bits_per_sample == 8:
        def on_chunk(data):
            rms[0] = math.sqrt(sum(((d - 128) / 256) ** 2 for d in data) / len(data))
            return True
    elif bits_per_sample == 16:
        def on_chunk(data):
            arr = array.array('h', data)
            rms[0] = math.sqrt(sum((d / 32768) ** 2 for d in arr) / len(arr))
            return True
    else:
        raise ValueError('cannot record {} bits per sample'.format(bits_per_sample))

    with wave.open(BytesIO(), 'wb') as wav:
        wav.setnchannels(1)
        wav.setframerate(sample_rate)
        wav.setsampwidth(bits_per_sample // 8)
        _record(wav, 0.5, on_chunk)
    return rms[0]
