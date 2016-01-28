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

__all__ = ['play', 'record', 'get_quiet_threshold']

if sys.platform == 'win32':
    import ctypes
    import ctypes.wintypes
    import _winapi

    HWAVEOUT = HWAVEIN = ctypes.wintypes.HANDLE

    class MMRESULT(ctypes.wintypes.DWORD):
        def _check_restype_(self):
            if self:
                raise OSError('error using audio device: {:x}'.format(self))

    WAVE_MAPPER = ctypes.wintypes.UINT(-1)
    WAVE_ALLOWSYNC = 0x00000002
    CALLBACK_EVENT = 0x00050000

    class WAVEFORMATEX(ctypes.Structure):
        _fields_ = [
            ('wFormatTag', ctypes.wintypes.WORD),
            ('nChannels', ctypes.wintypes.WORD),
            ('nSamplesPerSec', ctypes.wintypes.DWORD),
            ('nAvgBytesPerSec', ctypes.wintypes.DWORD),
            ('nBlockAlign', ctypes.wintypes.WORD),
            ('wBitsPerSample', ctypes.wintypes.WORD),
            ('cbSize', ctypes.wintypes.WORD),
        ]

    class WAVEHDR(ctypes.Structure): pass
    LPWAVEHDR = ctypes.POINTER(WAVEHDR)
    WAVEHDR._fields_ = [
        ('lpData', ctypes.wintypes.LPSTR),
        ('dwBufferLength', ctypes.wintypes.DWORD),
        ('dwBytesRecorded', ctypes.wintypes.DWORD),
        ('dwUser', ctypes.c_void_p),
        ('dwFlags', ctypes.wintypes.DWORD),
        ('dwLoops', ctypes.wintypes.DWORD),
        ('lpNext', LPWAVEHDR),
        ('reserved', ctypes.c_void_p),
    ]

    winmm = ctypes.WinDLL("winmm.dll")

    waveOutOpen = winmm.waveOutOpen
    waveOutOpen.argtypes = [
        ctypes.POINTER(HWAVEOUT),
        ctypes.wintypes.UINT,
        ctypes.POINTER(WAVEFORMATEX),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.wintypes.DWORD,
    ]
    waveOutOpen.restype = MMRESULT

    waveOutPrepareHeader = winmm.waveOutPrepareHeader
    waveOutPrepareHeader.argtypes = [HWAVEOUT, LPWAVEHDR, ctypes.wintypes.UINT]
    waveOutPrepareHeader.restype = MMRESULT

    waveOutUnprepareHeader = winmm.waveOutUnprepareHeader
    waveOutUnprepareHeader.argtypes = [HWAVEOUT, LPWAVEHDR, ctypes.wintypes.UINT]
    waveOutUnprepareHeader.restype = MMRESULT

    waveOutWrite = winmm.waveOutWrite
    waveOutWrite.argtypes = [HWAVEOUT, LPWAVEHDR, ctypes.wintypes.UINT]
    waveOutWrite.restype = MMRESULT

    waveOutClose = winmm.waveOutClose
    waveOutClose.argtypes = [HWAVEOUT]
    waveOutClose.restype = MMRESULT

    waveInOpen = winmm.waveInOpen
    waveInOpen.argtypes = [
        ctypes.POINTER(HWAVEIN),
        ctypes.wintypes.UINT,
        ctypes.POINTER(WAVEFORMATEX),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.wintypes.DWORD,
    ]
    waveInOpen.restype = MMRESULT

    waveInPrepareHeader = winmm.waveInPrepareHeader
    waveInPrepareHeader.argtypes = [HWAVEIN, LPWAVEHDR, ctypes.wintypes.UINT]
    waveInPrepareHeader.restype = MMRESULT

    waveInUnprepareHeader = winmm.waveInUnprepareHeader
    waveInUnprepareHeader.argtypes = [HWAVEIN, LPWAVEHDR, ctypes.wintypes.UINT]
    waveInUnprepareHeader.restype = MMRESULT

    waveInAddBuffer = winmm.waveInAddBuffer
    waveInAddBuffer.argtypes = [HWAVEIN, LPWAVEHDR, ctypes.wintypes.UINT]
    waveInAddBuffer.restype = MMRESULT

    waveInStart = winmm.waveInStart
    waveInStart.argtypes = [HWAVEIN]
    waveInStart.restype = MMRESULT

    waveInStop = winmm.waveInStop
    waveInStop.argtypes = [HWAVEIN]
    waveInStop.restype = MMRESULT

    waveInClose = winmm.waveInClose
    waveInClose.argtypes = [HWAVEIN]
    waveInClose.restype = MMRESULT

    kernel32 = ctypes.WinDLL("kernel32.dll")

    CreateEventW = kernel32.CreateEventW
    CreateEventW.argtypes = [ctypes.c_void_p, ctypes.wintypes.BOOL, ctypes.wintypes.BOOL, ctypes.wintypes.LPCWSTR]
    CreateEventW.restype = ctypes.wintypes.HANDLE

    CloseHandle = kernel32.CloseHandle
    CloseHandle.argtypes = [ctypes.wintypes.HANDLE]

    WaitForSingleObject = kernel32.WaitForSingleObject
    WaitForSingleObject.argtypes = [ctypes.wintypes.HANDLE, ctypes.wintypes.DWORD]
    WaitForSingleObject.restype = ctypes.wintypes.DWORD

    def _make_wave_format(wav):
        return WAVEFORMATEX(
            wFormatTag=1, # only support PCM
            nChannels=wav.getnchannels(),
            nSamplesPerSec=wav.getframerate(),
            nAvgBytesPerSec=wav.getsampwidth() * wav.getnchannels() * wav.getframerate(),
            nBlockAlign=wav.getsampwidth() * wav.getnchannels(),
            wBitsPerSample=wav.getsampwidth() * 8,
            cbSize=0,
        )

    def _play(wav):
        evt = CreateEventW(None, True, False, None)

        try:
            fmt = _make_wave_format(wav)
            handle = HWAVEOUT()
            waveOutOpen(
                ctypes.byref(handle),
                WAVE_MAPPER,
                ctypes.byref(fmt),
                evt,
                None,
                WAVE_ALLOWSYNC | (CALLBACK_EVENT if evt else 0)
            )

            try:
                # TODO: Use smaller buffers and read repeatedly to handle large files
                data = wav.readframes(wav.getnframes())
                hdr = WAVEHDR(lpData=data, dwBufferLength=len(data))
                waveOutPrepareHeader(handle, ctypes.byref(hdr), ctypes.sizeof(hdr))
                waveOutWrite(handle, ctypes.byref(hdr), ctypes.sizeof(hdr))

                # Wait for notifications from the playback
                while WaitForSingleObject(evt, 500) == 0 and (hdr.dwFlags & 1) == 0:
                    pass

                waveOutUnprepareHeader(handle, ctypes.byref(hdr), ctypes.sizeof(hdr))
            finally:
                waveOutClose(handle)
        finally:
            CloseHandle(evt)

    def _record(wav, seconds_per_chunk, on_chunk):
        fmt = _make_wave_format(wav)
        bytes_per_sec = wav.getsampwidth() * wav.getframerate() * wav.getnchannels()

        try:
            should_skip = on_chunk.should_skip
        except AttributeError:
            should_skip = None

        evt = CreateEventW(None, True, False, None)
        try:
            handle = HWAVEIN()
            waveInOpen(
                ctypes.byref(handle),
                WAVE_MAPPER,
                ctypes.byref(fmt),
                evt,
                None,
                CALLBACK_EVENT
            )

            try:
                buffer = ctypes.create_string_buffer(int(bytes_per_sec * seconds_per_chunk))
                hdr = WAVEHDR(lpData=ctypes.cast(buffer, ctypes.c_char_p), dwBufferLength=len(buffer))
                back_buffer = ctypes.create_string_buffer(int(bytes_per_sec * seconds_per_chunk))
                back_hdr = WAVEHDR(lpData=ctypes.cast(back_buffer, ctypes.c_char_p), dwBufferLength=len(back_buffer))

                waveInStart(handle)
                try:
                    waveInPrepareHeader(handle, ctypes.byref(hdr), ctypes.sizeof(hdr))
                    waveInAddBuffer(handle, ctypes.byref(hdr), ctypes.sizeof(hdr))
                    waveInPrepareHeader(handle, ctypes.byref(back_hdr), ctypes.sizeof(back_hdr))
                    waveInAddBuffer(handle, ctypes.byref(back_hdr), ctypes.sizeof(back_hdr))

                    while True:
                        # Wait for notifications from the playback
                        while WaitForSingleObject(evt, 500) == 0:
                            if (hdr.dwFlags & 1) == 1:
                                break

                        heard = buffer.raw[:hdr.dwBytesRecorded]
                        if not should_skip or not should_skip(heard):
                            wav.writeframes(heard)
                            if on_chunk(heard):
                                wav.close()
                                return

                        waveInUnprepareHeader(handle, ctypes.byref(hdr), ctypes.sizeof(hdr))
                        waveInPrepareHeader(handle, ctypes.byref(hdr), ctypes.sizeof(hdr))
                        waveInAddBuffer(handle, ctypes.byref(hdr), ctypes.sizeof(hdr))
                        hdr, buffer, back_hdr, back_buffer = back_hdr, back_buffer, hdr, buffer
                finally:
                    waveInStop(handle)
            finally:
                waveInClose(handle)
        finally:
            CloseHandle(evt)

