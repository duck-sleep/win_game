"""wasapi_loopback.py — 按 C 盘 CAudioRecorder<float> 抄的 WASAPI 环回。

不加载 RzAudioCapture / 任何雷云入口 DLL。按 C 盘里那套行为自己写：
  IMMDevice 渲染端 → IAudioClient GetMixFormat
  AUDCLNT_SHAREMODE_SHARED + LOOPBACK
  IAudioCaptureClient GetNextPacketSize / GetBuffer / ReleaseBuffer
  跟设备 mix 的采样率/通道，float32，完整帧，约 20ms 一块
  端点音量为 0 或静音时送全零（官方是 skip 编码）
"""
from __future__ import annotations

import ctypes
from ctypes import (
    POINTER, Structure, WINFUNCTYPE, byref, c_byte, c_float, c_int16,
    c_int32, c_int64, c_long, c_uint32, c_uint64, c_ushort, c_void_p,
    c_wchar_p,
)
from ctypes import wintypes

import numpy as np

ole32 = ctypes.WinDLL("ole32")
ole32.CoInitializeEx.argtypes = [c_void_p, c_uint32]
ole32.CoInitializeEx.restype = c_long
ole32.CoUninitialize.argtypes = []
ole32.CoCreateInstance.argtypes = [
    c_void_p, c_void_p, c_uint32, c_void_p, POINTER(c_void_p),
]
ole32.CoCreateInstance.restype = c_long
ole32.CoTaskMemFree.argtypes = [c_void_p]

COINIT_MULTITHREADED = 0x0
CLSCTX_ALL = 0x17
RPC_E_CHANGED_MODE = 0x80010106
S_OK = 0
S_FALSE = 1

eRender = 0
eConsole = 0
AUDCLNT_SHAREMODE_SHARED = 0
AUDCLNT_STREAMFLAGS_LOOPBACK = 0x00020000
AUDCLNT_BUFFERFLAGS_SILENT = 0x2
WAVE_FORMAT_PCM = 1
WAVE_FORMAT_IEEE_FLOAT = 3
WAVE_FORMAT_EXTENSIBLE = 0xFFFE
PERIOD_MS = 20
BUFFER_HNS = 1000000  # 100 ms in 100-ns units

KSDATAFORMAT_SUBTYPE_IEEE_FLOAT = bytes.fromhex(
    "0300000000001000800000aa00389b71")
KSDATAFORMAT_SUBTYPE_PCM = bytes.fromhex(
    "0100000000001000800000aa00389b71")


class GUID(Structure):
    _fields_ = [
        ("Data1", c_uint32),
        ("Data2", c_ushort),
        ("Data3", c_ushort),
        ("Data4", c_byte * 8),
    ]


def _guid(text: str) -> GUID:
    text = text.strip("{}")
    p = text.split("-")
    g = GUID()
    g.Data1 = int(p[0], 16)
    g.Data2 = int(p[1], 16)
    g.Data3 = int(p[2], 16)
    rest = p[3] + p[4]
    for i in range(8):
        g.Data4[i] = int(rest[i * 2:i * 2 + 2], 16)
    return g


CLSID_MMDeviceEnumerator = _guid("BCDE0395-E52F-467C-8E3D-C4579291692E")
IID_IMMDeviceEnumerator = _guid("A95664D2-9614-4F35-A746-DE8DB63617E6")
IID_IAudioClient = _guid("1CB9AD4C-DBFA-4c32-B178-C2F568A703B2")
IID_IAudioCaptureClient = _guid("C8ADBD64-E71E-48a0-A4DE-185C395CD317")
IID_IAudioEndpointVolume = _guid("5CDF2C82-841E-4546-9722-0CF74078229A")


class WAVEFORMATEX(Structure):
    _pack_ = 1
    _fields_ = [
        ("wFormatTag", c_ushort),
        ("nChannels", c_ushort),
        ("nSamplesPerSec", c_uint32),
        ("nAvgBytesPerSec", c_uint32),
        ("nBlockAlign", c_ushort),
        ("wBitsPerSample", c_ushort),
        ("cbSize", c_ushort),
    ]


