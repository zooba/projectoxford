#-------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation 
# All rights reserved. 
# 
# Distributed under the terms of the MIT License
#-------------------------------------------------------------------------

# cython: language_level=3
# distutils: libraries = winmm

cdef extern from "windows.h":
    ctypedef bint BOOL
    ctypedef int WORD
    ctypedef int DWORD
    ctypedef int UINT
    ctypedef int DWORD_PTR
    ctypedef int UINT_PTR
    ctypedef char* LPSTR
    ctypedef void* HANDLE
    ctypedef void* HWAVEIN
    ctypedef void* HWAVEOUT
    ctypedef int MMRESULT
    ctypedef int MMVERSION
    ctypedef unicode LPCWSTR
    
    DWORD WAVE_MAPPER
    DWORD WAVE_ALLOWSYNC
    DWORD CALLBACK_EVENT
    
    DWORD WAVE_FORMAT_PCM
    
    MMRESULT MMSYSERR_NOERROR, MMSYSERR_INVALHANDLE, MMSYSERR_NODRIVER, MMSYSERR_NOMEM
    MMRESULT WAVERR_STILLPLAYING
    
    ctypedef struct WAVEFORMATEX:
        WORD  wFormatTag
        WORD  nChannels
        DWORD nSamplesPerSec
        DWORD nAvgBytesPerSec
        WORD  nBlockAlign
        WORD  wBitsPerSample
        WORD  cbSize

    ctypedef struct WAVEHDR:
        LPSTR     lpData
        DWORD     dwBufferLength
        DWORD     dwBytesRecorded
        DWORD_PTR dwUser
        DWORD     dwFlags
        DWORD     dwLoops
        WAVEHDR*  lpNext
        DWORD_PTR reserved
    
    void ZeroMemory(void*, UINT) nogil
    
    MMRESULT waveOutOpen(HWAVEOUT*, UINT, WAVEFORMATEX*, DWORD_PTR, DWORD_PTR, DWORD) nogil
    MMRESULT waveOutReset(HWAVEOUT) nogil
    MMRESULT waveOutClose(HWAVEOUT) nogil
    MMRESULT waveOutPrepareHeader(HWAVEOUT, WAVEHDR*, UINT) nogil
    MMRESULT waveOutUnprepareHeader(HWAVEOUT, WAVEHDR*, UINT) nogil
    MMRESULT waveOutWrite(HWAVEOUT, WAVEHDR*, UINT) nogil

    MMRESULT waveInOpen(HWAVEIN*, UINT, WAVEFORMATEX*, DWORD_PTR, DWORD_PTR, DWORD) nogil
    MMRESULT waveInStart(HWAVEIN) nogil
    MMRESULT waveInStop(HWAVEIN) nogil
    MMRESULT waveInReset(HWAVEIN) nogil
    MMRESULT waveInClose(HWAVEIN) nogil
    MMRESULT waveInPrepareHeader(HWAVEIN, WAVEHDR*, UINT) nogil
    MMRESULT waveInUnprepareHeader(HWAVEIN, WAVEHDR*, UINT) nogil
    MMRESULT waveInAddBuffer(HWAVEIN, WAVEHDR*, UINT) nogil
    MMRESULT waveOutWrite(HWAVEIN, WAVEHDR*, UINT) nogil

    ctypedef struct WAVEINCAPSW:
        WORD wMid
        WORD wPid
        MMVERSION vDriverVersion
        Py_UNICODE[32] szPname
        DWORD dwFormats
        WORD wChannels
        WORD wReserved1
    
    ctypedef struct WAVEOUTCAPSW:
        WORD wMid
        WORD wPid
        MMVERSION vDriverVersion
        Py_UNICODE[32] szPname
        DWORD dwFormats
        WORD wChannels
        WORD wReserved1
        DWORD dwSupport

    UINT waveInGetNumDevs() nogil
    UINT waveInGetDevCapsW(UINT_PTR, WAVEINCAPSW*, UINT) nogil
    UINT waveOutGetNumDevs() nogil
    UINT waveOutGetDevCapsW(UINT_PTR, WAVEOUTCAPSW*, UINT) nogil

    MMRESULT waveInGetErrorTextW(MMRESULT, Py_UNICODE*, UINT) nogil
    MMRESULT waveOutGetErrorTextW(MMRESULT, Py_UNICODE*, UINT) nogil

    HANDLE CreateEventW(void*, BOOL, BOOL, LPCWSTR) nogil
    void CloseHandle(HANDLE) nogil
    DWORD WaitForSingleObject(HANDLE, DWORD) nogil