else:
    def _play(wav):
        raise NotImplementedError('play is not implemented for platform {}'.format(sys.platform))

    def _record(wav, seconds_per_chunk, on_chunk):
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

def play(wav):
    '''Plays a wave file using the user's default playback device.
    The function will block until playback is complete.

    wav:
        An open `wave.Wave_read` object, a `bytes` object containing
        a wave file, or a valid argument to `wave.open`.
    '''
    with _open_wav(wav) as w:
        return _play(w)

class _RecordStatus(object):
    def __init__(
        self,
        bits_per_sample,
        sample_rate,
        quiet_threshold,
        max_seconds=0,
        max_quiet_seconds=0,
        lstrip_quiet=True,
        on_call=None
    ):
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

    def should_skip(self, chunk):
        if self.lstrip_quiet:
            if self.is_quiet(chunk):
                return True
            self.lstrip_quiet = False

    def __call__(self, chunk):
        if self.on_call:
            self.on_call(chunk)

        s = len(chunk) / self.bytes_per_second
        self.seconds += s
        if self.max_seconds > 0 and self.seconds >= self.max_seconds:
            return True

        if self.max_quiet_seconds <= 0:
            return False

        if self.is_quiet(chunk):
            self.quiet_seconds += s
        else:
            self.quiet_seconds = 0
        return self.quiet_seconds >= self.max_quiet_seconds


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
    on_chunk=None
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
    '''
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
        bits_per_sample,
        sample_rate,
        quiet_threshold,
        seconds,
        quiet_seconds,
        wait_for_sound,
        on_chunk
    )
    try:
        _record(wav, seconds_per_chunk, _on_chunk)
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
