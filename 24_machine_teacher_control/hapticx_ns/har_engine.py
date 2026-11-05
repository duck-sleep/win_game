"""har_engine.py — 按 HAR.dll 播放 API 抄，不 LoadLibrary。

C 盘导出（RazerProvider 实际 import）：
  ComputeAllEvents
  GetInterhapticsHapticFrame
  GetFrameSize
  GetInterhapticsFrameDecodingData
  AddConnectedDevice

官方循环（InterhapticsEngine.h）：
  ComputeAllEvents(curTime)     ← 把正在播的效果画进每个部位的缓冲
  ProviderRenderHaptics()       ← 再来抽这一帧

Sage T1：部位 216 / 116，触觉流按 1000 Hz、20 ms 一块（20 sample / 掌）。
缓冲是 float32 **包络**（这一拍的振幅），pitch 曲线另记。
马达载波由后面 Provider 编进 Feature 4 的音高档，不在这段 PCM 里。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from har_pack import BODYPART_LEFT, BODYPART_RIGHT, HapticFrame

HAPTIC_FS = 1000.0
PERIOD_S = 0.02
DEVICE_SAGE_T1 = 1


@dataclass
class DecodingPair:
    bodypart_id: int
    n_samples: int


@dataclass
class ConnectedDevice:
    device_id: int
    bodyparts: list[int]
    sample_rate: float = HAPTIC_FS


class HarEngine:
    def __init__(self, sample_rate: float = HAPTIC_FS, period_s: float = PERIOD_S):
        self.sample_rate = float(sample_rate)
        self.period_s = float(period_s)
        self.n_samples = max(1, int(round(self.sample_rate * self.period_s)))
        self.devices: dict[int, ConnectedDevice] = {}
        self.amp: dict[int, np.ndarray] = {}
        self.pitch: dict[int, np.ndarray] = {}
        self.last_transient = False
        self.last_freq_hz = 0.0
        self._phase = {BODYPART_LEFT: 0.0, BODYPART_RIGHT: 0.0}
        self._cur_time = 0.0
        self.add_connected_device(DEVICE_SAGE_T1, [BODYPART_LEFT, BODYPART_RIGHT])

    def add_connected_device(self, device_id: int, bodyparts, sample_rate: float | None = None) -> None:
        fs = float(sample_rate or self.sample_rate)
        bps = [int(x) for x in bodyparts]
        self.devices[int(device_id)] = ConnectedDevice(int(device_id), bps, fs)
        n = self.n_samples
        for bp in bps:
            self.amp[bp] = np.zeros(n, dtype=np.float32)
            self.pitch[bp] = np.zeros(n, dtype=np.float32)
            self._phase.setdefault(bp, 0.0)

    def get_frame_size(self, device_id: int, bodyparts) -> int:
        """HAR.GetFrameSize：返回这一拍缓冲字节数（float32 × sample × 部位）。"""
        if int(device_id) not in self.devices:
            return 0
        nbp = len(bodyparts) if bodyparts is not None else len(self.devices[int(device_id)].bodyparts)
        return int(self.n_samples * nbp * 4)

    def get_interhaptics_frame_decoding_data(self, device_id: int, bodyparts) -> list[DecodingPair]:
        """HAR.GetInterhapticsFrameDecodingData：每个部位 (id, n_samples)。"""
        if int(device_id) not in self.devices:
            return []
        bps = list(bodyparts) if bodyparts is not None else self.devices[int(device_id)].bodyparts
        return [DecodingPair(int(bp), self.n_samples) for bp in bps]

    def get_interhaptics_haptic_frame(self, device_id: int, bodyparts) -> bytes:
        """HAR.GetInterhapticsHapticFrame：按部位顺序拼 float32 PCM。"""
        if int(device_id) not in self.devices:
            return b""
        bps = list(bodyparts) if bodyparts is not None else self.devices[int(device_id)].bodyparts
        chunks = []
        for bp in bps:
            chunks.append(np.asarray(self.amp.get(int(bp), np.zeros(self.n_samples, np.float32)), np.float32))
        if not chunks:
            return b""
        return np.concatenate(chunks).tobytes()

    def compute_all_events(
        self,
        cur_time: float,
        frame: HapticFrame | None,
        gain: float = 1.0,
    ) -> None:
        """HAR.ComputeAllEvents：把当前 parametric 效果画进 216/116 缓冲。"""
        self._cur_time = float(cur_time)
        n = self.n_samples
        for bp in list(self.amp):
            self.amp[bp] = np.zeros(n, dtype=np.float32)
            self.pitch[bp] = np.zeros(n, dtype=np.float32)
        self.last_transient = False
        self.last_freq_hz = 0.0
        if frame is None or not frame.parts:
            return
        g = max(0.0, float(gain))
        left, right, pitch_norm, hit = frame.sample(0.0)
        left = min(max(left * g, 0.0), 1.0)
        right = min(max(right * g, 0.0), 1.0)
        span = frame.pitch_max - frame.pitch_min
        freq = frame.pitch_min + pitch_norm * span if span > 1e-9 else 0.0
        if left <= 0.02 and right <= 0.02 and not hit:
            freq = 0.0
        self.last_transient = bool(hit)
        self.last_freq_hz = float(freq)
        for bp, amp in ((BODYPART_LEFT, left), (BODYPART_RIGHT, right)):
            y = np.full(n, amp, dtype=np.float32)
            if hit and n:
                y[0] = np.float32(min(1.0, amp + 0.35))
            self.amp[bp] = y
            self.pitch[bp] = np.full(n, pitch_norm, dtype=np.float32)