def _vcall(this: int, idx: int, proto):
    vtbl = c_uint64.from_address(this).value
    return proto(c_uint64.from_address(vtbl + idx * 8).value)


def _release(this: int | None):
    if not this:
        return
    _vcall(this, 2, WINFUNCTYPE(c_uint32, c_void_p))(this)


def _hr_ok(hr: int) -> bool:
    return int(hr) >= 0


def _co_init():
    hr = ole32.CoInitializeEx(None, COINIT_MULTITHREADED)
    return hr in (S_OK, S_FALSE) or (hr & 0xFFFFFFFF) == RPC_E_CHANGED_MODE


def _enumerator() -> int:
    ptr = c_void_p()
    hr = ole32.CoCreateInstance(
        ctypes.byref(CLSID_MMDeviceEnumerator), None, CLSCTX_ALL,
        ctypes.byref(IID_IMMDeviceEnumerator), byref(ptr),
    )
    if not _hr_ok(hr) or not ptr.value:
        raise OSError(f"CoCreateInstance MMDeviceEnumerator hr=0x{hr & 0xFFFFFFFF:08X}")
    return ptr.value


def _get_device(enum_ptr: int, endpoint_id: str | None) -> int:
    device = c_void_p()
    if endpoint_id:
        get_dev = _vcall(
            enum_ptr, 5,
            WINFUNCTYPE(c_long, c_void_p, c_wchar_p, POINTER(c_void_p)),
        )
        hr = get_dev(enum_ptr, endpoint_id, byref(device))
        if _hr_ok(hr) and device.value:
            return device.value
    get_def = _vcall(
        enum_ptr, 4,
        WINFUNCTYPE(c_long, c_void_p, c_int32, c_int32, POINTER(c_void_p)),
    )
    hr = get_def(enum_ptr, eRender, eConsole, byref(device))
    if not _hr_ok(hr) or not device.value:
        raise OSError(f"GetDefaultAudioEndpoint hr=0x{hr & 0xFFFFFFFF:08X}")
    return device.value


def _device_id(device: int) -> str:
    pw = c_wchar_p()
    hr = _vcall(device, 5, WINFUNCTYPE(c_long, c_void_p, POINTER(c_wchar_p)))(
        device, byref(pw))
    if not _hr_ok(hr) or not pw:
        return ""
    text = pw.value or ""
    ole32.CoTaskMemFree(pw)
    return text


def _activate(device: int, iid: GUID) -> int:
    out = c_void_p()
    hr = _vcall(
        device, 3,
        WINFUNCTYPE(
            c_long, c_void_p, c_void_p, c_uint32, c_void_p, POINTER(c_void_p)),
    )(device, ctypes.byref(iid), CLSCTX_ALL, None, byref(out))
    if not _hr_ok(hr) or not out.value:
        raise OSError(f"IMMDevice.Activate hr=0x{hr & 0xFFFFFFFF:08X}")
    return out.value


def _mix_format(client: int) -> tuple[int, WAVEFORMATEX, bool]:
    """返回 (CoTaskMem 指针, 基本 WAVEFORMATEX 拷贝, 是否 float)。调用方 Initialize 后再 CoTaskMemFree。"""
    fmt_p = c_void_p()
    hr = _vcall(client, 8, WINFUNCTYPE(c_long, c_void_p, POINTER(c_void_p)))(
        client, byref(fmt_p))
    if not _hr_ok(hr) or not fmt_p.value:
        raise OSError(f"GetMixFormat hr=0x{hr & 0xFFFFFFFF:08X}")
    copied = WAVEFORMATEX()
    ctypes.memmove(ctypes.addressof(copied), fmt_p.value, ctypes.sizeof(WAVEFORMATEX))
    is_float = copied.wFormatTag == WAVE_FORMAT_IEEE_FLOAT
    if copied.wFormatTag == WAVE_FORMAT_EXTENSIBLE and copied.cbSize >= 22:
        sub = (c_byte * 16).from_address(fmt_p.value + ctypes.sizeof(WAVEFORMATEX) + 6)
        is_float = bytes(sub) == KSDATAFORMAT_SUBTYPE_IEEE_FLOAT
    return fmt_p.value, copied, is_float


