"""haptic_mixer.py — 按 C 盘 HapticService service-config 抄的混音器，不 LoadLibrary。

本机 JSON 原文：
  priority.controller = ["SDK", "Modding", "Synesthesia", "A2H"]   # 左高右低
  volumes.native      = 0.6705882352941176
Synapse 日志：change the 254 volume to 0.670588

HapticX 这条产品链只有 A2H 源。更高优先级源一旦 active，A2H 被压掉。
混音器对 A2H 振幅/瞬态乘 0.67；pitch 不乘音量。
"""
from __future__ import annotations

from dataclasses import dataclass

from har_pack import HapticFrame

PRIORITY = ("SDK", "Modding", "Synesthesia", "A2H")
A2H_GAIN = 0.6705882352941176


@dataclass
class MixedSample:
    left: float
    right: float
    pitch_norm: float
    freq_hz: float
    amp: float
    transient: bool
    source: str | None
    gain: float
    frame: HapticFrame | None = None


class HapticMixer:
    def __init__(self, a2h_gain: float = A2H_GAIN):
        self.gains = {
            "SDK": 1.0,
            "Modding": 1.0,
            "Synesthesia": 1.0,
            "A2H": float(a2h_gain),
        }
        self._frames: dict[str, HapticFrame | None] = {n: None for n in PRIORITY}

    def set_gain(self, source: str, gain: float) -> None:
        if source in self.gains:
            self.gains[source] = max(0.0, min(1.0, float(gain)))

    def set_a2h_gain(self, gain: float) -> None:
        self.set_gain("A2H", gain)

    def submit(self, source: str, frame: HapticFrame | None) -> None:
        if source in self._frames:
            self._frames[source] = frame

    def submit_a2h(self, frame: HapticFrame | None) -> MixedSample:
        self.submit("A2H", frame)
        return self.mix()

    def clear(self, source: str | None = None) -> None:
        if source is None:
            for k in self._frames:
                self._frames[k] = None
        elif source in self._frames:
            self._frames[source] = None

    def mix(self, t: float = 0.0) -> MixedSample:
        # 左到右：SDK 压 Modding 压 Synesthesia 压 A2H
        for name in PRIORITY:
            frame = self._frames.get(name)
            if frame is None or not frame.parts:
                continue
            left, right, pitch_norm, hit = frame.sample(t)
            gain = self.gains.get(name, 1.0)
            if name == "A2H":
                left *= gain
                right *= gain
            left = min(max(left, 0.0), 1.0)
            right = min(max(right, 0.0), 1.0)
            span = frame.pitch_max - frame.pitch_min
            freq = frame.pitch_min + pitch_norm * span if span > 1e-9 else 0.0
            if left <= 0.02 and right <= 0.02 and not hit:
                freq = 0.0
            return MixedSample(
                left=left,
                right=right,
                pitch_norm=pitch_norm,
                freq_hz=freq,
                amp=max(left, right),
                transient=hit,
                source=name,
                gain=gain,
                frame=frame,
            )
        return MixedSample(0.0, 0.0, 0.0, 0.0, 0.0, False, None, 0.0, None)
