"""a2h_encoder.py — 按 C 盘编码器抄的 Audio2Haptics，不 LoadLibrary 供应商 DLL。

FUN_180029aa0：Iir::Butterworth 阶数写死 2（edx=2），不是模板容量 7。
下沿为 0 走低通，否则 center=(lo+hi)/2、width=hi-lo，再除以采样率。
系数是 BandPassTransform（cos / tan 预畸变），两节 DirectFormII，全程 double。
FUN_1800208b0：频率窗补到 2 的幂做 FFT，返回峰值 bin 的 Hz，不看 band 边界。
"""
from __future__ import annotations

import cmath
import json
import math
from collections import deque

import numpy as np

from .har_pack import Transient, frame_from_block, freq_skirt

# 雷云 lighting-engine 日志里的 SENSA_HD / dynamic（2026-09-23）
# 两条 band。每条 band 一条曲线；带外 50 Hz 衰减在 _band_level。
SYNAPSE_PROFILE = {
    "volume": 1,
    "transients": {
        "volume": 1,
        "prominence": 1.4,
        "duration": 0.022,
    },
    "underlying_bands": {
        "volume": 6,
        "bands": [
            {
                "volume": 0.3,
                "amplitude_window_length": 0.03,
                "frequency_window_length": 0.125,
                "minimal_amplitude_threshold": 0.005,
                "frequency_range": {"min": 30, "max": 100},
                "output_frequency_range": {"min": 30, "max": 100},
            },
            {
                "volume": 0.1,
                "amplitude_window_length": 0.03,
                "frequency_window_length": 0.125,
                "minimal_amplitude_threshold": 0.005,
                "frequency_range": {"min": 100, "max": 200},
                "output_frequency_range": {"min": 100, "max": 200},
            },
        ],
    },
    "haptic_EQ": {
        "is_before_compressor": True,
        "keyframes": [
            {"frequency": 0, "volume": 0.5},
            {"frequency": 50, "volume": 0.5},
            {"frequency": 100, "volume": 1},
            {"frequency": 150, "volume": 1},
            {"frequency": 200, "volume": 0.5},
        ],
    },
    "compressor": {
        "amp_limit": 1,
        "amp_comp": 0.25,
        "amp_comp_ratio": 0.3,
        "gamma": 5,
    },
}

REF_LEVEL = 0.3
PITCH_CONF_MIN = 0.35
PERIOD_MS = 20


def _as_profile(profile) -> dict:
    if profile is None:
        return json.loads(json.dumps(SYNAPSE_PROFILE))
    if isinstance(profile, str):
        return json.loads(profile)
    return json.loads(json.dumps(profile))


def _pz_biquad(pole: complex, zero: complex):
    """共轭对 → 一节。a0 折进系数，和 DirectFormII 的 m_a1/m_b0 一致。"""
    a1 = -2.0 * pole.real
    a2 = pole.real * pole.real + pole.imag * pole.imag
    b1 = -2.0 * zero.real
    b2 = zero.real * zero.real + zero.imag * zero.imag
    return (1.0, b1, b2, a1, a2)


def _cascade_response(stages, norm_hz: float) -> complex:
    w = 2.0 * math.pi * norm_hz
    z1 = cmath.rect(1.0, -w)
    z2 = cmath.rect(1.0, -2.0 * w)
    h = 1.0 + 0.0j
    for b0, b1, b2, a1, a2 in stages:
        h *= (b0 + b1 * z1 + b2 * z2) / (1.0 + a1 * z1 + a2 * z2)
    return h


def _scale_first(stages, scale: float):
    b0, b1, b2, a1, a2 = stages[0]
    stages[0] = (b0 * scale, b1 * scale, b2 * scale, a1, a2)
    return stages


def _bandpass_transform(c: complex, a2: float, b2: float, ab_2: float, b: float):
    """Iir::BandPassTransform::transform。无穷点在调用处单独处理。"""
    c = (1.0 + c) / (1.0 - c)
    v = 4.0 * (b2 * (a2 - 1.0) + 1.0) * c
    v += 8.0 * (b2 * (a2 - 1.0) - 1.0)
    v *= c
    v += 4.0 * (b2 * (a2 - 1.0) + 1.0)
    v = cmath.sqrt(v)
    u = -v + ab_2 * c + ab_2
    v = v + ab_2 * c + ab_2
    d = 2.0 * (b - 1.0) * c + 2.0 * (1.0 + b)
    return (u / d, v / d)