def _endpoint_volume(device: int) -> tuple[float, bool]:
    vol = None
    try:
        vol = _activate(device, IID_IAudioEndpointVolume)
        level = c_float(1.0)
        hr = _vcall(vol, 9, WINFUNCTYPE(c_long, c_void_p, POINTER(c_float)))(
            vol, byref(level))
        mute = wintypes.BOOL(0)
        hr2 = _vcall(vol, 15, WINFUNCTYPE(c_long, c_void_p, POINTER(wintypes.BOOL)))(
            vol, byref(mute))
        if not _hr_ok(hr):
            return 1.0, False
        muted = bool(mute.value) if _hr_ok(hr2) else False
        return float(level.value), muted
    except OSError:
        return 1.0, False
    finally:
        _release(vol)


def _pcm_to_float(data_ptr: int, nframes: int, nch: int, bits: int, is_float: bool):
    n = nframes * nch
    if n <= 0:
        return np.zeros((0, nch), dtype=np.float32)
    if is_float and bits == 32:
        raw = np.ctypeslib.as_array((c_float * n).from_address(data_ptr))
        return raw.copy().reshape(nframes, nch)
    if bits == 16:
        raw = np.ctypeslib.as_array((c_int16 * n).from_address(data_ptr))
        return (raw.astype(np.float32) / 32768.0).reshape(nframes, nch)
    if bits == 32 and not is_float:
        raw = np.ctypeslib.as_array((c_int32 * n).from_address(data_ptr))
        return (raw.astype(np.float32) / 2147483648.0).reshape(nframes, nch)
    raise OSError(f"unsupported mix format bits={bits} float={is_float}")


def resolve_endpoint(device_name=None) -> tuple[str, str]:
    """(friendly_name, WASAPI endpointId). 用 soundcard 只做名字→id，不采 PCM。"""
    import soundcard as sc
    if device_name:
        speaker = sc.get_speaker(device_name)
    else:
        speaker = sc.default_speaker()
    return speaker.name, str(speaker.id)


