"""雷云那条线的编码器输出 → NS 的两个振荡器。

⚠️ 这是**设计**，不是抄来的协议：雷云手柄收两条曲线 + 瞬态由固件合成，
NS 是主机直接给两个振荡器的频率和振幅。映射靠用户手感调，只有下面三个常量可动：
TRANSIENT_HZ、TRANSIENT_PACKETS、以及调用方传的增益。不许改编码器、不许改 codec 的协议编码。

映射（每只手）：
  曲线0（30–100 Hz 带）(a0, h0) → 低频振荡器 lf_hz=h0, lf_amp=a0
  曲线1（100–200 Hz 带）(a1, h1) → 高频振荡器 hf_hz=h1, hf_amp=a1
  新瞬态              → 高频振荡器临时改成 TRANSIENT_HZ、振幅 max(a1, 瞬态力度)，持续 TRANSIENT_PACKETS 个包

Hz 越界由 codec.encode_side 自己夹，映射层不再夹。
"""

from __future__ import annotations

from .codec import encode_side

TRANSIENT_HZ = 160.0        # 设计值：Pro 手柄静止包里低频默认 160 Hz
TRANSIENT_PACKETS = 2       # 瞬态持续几个包
MIN_GAP_S = 0.022           # 同一下敲击的最小间隔（编码器也是这个口径）


class A2HToNS:
    """有状态：每只手各自记「上次瞬态的绝对样本号」和「剩余瞬态包数」。"""

    def __init__(self, sample_rate: float, enable_transients: bool = True) -> None:
        self.sr = float(sample_rate)
        self.enable_transients = bool(enable_transients)
        # None = 这只手还没触发过。不能用 0/-1 当哨兵：第一次的绝对样本号可能只差几十
        # （例：0.004 s = 192），会被间隔门限误杀（本机实测少 1 次触发，31 ≠ 32）。
        self.last_abs = [None, None]
        self.pending = [0, 0]
        self.pending_amp = [0.0, 0.0]
        self.hits = [[], []]      # 每只手触发过的绝对样本号，给测试和排障用
        # 每只手"想要"的 (hf_hz, hf_amp, lf_hz, lf_amp)（含瞬态覆盖后的值）。
        # 存在的理由：想量量化误差，就得拿"本意"和"4 字节反解回来的实际"对比，
        # 拿编码器原始曲线比会把瞬态覆盖也算成误差（2026-11-04 就错过一次）。
        self.want = [(0.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 0.0)]

    def _take_transient(self, hand: int, transients, total_samples: int, hist_len: int) -> None:
        """编码器每块都重扫最近 125 ms，同一下敲击会连着出现好几块 ⇒ 用绝对样本号去重。

        tr.time 是窗口内的秒数；hist_len 传 len(enc._raw_l)（编码器私有属性，只读）。
        """
        gap = int(MIN_GAP_S * self.sr)
        for tr in transients:
            abs_i = total_samples - hist_len + int(round(tr.time * self.sr))
            if self.last_abs[hand] is None or abs_i - self.last_abs[hand] > gap:
                self.last_abs[hand] = abs_i
                self.pending[hand] = TRANSIENT_PACKETS
                self.pending_amp[hand] = float(tr.amp)
                self.hits[hand].append(abs_i)

    def frame_to_bytes(self, frame, total_samples: int, hist_len: int) -> tuple[bytes, bytes]:
        """一帧 → 左右各 4 字节。"""
        sides = []
        parts = list(getattr(frame, "parts", []))[:2]
        for hand in range(2):
            if hand >= len(parts):
                sides.append(encode_side(0.0, 0.0, 0.0, 0.0))
                continue
            part = parts[hand]
            curves = list(part.curves) + [(0.0, 0.0), (0.0, 0.0)]
            (a0, h0), (a1, h1) = curves[0], curves[1]
            if self.enable_transients:
                self._take_transient(hand, part.transients, total_samples, hist_len)

            hf_hz, hf_amp = h1, a1
            if self.enable_transients and self.pending[hand] > 0:
                self.pending[hand] -= 1
                hf_hz = TRANSIENT_HZ
                hf_amp = max(a1, self.pending_amp[hand])
            self.want[hand] = (hf_hz, hf_amp, h0, a0)
            sides.append(encode_side(hf_hz, hf_amp, h0, a0))
        return sides[0], sides[1]