def _iir_band_stages(lo_hz: float, hi_hz: float, fs: float):
    """FUN_180029aa0：阶数 2。lo==0 为低通一节，否则带通两节。"""
    nyq = 0.5 * fs
    lo = float(lo_hz)
    hi = float(hi_hz)
    if lo > hi:
        lo, hi = hi, lo
    lo = min(lo, nyq)
    hi = min(hi, nyq)
    if lo == 0.0:
        fc = hi / fs
        f = math.tan(math.pi * fc)
        pole = cmath.rect(1.0, math.pi / 2.0 + math.pi / 4.0)
        pole = f * pole
        pole = (1.0 + pole) / (1.0 - pole)
        stages = [_pz_biquad(pole, complex(-1.0, 0.0))]
        gain = abs(_cascade_response(stages, 0.0))
        return _scale_first(stages, 1.0 / gain if gain else 1.0)
    fc = ((lo + hi) * 0.5) / fs
    fw = (hi - lo) / fs
    ww = 2.0 * math.pi * fw
    wc2 = 2.0 * math.pi * fc - ww / 2.0
    wc = wc2 + ww
    if wc2 < 1e-8:
        wc2 = 1e-8
    if wc > 2.0 * math.pi - 1e-8:
        wc = 2.0 * math.pi - 1e-8
    a = math.cos((wc + wc2) * 0.5) / math.cos((wc - wc2) * 0.5)
    b = 1.0 / math.tan((wc - wc2) * 0.5)
    a2 = a * a
    b2 = b * b
    ab_2 = 2.0 * a * b
    pole = cmath.rect(1.0, math.pi / 2.0 + math.pi / 4.0)
    poles = _bandpass_transform(pole, a2, b2, ab_2, b)
    zeros = (complex(-1.0, 0.0), complex(1.0, 0.0))
    stages = [_pz_biquad(p, z) for p, z in zip(poles, zeros)]
    wn = 2.0 * math.atan(math.sqrt(math.tan(wc * 0.5) * math.tan(wc2 * 0.5)))
    gain = abs(_cascade_response(stages, wn / (2.0 * math.pi)))
    return _scale_first(stages, 1.0 / gain if gain else 1.0)


def _rbj_peaking(f0: float, gain_db: float, q: float, fs: float):
    """Iir::RBJ 峰值（库里有 BandPass / HighShelf / LowShelf，EQ 关键帧按这个抄）。"""
    a = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * math.pi * float(f0) / fs
    alpha = math.sin(w0) / (2.0 * max(q, 0.1))
    cosw = math.cos(w0)
    b0 = 1.0 + alpha * a
    b1 = -2.0 * cosw
    b2 = 1.0 - alpha * a
    a0 = 1.0 + alpha / a
    a1 = -2.0 * cosw
    a2 = 1.0 - alpha / a
    return (b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)


class _DirectFormII:
    """抄 Iir::DirectFormII：v 状态，y = b0*w + b1*v1 + b2*v2。"""

    def __init__(self, coef):
        self.b0, self.b1, self.b2, self.a1, self.a2 = coef
        self.v1 = 0.0
        self.v2 = 0.0

    def reset(self):
        self.v1 = 0.0
        self.v2 = 0.0

    def process(self, x: np.ndarray) -> np.ndarray:
        xx = np.asarray(x, dtype=np.float64).tolist()
        n = len(xx)
        yy = [0.0] * n
        v1, v2 = self.v1, self.v2
        b0, b1, b2, a1, a2 = self.b0, self.b1, self.b2, self.a1, self.a2
        for i, xn in enumerate(xx):
            w = xn - a1 * v1 - a2 * v2
            yy[i] = b0 * w + b1 * v1 + b2 * v2
            v2 = v1
            v1 = w
        self.v1, self.v2 = v1, v2
        return np.asarray(yy, dtype=np.float64)