ERROR_CODES = {
    WAVERR_STILLPLAYING: "WAVERR_STILLPLAYING",
    MMSYSERR_INVALHANDLE: "MMSYSERR_INVALHANDLE",
    MMSYSERR_NODRIVER: "MMSYSERR_NODRIVER",
    MMSYSERR_NOMEM: "MMSYSERR_NOMEM",
}

cdef int check_mmresult(MMRESULT r, str cause, bint for_in) nogil except? -1:
    cdef Py_UNICODE[256] msg
    if r == MMSYSERR_NOERROR:
        return 0
    if for_in:
        r2 = waveInGetErrorTextW(r, msg, 256)
    else:
        r2 = waveOutGetErrorTextW(r, msg, 256)
    with gil:
        if r2:
            msg = ERROR_CODES.get(r, 'UNKNOWN_ERROR')
        raise OSError("Failed to {}: {} (0x{:x})".format(<str>cause, msg, r))

cdef int check_mmr_in(MMRESULT r, str cause) nogil except? -1:
    return check_mmresult(r, cause, 1)

cdef int check_mmr_out(MMRESULT r, str cause) nogil except? -1:
    return check_mmresult(r, cause, 0)


def _get_playback_devices():
    cdef WAVEOUTCAPSW caps
    devs = [("Default", WAVE_MAPPER)]
    for i in range(waveOutGetNumDevs()):
        dw_i = <UINT_PTR>i
        with nogil:
            check_mmr_out(waveOutGetDevCapsW(dw_i, &caps, sizeof(WAVEOUTCAPSW)), "get device capabilities")
        devs.append((<unicode>caps.szPname, i))
    return devs

def _get_recording_devices():
    cdef WAVEINCAPSW caps
    devs = [("Default", WAVE_MAPPER)]
    for i in range(waveInGetNumDevs()):
        dw_i = <UINT_PTR>i
        with nogil:
            check_mmr_in(waveInGetDevCapsW(dw_i, &caps, sizeof(WAVEINCAPSW)), "get device capabilities")
        devs.append((<unicode>caps.szPname, i, caps.wChannels))
    return devs


cdef void hdr_in_prepare_add(HWAVEIN hw, WAVEHDR* w):
    with nogil:
        check_mmr_in(waveInPrepareHeader(hw, w, sizeof(WAVEHDR)), "prepare audio buffer")
        check_mmr_in(waveInAddBuffer(hw, w, sizeof(WAVEHDR)), "add audio buffer")

cdef void hdr_in_unprepare(HWAVEIN hw, WAVEHDR* w):
    with nogil:
        check_mmr_in(waveInUnprepareHeader(hw, w, sizeof(WAVEHDR)), "unprepare audio buffer")

cdef void hdr_out_prepare_write(HWAVEOUT hw, WAVEHDR* w):
    with nogil:
        check_mmr_out(waveOutPrepareHeader(hw, w, sizeof(WAVEHDR)), "prepare audio data")
        check_mmr_out(waveOutWrite(hw, w, sizeof(WAVEHDR)), "write audio data")

cdef void hdr_out_unprepare(HWAVEOUT hw, WAVEHDR* w):
    with nogil:
        check_mmr_out(waveOutUnprepareHeader(hw, w, sizeof(WAVEHDR)), "unprepare audio buffer")


cdef class PlaybackDevice:
    cdef HWAVEOUT _c_hw
    cdef WAVEFORMATEX _c_fmt
    cdef HANDLE _c_evt
    
    def __cinit__(
        self,
        DWORD dev_id,
        int nchannels,
        int framerate,
        int sampwidth
    ):
        self._c_evt = CreateEventW(NULL, True, False, None)
        
        self._c_fmt.wFormatTag = WAVE_FORMAT_PCM
        self._c_fmt.nChannels = nchannels
        self._c_fmt.nSamplesPerSec = framerate
        self._c_fmt.nAvgBytesPerSec = sampwidth * nchannels * framerate
        self._c_fmt.nBlockAlign = sampwidth * nchannels
        self._c_fmt.wBitsPerSample = sampwidth * 8
        self._c_fmt.cbSize = 0
        
        with nogil:
            check_mmr_out(waveOutOpen(
                &self._c_hw,
                dev_id,
                &self._c_fmt,
                <DWORD_PTR>self._c_evt,
                0,
                WAVE_ALLOWSYNC | CALLBACK_EVENT
            ), "open audio device")
    
    def close(self):
        '''Closes this device.'''
        with nogil:
            CloseHandle(self._c_evt)
            check_mmr_out(waveOutReset(self._c_hw), "reset audio device")
            check_mmr_out(waveOutClose(self._c_hw), "close audio device")
    
    def play(self, get_data):
        '''Streams audio to this device from a callback function.
        
        get_data
            A callback that returns the next buffer of data. To cancel
            playback, return None, an empty buffer, or raise an
            exception.
        '''
        cdef HWAVEOUT hw = self._c_hw
        cdef WAVEHDR hdr1, hdr2
        cdef WAVEHDR *phdr
        cdef WAVEHDR *pnext_hdr
        data = get_data()
        data2 = None
        if not data:
            return
        
        with nogil:
            ZeroMemory(&hdr1, sizeof(WAVEHDR))
            ZeroMemory(&hdr2, sizeof(WAVEHDR))
        
        phdr = &hdr1
        pnext_hdr = &hdr2
        pnext_hdr.lpData = data
        pnext_hdr.dwBufferLength = len(data)
        
        hdr_out_prepare_write(hw, pnext_hdr)
        
        exit = False
        while not exit:
            phdr, pnext_hdr = pnext_hdr, phdr
            data2, data = data, data2
            
            success = False
            try:
                data = get_data()
                success = True
            finally:
                if not success:
                    with nogil:
                        check_mmr_out(waveOutReset(hw), "reset audio device")
                    hdr_out_unprepare(hw, phdr)
            if data:
                pnext_hdr.lpData = data
                pnext_hdr.dwBufferLength = len(data)
                
                hdr_out_prepare_write(hw, pnext_hdr)
            else:
                exit = True
            
            while True:
                with nogil:
                    r = WaitForSingleObject(self._c_evt, 500)
                if r != 0 or (phdr.dwFlags & 1) == 1:
                    break
            
            hdr_out_unprepare(hw, phdr)