class WasapiLoopback:
    """阻塞读一块 ~period_ms 的 float32 (frames, channels)。"""

    def __init__(self, endpoint_id: str | None = None, period_ms: int = PERIOD_MS):
        self.endpoint_id = endpoint_id
        self.period_ms = int(period_ms)
        self.sample_rate = 48000
        self.n_channels = 2
        self.volume = 1.0
        self.muted = False
        self._enum = None
        self._device = None
        self._client = None
        self._dummy = None
        self._capture = None
        self._is_float = True
        self._bits = 32
        self._pending = None
        self._inited_com = False

    def open(self):
        self._inited_com = _co_init()
        self._enum = _enumerator()
        self._device = _get_device(self._enum, self.endpoint_id)
        got_id = _device_id(self._device)
        if got_id:
            self.endpoint_id = got_id
    def _initialize(self, client: int, flags: int, fmt_ptr: int):
        init = _vcall(
            client, 3,
            WINFUNCTYPE(
                c_long, c_void_p, c_int32, c_uint32, c_int64, c_int64,
                c_void_p, c_void_p),
        )
        hr = init(
            client, AUDCLNT_SHAREMODE_SHARED, flags,
            BUFFER_HNS, 0, fmt_ptr, None,
        )
        if not _hr_ok(hr):
            raise OSError(
                f"IAudioClient.Initialize flags=0x{flags:X} hr=0x{hr & 0xFFFFFFFF:08X}")

    def _start(self, client: int):
        hr = _vcall(client, 10, WINFUNCTYPE(c_long, c_void_p))(client)
        if not _hr_ok(hr):
            raise OSError(f"IAudioClient.Start hr=0x{hr & 0xFFFFFFFF:08X}")

    def open(self):
        self._inited_com = _co_init()
        self._enum = _enumerator()
        self._device = _get_device(self._enum, self.endpoint_id)
        got_id = _device_id(self._device)
        if got_id:
            self.endpoint_id = got_id
        probe = _activate(self._device, IID_IAudioClient)
        fmt_ptr, fmt, self._is_float = _mix_format(probe)
        self.sample_rate = int(fmt.nSamplesPerSec)
        self.n_channels = int(fmt.nChannels)
        self._bits = int(fmt.wBitsPerSample)
        try:
            try:
                self._dummy = _activate(self._device, IID_IAudioClient)
                self._initialize(self._dummy, 0, fmt_ptr)
                self._start(self._dummy)
            except OSError:
                _release(self._dummy)
                self._dummy = None
            self._client = probe
            probe = None
            self._initialize(self._client, AUDCLNT_STREAMFLAGS_LOOPBACK, fmt_ptr)
        finally:
            _release(probe)
            ole32.CoTaskMemFree(fmt_ptr)
        svc = c_void_p()
        hr = _vcall(
            self._client, 14,
            WINFUNCTYPE(c_long, c_void_p, c_void_p, POINTER(c_void_p)),
        )(self._client, ctypes.byref(IID_IAudioCaptureClient), byref(svc))
        if not _hr_ok(hr) or not svc.value:
            raise OSError(f"GetService IAudioCaptureClient hr=0x{hr & 0xFFFFFFFF:08X}")
        self._capture = svc.value
        self._start(self._client)
        self._pending = np.zeros((0, self.n_channels), dtype=np.float32)
        self._refresh_volume()

    def _refresh_volume(self):
        if not self._device:
            return
        self.volume, self.muted = _endpoint_volume(self._device)

    def _pull_packet(self) -> np.ndarray | None:
        nnext = c_uint32(0)
        hr = _vcall(
            self._capture, 5,
            WINFUNCTYPE(c_long, c_void_p, POINTER(c_uint32)),
        )(self._capture, byref(nnext))
        if not _hr_ok(hr) or nnext.value == 0:
            return None
        data = c_void_p()
        nframes = c_uint32(0)
        flags = c_uint32(0)
        hr = _vcall(
            self._capture, 3,
            WINFUNCTYPE(
                c_long, c_void_p, POINTER(c_void_p), POINTER(c_uint32),
                POINTER(c_uint32), c_void_p, c_void_p),
        )(self._capture, byref(data), byref(nframes), byref(flags), None, None)
        if not _hr_ok(hr):
            return None
        n = int(nframes.value)
        nch = self.n_channels
        if n == 0:
            _vcall(self._capture, 4, WINFUNCTYPE(c_long, c_void_p, c_uint32))(
                self._capture, 0)
            return None
        if flags.value & AUDCLNT_BUFFERFLAGS_SILENT or not data.value:
            block = np.zeros((n, nch), dtype=np.float32)
        else:
            block = _pcm_to_float(data.value, n, nch, self._bits, self._is_float)
        _vcall(self._capture, 4, WINFUNCTYPE(c_long, c_void_p, c_uint32))(
            self._capture, nframes)
        return block

    def read_block(self, stop_event=None) -> np.ndarray:
        """返回 (period_frames, n_channels) float32，完整帧。"""
        period = max(1, self.sample_rate * self.period_ms // 1000)
        import time
        idle_ms = 0
        while True:
            if stop_event is not None and stop_event.is_set():
                return np.zeros((0, self.n_channels), dtype=np.float32)
            pkt = self._pull_packet()
            if pkt is None:
                time.sleep(0.003)
                idle_ms += 3
                if idle_ms >= self.period_ms and self._pending.shape[0] == 0:
                    self._refresh_volume()
                    return np.zeros((period, self.n_channels), dtype=np.float32)
                continue
            idle_ms = 0
            self._pending = np.concatenate([self._pending, pkt], axis=0)
            if self._pending.shape[0] >= period:
                out = self._pending[:period]
                self._pending = self._pending[period:]
                self._refresh_volume()
                if self.muted or self.volume <= 1e-4:
                    return np.zeros_like(out)
                return out

    def close(self):
        for client in (self._client, self._dummy):
            if client:
                try:
                    _vcall(client, 11, WINFUNCTYPE(c_long, c_void_p))(client)
                except OSError:
                    pass
        _release(self._capture)
        _release(self._client)
        _release(self._dummy)
        _release(self._device)
        _release(self._enum)
        self._capture = self._client = self._dummy = self._device = self._enum = None
        if self._inited_com:
            try:
                ole32.CoUninitialize()
            except OSError:
                pass
            self._inited_com = False