class _CascadeDF2:
    """两节（低通时一节）DirectFormII 级联。"""

    def __init__(self, stages):
        self.stages = [_DirectFormII(c) for c in stages]

    def reset(self):
        for stage in self.stages:
            stage.reset()

    def process(self, x: np.ndarray) -> np.ndarray:
        y = x
        for stage in self.stages:
            y = stage.process(y)
        return y


class A2HEncoder:
    """按 C 盘编码器步骤抄。process_block 接口对齐管线。"""

    def __init__(self, gain=0.67, profile=None, sample_rate=48000.0):
        self.gain = float(gain)
        self.sample_rate = float(sample_rate)
        self.last_freq_hz = 0.0
        self.last_centroid_hz = 0.0
        self.last_pitch_norm = 0.0
        self.last_pitch_confidence = 0.0
        self.last_amp = 0.0
        self.last_band_energies = [0.0, 0.0, 0.0]
        self.viz = np.zeros(16)
        self.beat_count = 0
        self._smooth_freq_hz = 0.0
        self._elapsed = 0.0
        self._last_beat_t = -1.0
        self.transient_amp = 0.0
        self.transient_decay = 0.0
        self._transient_fresh = False
        self.env_l = 0.0
        self.env_r = 0.0
        self.freq_env = 0.0
        self.prev_env = 0.0
        self._bp_l = None
        self._bp_r = None
        self._eq_l = []
        self._eq_r = []
        self._sub_bp = []
        self.last_frame = None
        self.last_payload = b""
        self.set_haptics_profile(profile or SYNAPSE_PROFILE)

    def version(self) -> str:
        return "a2h-iir"

    def set_haptics_profile(self, profile) -> int:
        self.profile = _as_profile(profile)
        bands = self.profile.get("underlying_bands", {}).get("bands") or [{}]
        self.band = dict(bands[0])
        fr = self.band.get("frequency_range") or {}
        out = self.band.get("output_frequency_range") or {}
        self.band_min = float(fr.get("min", 30))
        self.band_max = float(fr.get("max", 130))
        self.pitch_min = float(out.get("min", 30))
        self.pitch_max = float(out.get("max", 80))
        self.amp_win = float(self.band.get(
            "amplitude_window_length", self.band.get("window_length", 0.04)))
        self.freq_win = float(self.band.get("frequency_window_length", 0.125))
        self.gate = float(self.band.get("minimal_amplitude_threshold", 0.03))
        self.band_volume = float(self.band.get("volume", 1.0))
        self.profile_volume = float(self.profile.get("volume", 1.0))
        bands_root = self.profile.get("underlying_bands") or {}
        self.bands_volume = float(bands_root.get("volume", 1.0))
        eq = self.profile.get("haptic_EQ") or {}
        kfs = eq.get("keyframes") or [{"frequency": 0, "volume": 1}]
        self.eq_hz = [float(k.get("frequency", 0)) for k in kfs]
        self.eq_vol = [float(k.get("volume", 1)) for k in kfs]
        self.eq_before = bool(eq.get("is_before_compressor", True))
        comp = self.profile.get("compressor") or {}
        self.gamma = float(comp.get("gamma", 3))
        self.amp_comp = float(comp.get("amp_comp", 0.5))
        self.amp_comp_ratio = float(comp.get("amp_comp_ratio", 0.5))
        self.amp_limit = float(comp.get("amp_limit", 1))
        self._band_defs = []
        for band in (bands_root.get("bands") or [self.band]):
            fr = band.get("frequency_range") or {}
            self._band_defs.append({
                "lo": float(fr.get("min", self.band_min)),
                "hi": float(fr.get("max", self.band_max)),
                "volume": float(band.get("volume", 1.0)),
                "gate": float(band.get("minimal_amplitude_threshold", self.gate)),
                "freq_win": float(band.get("frequency_window_length", self.freq_win)),
            })
        tr = self.profile.get("transients") or {}
        self.tr_vol = float(tr.get("volume", 0))
        self.tr_prom = float(tr.get("prominence", 0.4))
        self.tr_dur = float(tr.get("duration", 0.022))
        self._rebuild_tables()
        return 0

    def _rebuild_tables(self):
        sr = max(8000.0, float(self.sample_rate))
        self.block_period = PERIOD_MS / 1000.0
        stages = _iir_band_stages(self.band_min, self.band_max, sr)
        self._bp_l = _CascadeDF2(stages)
        self._bp_r = _CascadeDF2(stages)
        third = (self.band_max - self.band_min) / 3.0
        self._sub_bp = []
        for i in range(3):
            lo = self.band_min + i * third
            hi = lo + third
            self._sub_bp.append(_CascadeDF2(_iir_band_stages(lo, hi, sr)))
        freq_n = max(256, int(round(sr * self.freq_win)))
        self.freq_n = freq_n
        self.freq_buffer = np.zeros(freq_n, dtype=np.float64)
        keep = max(1, int(sr * self.amp_win))
        self._band_l = []
        self._band_r = []
        self._band_hist_l = []
        self._band_hist_r = []
        self._pitch_l = []
        self._pitch_r = []
        self._tr_slots: list[Transient] = []
        hist_n = max(self.freq_win, self.amp_win, self.tr_dur)
        for spec in self._band_defs:
            hist_n = max(hist_n, spec["freq_win"])
        self._raw_n = max(16, int(round(sr * hist_n)))
        self._raw_l: deque = deque(maxlen=self._raw_n)
        self._raw_r: deque = deque(maxlen=self._raw_n)
        self._amp_n = max(1, int(round(sr * self.amp_win)))
        for spec in self._band_defs:
            stages = _iir_band_stages(spec["lo"], spec["hi"], sr)
            self._band_l.append(_CascadeDF2(stages))
            self._band_r.append(_CascadeDF2(stages))
            self._band_hist_l.append(deque(maxlen=keep))
            self._band_hist_r.append(deque(maxlen=keep))
            pitch_n = max(16, int(round(sr * spec["freq_win"])))
            self._pitch_l.append(deque(maxlen=pitch_n))
            self._pitch_r.append(deque(maxlen=pitch_n))
        self.env_l = self.env_r = self.freq_env = self.prev_env = 0.0
        self.viz = np.zeros(16)

    def _eq_gain(self, hz: float) -> float:
        """FUN_1800205f0：关键帧之间线性插值，乘在归一化力度上。"""
        if not self.eq_hz:
            return 1.0
        return float(np.interp(float(hz), self.eq_hz, self.eq_vol, left=self.eq_vol[0], right=self.eq_vol[-1]))

    def _zcr_pitch(self, x: np.ndarray) -> tuple[float, float]:
        """带通之后的过零估频（时域，不用 FFT）。"""
        if x.size < 16:
            return 0.0, 0.0
        s = np.signbit(x)
        idx = np.flatnonzero(s[1:] != s[:-1])
        if idx.size < 4:
            return 0.0, 0.0
        gaps = np.diff(idx.astype(np.float64))
        med = float(np.median(gaps))
        if med < 2.0:
            return 0.0, 0.0
        hz = float(self.sample_rate / (2.0 * med))
        if hz < self.band_min * 0.5 or hz > self.band_max * 1.5:
            return 0.0, 0.0
        conf = float(np.clip(1.0 - np.std(gaps) / (med + 1e-9), 0.0, 1.0))
        return hz, conf

    def _amdf_pitch(self, x: np.ndarray) -> tuple[float, float]:
        """frequency_window 上的 YIN/AMDF 周期（时域，不用 FFT）。"""
        if x.size < 64:
            return 0.0, 0.0
        fs = float(self.sample_rate)
        dec = max(1, int(round(fs / 4000.0)))
        y = x[::dec]
        fs2 = fs / dec
        if y.size < 32:
            return 0.0, 0.0
        min_lag = max(2, int(fs2 / max(self.band_max, 40.0)))
        max_lag = min(y.size // 2 - 1, int(fs2 / max(self.band_min, 20.0)))
        if max_lag <= min_lag + 2:
            return 0.0, 0.0
        d = np.empty(max_lag - min_lag + 1, dtype=np.float64)
        for i, tau in enumerate(range(min_lag, max_lag + 1)):
            d[i] = float(np.mean(np.abs(y[:-tau] - y[tau:])))
        # YIN cumulative mean: 取最短合格周期，避免 1/2、1/3 频
        acc = np.cumsum(d)
        yin = d * np.arange(1, d.size + 1) / (acc + 1e-18)
        thresh = 0.15
        hits = np.flatnonzero(yin < thresh)
        k = int(hits[0]) if hits.size else int(np.argmin(yin))
        if k <= 0 or k >= d.size - 1:
            tau = float(min_lag + k)
        else:
            a, b, c = float(yin[k - 1]), float(yin[k]), float(yin[k + 1])
            denom = a - 2.0 * b + c
            tau = float(min_lag + k) + (0.5 * (a - c) / denom if abs(denom) > 1e-12 else 0.0)
        if tau < 2.0:
            return 0.0, 0.0
        hz = float(fs2 / tau)
        if hz < self.band_min * 0.5 or hz > self.band_max * 1.5:
            return 0.0, 0.0
        conf = float(np.clip(1.0 - float(yin[k]), 0.0, 1.0))
        return hz, conf

    def _update_pitch(self):
        zcr_hz, zcr_c = self._zcr_pitch(self.freq_buffer)
        amdf_hz, amdf_c = self._amdf_pitch(self.freq_buffer)
        # 带通后近似正弦：过零优先；AMDF 只在过零不可靠时补
        if zcr_c >= PITCH_CONF_MIN:
            raw_hz, conf = zcr_hz, zcr_c
            if (amdf_c >= PITCH_CONF_MIN and abs(amdf_hz - zcr_hz) < 12.0):
                raw_hz = 0.5 * (amdf_hz + zcr_hz)
                conf = 0.5 * (amdf_c + zcr_c)
        else:
            raw_hz, conf = amdf_hz, amdf_c
        self.last_pitch_confidence = conf
        if conf < PITCH_CONF_MIN or raw_hz <= 0.0:
            self._smooth_freq_hz = 0.0
            self.last_freq_hz = 0.0
            self.last_centroid_hz = 0.0
            self.last_pitch_norm = 0.0
            return
        alpha = 1.0 - np.exp(-self.block_period / max(self.freq_win, 1e-6))
        if self._smooth_freq_hz <= 0.0:
            self._smooth_freq_hz = raw_hz
        else:
            self._smooth_freq_hz += (raw_hz - self._smooth_freq_hz) * float(alpha)
        hz = float(np.clip(self._smooth_freq_hz, self.pitch_min, self.pitch_max))
        self.last_freq_hz = hz
        self.last_centroid_hz = hz
        span = self.pitch_max - self.pitch_min
        self.last_pitch_norm = float(np.clip(
            (hz - self.pitch_min) / span if span > 1e-9 else 0.0, 0.0, 1.0))

    def _envelope(self, env: float, amp: float) -> float:
        alpha = 1.0 - np.exp(-self.block_period / max(self.amp_win, 1e-6))
        release = alpha * 0.4
        env += (amp - env) * (alpha if amp > env else release)
        return float(env)

    def _shape(self, peak: float, gate: float, eq_gain: float = 1.0) -> float:
        """门限归一化 → EQ（拐点前）→ 拐点 → ln(gamma·y+1)。"""
        if peak <= 0.0:
            return 0.0
        span = 1.0 - gate
        x = (peak - gate) / span if span > 1e-9 else peak
        x = min(max(x, 0.0), 1.0)
        if self.eq_before:
            x *= eq_gain
        limit = self.amp_limit
        comp = self.amp_comp
        ratio = self.amp_comp_ratio
        knee = comp + (limit - comp) * ratio
        if x <= comp:
            y = x
        elif x >= limit:
            y = knee
        else:
            y = comp + (x - comp) * ratio
        if knee > 1e-12:
            y *= limit / knee
        if self.gamma > 0.0:
            y = math.log(self.gamma * y + 1.0)
        if not self.eq_before:
            y *= eq_gain
        return float(max(y, 0.0))

    def _compress(self, gated: float) -> float:
        """门限归一化 → 拐点 → ln(gamma·y+1) → 音量。带外衰减由 _band_level 乘。"""
        y = self._shape(gated, self.gate)
        y *= self.band_volume * self.bands_volume * self.profile_volume
        return float(min(y, 1.0))

    def _band_level(self, peak: float, freq_hz: float, spec: dict) -> float:
        y = self._shape(peak, spec["gate"], self._eq_gain(freq_hz))
        y *= freq_skirt(freq_hz, spec["lo"], spec["hi"])
        y *= spec["volume"] * self.bands_volume * self.profile_volume
        return float(min(max(y, 0.0), 1.0))

    def _note_transient(self, amp: float, time_s: float) -> None:
        """设备最多两条。新的只有比已有的更响才替换。"""
        ev = Transient(time_s, amp, 0.5)
        if len(self._tr_slots) < 2:
            self._tr_slots.append(ev)
            return
        weakest = min(range(2), key=lambda i: self._tr_slots[i].amp)
        if amp > self._tr_slots[weakest].amp:
            self._tr_slots[weakest] = ev

    def _scan_transients(self, samples: np.ndarray) -> None:
        """FUN_18001f670：重扫原始波形。每个谷都更新参考值，静音滑出窗口后槽位是空的。"""
        self._tr_slots = []
        if self.tr_vol <= 0.0:
            return
        x = np.asarray(samples, dtype=np.float64)
        n = int(x.size)
        if n < 3:
            return
        sr = float(self.sample_rate)
        eps = 2.220446049250313e-14
        d = np.diff(x)
        left, right = d[:-1], d[1:]
        flat = (np.abs(left) <= eps) & (np.abs(right) <= eps)
        is_max = (left >= 0.0) & (right <= 0.0) & ~flat
        is_min = (left <= 0.0) & (right >= 0.0) & ~flat
        idx = np.flatnonzero(is_max | is_min)
        armed = False
        peak_i = 0
        peak_v = 0.0
        # 参考值从窗口第 0 个样本开始。每个谷都改成这个谷，见 0x18001FCCA。
        ref = float(x[0])
        last_i = int(round(-self.tr_dur * sr) - 1.0)
        for i in idx:
            i = int(i) + 1
            mid = float(x[i])
            if is_max[i - 1]:
                # 0x18001FAB5：已经有峰时不再换成后面的峰。
                if not armed:
                    peak_i = i
                    peak_v = mid
                    armed = True
                continue
            if armed:
                if (i - last_i) / sr >= self.tr_dur:
                    drop = max(abs(peak_v - mid), abs(peak_v - ref))
                    if drop >= self.tr_prom:
                        amp = abs(peak_v) * self.profile_volume * self.tr_vol
                        self._note_transient(amp, peak_i / sr)
                        last_i = peak_i
                armed = False
            ref = mid

    def _window_level(self, hist: deque) -> float:
        """FUN_1800206c0：幅度窗里 (最大值 − 最小值) × 0.5。稳态正弦等于峰值。"""
        if hist is None or len(hist) == 0:
            return 0.0
        arr = np.asarray(hist, dtype=np.float64)
        return float((arr.max() - arr.min()) * 0.5)

    def _fft_peak_hz(self, hist: deque) -> float:
        """FUN_1800208b0：最后一窗补到 2 的幂，取 0..N/2 里幅度最大的 bin。"""
        n = len(hist)
        if n < 16:
            return 0.0
        nfft = 1
        while nfft < n:
            nfft *= 2
        spec = np.fft.rfft(np.asarray(hist, dtype=np.float64), n=nfft)
        mag = np.abs(spec[: nfft // 2])
        k = int(np.argmax(mag))
        return float(k * self.sample_rate / nfft)

    def _detect_transient(self, flux: float) -> bool:
        self._elapsed += self.block_period
        if self.tr_vol <= 0 or self.freq_env <= 1e-6:
            return False
        if self._elapsed - self._last_beat_t < 0.12:
            return False
        if flux / (self.freq_env + 1e-9) > self.tr_prom * 8:
            self.transient_amp = self.tr_vol
            self.transient_decay = float(np.exp(
                -self.block_period / max(self.tr_dur, 1e-6)))
            self._transient_fresh = True
            self.beat_count += 1
            self._last_beat_t = self._elapsed
            return True
        return False

    def process_block(self, samples, sample_rate=None):
        if sample_rate is not None and abs(float(sample_rate) - self.sample_rate) > 0.5:
            self.sample_rate = float(sample_rate)
            self._rebuild_tables()
        arr = np.asarray(samples, dtype=np.float64)
        if arr.ndim == 1:
            stereo = np.stack([arr, arr], axis=1)
        else:
            if arr.shape[1] == 1:
                stereo = np.repeat(arr, 2, axis=1)
            else:
                stereo = np.ascontiguousarray(arr[:, :2])
        self._raw_l.extend(stereo[:, 0].tolist())
        self._raw_r.extend(stereo[:, 1].tolist())
        raw_l = np.asarray(self._raw_l, dtype=np.float64)
        raw_r = np.asarray(self._raw_r, dtype=np.float64)
        mix = 0.5 * (stereo[:, 0] + stereo[:, 1])
        energies = []
        for flt in self._sub_bp:
            band = flt.process(mix)
            energies.append(float(np.sqrt(np.mean(band ** 2))))
        self.last_band_energies = energies + [0.0] * max(0, 3 - len(energies))
        self.last_band_energies = self.last_band_energies[:3]
        # FUN_18001ef60 立体声：216 用第 0 路，116 用第 1 路，各自扫瞬态、各自估频。
        self._scan_transients(raw_l)
        trans_l = list(self._tr_slots)
        self._scan_transients(raw_r)
        trans_r = list(self._tr_slots)
        curves_l = []
        curves_r = []
        amp_n = self._amp_n
        for spec, flt_l, flt_r in zip(self._band_defs, self._band_l, self._band_r):
            flt_l.reset()
            flt_r.reset()
            bl = flt_l.process(raw_l) if raw_l.size else raw_l
            br = flt_r.process(raw_r) if raw_r.size else raw_r
            freq_n = max(16, int(round(self.sample_rate * spec["freq_win"])))
            peak_l = self._window_level(bl[-amp_n:])
            peak_r = self._window_level(br[-amp_n:])
            hz_l = self._fft_peak_hz(bl[-freq_n:])
            hz_r = self._fft_peak_hz(br[-freq_n:])
            curves_l.append((self._band_level(peak_l, hz_l, spec), hz_l))
            curves_r.append((self._band_level(peak_r, hz_r, spec), hz_r))
        if curves_l:
            self.freq_buffer = bl[-self.freq_n:] if bl.size >= self.freq_n else bl
        self._update_pitch()
        left = curves_l[0][0] if curves_l else 0.0
        right = curves_r[0][0] if curves_r else 0.0
        freq = curves_l[0][1] if curves_l else 0.0
        self.last_freq_hz = freq
        self.last_amp = max(left, right)
        self.last_frame = frame_from_block(
            left, right, self.last_pitch_norm,
            freq_hz=freq,
            curves_l=curves_l,
            curves_r=curves_r,
            transients_l=trans_l,
            transients_r=trans_r,
            pitch_min=self.pitch_min, pitch_max=self.pitch_max)
        beat = bool(trans_l or trans_r)
        self.last_payload = self.last_frame.packed
        self.viz[:] = 0.0
        self.viz[1:6] = self.last_amp
        if self.last_amp <= 0.02:
            self.last_freq_hz = 0.0
            self.last_pitch_norm = 0.0
            self.last_pitch_confidence = 0.0
        return left, right, float(self.last_amp), bool(beat)

    def get_haptic_payload(self) -> bytes:
        return self.last_payload or b""

    def get_haptic_payload_size(self) -> int:
        return len(self.last_payload or b"")

    def reconfigure(self, **kwargs):
        if kwargs.get("gain") is not None:
            self.gain = max(0.05, min(1.5, float(kwargs["gain"])))
        if kwargs.get("profile") is not None:
            self.set_haptics_profile(kwargs["profile"])

    def set_band_gains(self, band_gains):
        return None

    def set_band_edges(self, band_edges):
        return None

    def close(self):
        return None