cdef class RecordingDevice:
    cdef HWAVEIN _c_hw
    cdef WAVEFORMATEX _c_fmt
    cdef HANDLE _c_evt
    
    def __cinit__(
        self,
        DWORD dev_id,
        int nchannels,
        int framerate,
        int sampwidth
    ):
        self._c_evt = CreateEventW(NULL, True, False, None)
        
        self._c_fmt.wFormatTag = WAVE_FORMAT_PCM
        self._c_fmt.nChannels = nchannels
        self._c_fmt.nSamplesPerSec = framerate
        self._c_fmt.nAvgBytesPerSec = sampwidth * nchannels * framerate
        self._c_fmt.nBlockAlign = sampwidth * nchannels
        self._c_fmt.wBitsPerSample = sampwidth * 8
        self._c_fmt.cbSize = 0
        
        with nogil:
            check_mmr_in(waveInOpen(
                &self._c_hw,
                dev_id,
                &self._c_fmt,
                <DWORD_PTR>self._c_evt,
                0,
                CALLBACK_EVENT
            ), "open audio device")
    
    def close(self):
        '''Closes this device.'''
        with nogil:
            CloseHandle(self._c_evt)
            check_mmr_in(waveInReset(self._c_hw), "reset audio device")
            check_mmr_in(waveInClose(self._c_hw), "close audio device")
    
    def record(self, int samples, on_chunk):
        '''Records audio from this device into a callback function.
        
        samples
            The number of samples to record before calling `on_chunk`
        on_chunk
            A function taking a memoryview of the recorded data.
            Return True to record another chunk. This function must
            return within `samples` time to avoid missing data.
        '''
        cdef HWAVEIN hw = self._c_hw
        cdef WAVEHDR hdr1, hdr2
        cdef WAVEHDR *phdr
        cdef WAVEHDR *pnext_hdr
        phdr = &hdr1
        pnext_hdr = &hdr2
        
        ZeroMemory(phdr, sizeof(WAVEHDR))
        ZeroMemory(pnext_hdr, sizeof(WAVEHDR))
        
        data1 = bytearray(self._c_fmt.nBlockAlign * samples)
        data2 = bytearray(self._c_fmt.nBlockAlign * samples)
        
        phdr.lpData = data1
        phdr.dwBufferLength = len(data1)
        pnext_hdr.lpData = data2
        pnext_hdr.dwBufferLength = len(data2)
        
        hdr_in_prepare_add(hw, phdr)
        
        with nogil:
            check_mmr_in(waveInStart(hw), "start recording")

        try:
            another = True
            while another:
                hdr_in_prepare_add(hw, pnext_hdr)
                
                while True:
                    with nogil:
                        r = WaitForSingleObject(self._c_evt, 500)
                    if r != 0 or (phdr.dwFlags & 1) == 1:
                        break

                success = False
                try:
                    another = bool(on_chunk(data1))
                    success = True
                finally:
                    hdr_in_unprepare(hw, phdr)
                    if not success:
                        another = False
                        with nogil:
                            check_mmr_in(waveInReset(hw), "reset audio device")
                        hdr_in_unprepare(hw, pnext_hdr)
                phdr, pnext_hdr = pnext_hdr, phdr
                data1, data2 = data2, data1
        finally:
            with nogil:
                check_mmr_in(waveInStop(hw), "stop recording")
        