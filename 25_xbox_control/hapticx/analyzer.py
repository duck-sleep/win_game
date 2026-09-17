"""analyzer.py — FFT 频段分析 + 雷云 A2H 映射引擎。

参数全部对标雷云 RzAudioCapture.log 中挖出的 A2H 配方(见 razer_probe.py):
  频段 30-130Hz / EQ(0:1, 50:1, 100:0.3, 150:0.3) / 振幅窗 40ms /
  频率窗 125ms / 门限 0.03 / 压缩器 gamma 3 / 瞬态 prominence 0.4、时长 22ms。
pitch_norm 用 A2H output_frequency_range 30–80Hz 归一化(W0.3),不是 50ms FFT。
"""
import numpy as np

from audio_capture import SAMPLE_RATE

FFT_WINDOW = 2400  # 50ms,雷云 period_ms_fft=50
FFT_HOP = 960      # 20ms

# 估频另开约 125ms 窗。现有 2400 点只有 20Hz/格,分不开小星星 65/98/110Hz。
# 6000 点 @48kHz → 8Hz/格。不要拿 50ms 振幅 FFT 冒充 pitch。
FREQ_EST_WINDOW = 6000
# W0.3 日志 profile.underlying_bands[0].output_frequency_range,不是 deviceReport 30–400。
PITCH_FREQ_MIN = 30.0
PITCH_FREQ_MAX = 80.0
# 峰邻域能量 / 30–130Hz 总能量;低于此则 freq/pitch 归零,不沿用上次值。
PITCH_CONF_MIN = 0.55
PITCH_SMOOTH_ALPHA = 0.55  # 约 2–3 块跟上新纯音,总延迟仍压在 ~150ms 窗填充内
PITCH_PEAK_NEIGHBORS = 1   # ±1 格;白噪声在 30–130 约 13 格,±2 会误过高置信
ENERGY_SILENCE = 1e-12

# 雷云四种模式的参数预设(均衡=雷云真值)
# 注意:压缩器归一化使用固定参考值 REF_LEVEL=0.3,
# 不依赖 gate,确保所有模式在相同输入能量下输出相近强度。
# 模式差异只体现在:门限(静音阈值)、gamma(压缩曲线)、瞬态(节拍脉冲)。
MODES = {
    "controlled": {  # 受控:门限更高、衰减更强、瞬态轻但可感,适合安静环境
        "gate": 0.04, "band_scale": 1.0, "transient_vol": 0.25,
        "gamma": 3.5, "freq_win": 0.15, "amp_win": 0.04,
    },
    "balanced": {  # 均衡:雷云默认配方,节拍弹跳适中
        "gate": 0.03, "band_scale": 1.0, "transient_vol": 0.35,
        "gamma": 3.0, "freq_win": 0.125, "amp_win": 0.04,
    },
    "dynamic": {  # 动态:对比度增强+瞬态(节拍打拍子),最猛
        "gate": 0.02, "band_scale": 1.0, "transient_vol": 0.6,
        "gamma": 4.0, "freq_win": 0.06, "amp_win": 0.025,
    },
    "custom": {  # 自订:同均衡,参数可被 UI 覆盖
        "gate": 0.03, "band_scale": 1.0, "transient_vol": 0.5,
        "gamma": 3.0, "freq_win": 0.125, "amp_win": 0.04,
    },
}

EQ_KEYFRAMES = [(0, 1.0), (50, 1.0), (100, 0.3), (150, 0.3)]  # 雷云 haptic_EQ

BAND_MIN, BAND_MAX = 30.0, 130.0  # 雷云输入频段

# 用户可调的频段增益(对标雷云逐频段调节)
# 频率分界点,将 30-130Hz 分成 3 段,每段一个增益滑条
BAND_EDGES = [30.0, 70.0, 100.0, 200.0]
BAND_LABELS = ["超低音", "低音", "中低音"]
BAND_DEFAULT = [1.0, 0.7, 0.3]

# 每个模式各自的频段增益预设(对标雷云:每个配置文件有独立频段曲线)
# 受控整体收敛;均衡=雷云默认;动态侧重超低音出拳感;自订从均衡起步
MODE_BAND_GAINS = {
    "controlled": [0.7, 0.5, 0.2],
    "balanced": [1.0, 0.7, 0.3],
    "dynamic": [1.3, 0.6, 0.2],
    "custom": [1.0, 0.7, 0.3],
}


def band_gains_for(config, mode):
    """取某模式的频段增益:用户在配置里调过就用调过的值,否则用模式预设。"""
    gains = (config.get("mode_band_gains") or {}).get(mode)
    if gains:
        return [max(0.0, min(2.0, float(g))) for g in gains]
    return list(MODE_BAND_GAINS.get(mode, BAND_DEFAULT))


def band_edges_for(config, mode):
    """取某模式的频段边界(Hz):用户调过就用调过的值,否则用默认 30/70/100/200。

    外边界 30/200Hz 是触觉处理范围(BAND_MIN/BAND_MAX),固定;内边界可调。"""
    edges = (config.get("mode_band_edges") or {}).get(mode)
    if edges and len(edges) == len(BAND_EDGES):
        return [max(30.0, min(200.0, float(e))) for e in edges]
    return list(BAND_EDGES)


class A2HAnalyzer:
    def __init__(self, mode="balanced", gain=0.67, overrides=None, band_gains=None,
                 band_edges=None):
        cfg = dict(MODES.get(mode, MODES["balanced"]))
        if overrides:
            cfg.update(overrides)
        self.cfg = cfg
        self.gain = gain  # 雷云 SetHapticMixerGain gain=67 → 0.67
        self.mode = mode
        self.buffer = np.zeros(FFT_WINDOW, dtype=np.float64)
        self.window = np.hanning(FFT_WINDOW)
        self.prev_spectrum = None
        self.freqs = np.fft.rfftfreq(FFT_WINDOW, 1.0 / SAMPLE_RATE)
        self.band_mask = (self.freqs >= BAND_MIN) & (self.freqs <= BAND_MAX)
        self.eq_table = np.interp(self.freqs, *zip(*EQ_KEYFRAMES))
        self.band_gains = list(band_gains) if band_gains else list(BAND_DEFAULT)
        self.band_edges = [float(e) for e in
                           (band_edges if band_edges else BAND_EDGES)]
        self._rebuild_eq()

        self.freq_buffer = np.zeros(FREQ_EST_WINDOW, dtype=np.float64)
        self.freq_window = np.hanning(FREQ_EST_WINDOW)
        self.freq_bins = np.fft.rfftfreq(FREQ_EST_WINDOW, 1.0 / SAMPLE_RATE)
        self.freq_band_mask = (self.freq_bins >= BAND_MIN) & (self.freq_bins <= BAND_MAX)
        self.last_freq_hz = 0.0
        self.last_amp = 0.0
        self.last_centroid_hz = 0.0
        self.last_pitch_norm = 0.0
        self.last_pitch_confidence = 0.0
        self.last_band_energies = [0.0, 0.0, 0.0]
        self._smooth_freq_hz = 0.0

        # 可视化:16个对数频段(20Hz-8kHz),触觉频段高亮
        viz_edges = np.geomspace(20.0, 8000.0, 17)
        self.viz_masks = [((self.freqs >= lo) & (self.freqs < hi))
                          for lo, hi in zip(viz_edges[:-1], viz_edges[1:])]
        self.viz_in_band = [(lo >= BAND_MIN and lo <= BAND_MAX) for lo in viz_edges[:-1]]
        self.viz = np.zeros(len(self.viz_masks))

        # 振幅包络(attack=窗长,release 稍慢让振动自然衰减)
        self.env = 0.0
        # 频率窗平滑
        self.freq_env = 0.0
        # 瞬态脉冲状态
        self.transient_amp = 0.0
        self.transient_decay = 0.0
        self._transient_fresh = False
        self.block_period = FFT_HOP / SAMPLE_RATE
        self.beat_count = 0
        self._elapsed = 0.0
        self._last_beat_t = -1.0
        self.refractory = 0.12  # 不应期:两次节拍脉冲最小间隔

    def _eq_weighted_band(self):
        spectrum = np.abs(np.fft.rfft(self.buffer * self.window)) / FFT_WINDOW
        self.viz = np.array([
            float(np.sqrt(np.mean(spectrum[mask] ** 2))) / 0.25 if mask.any() else 0.0
            for mask in self.viz_masks
        ])
        self.viz = np.clip(self.viz, 0.0, 1.0)
        flux = 0.0
        if self.prev_spectrum is not None:
            diff = spectrum - self.prev_spectrum
            # 只统计鼓点所在频段(30-130Hz)的上升通量,镲片/人声不触发节拍
            flux = float(np.sum(diff[self.band_mask & (diff > 0)]))
        self.prev_spectrum = spectrum
        band = spectrum * self.eq_table
        amp = float(np.sqrt(np.mean(band[self.band_mask] ** 2)))
        return amp, flux

    def _envelope(self, amp):
        tau = self.cfg["amp_win"]
        alpha = 1.0 - np.exp(-self.block_period / max(tau, 1e-6))
        release = alpha * 0.4  # 释放更慢,振动自然衰减
        self.env += (amp - self.env) * (alpha if amp > self.env else release)
        return self.env

    def _frequency_smooth(self, amp):
        tau = self.cfg["freq_win"]
        alpha = 1.0 - np.exp(-self.block_period / max(tau, 1e-6))
        self.freq_env += (amp - self.freq_env) * alpha
        return self.freq_env

    def reconfigure(self, mode=None, gain=None, overrides=None, band_gains=None,
                    band_edges=None):
        """UI线程在线切换模式/增益/频段增益/频段边界,无需重启管线。"""
        if mode is not None and mode in MODES:
            cfg = dict(MODES[mode])
            if mode == "custom" and overrides:
                cfg.update(overrides)
            self.cfg = cfg
            self.mode = mode
        if overrides and self.mode == "custom":
            self.cfg.update(overrides)
        if gain is not None:
            self.gain = max(0.05, min(1.5, float(gain)))
        if band_gains is not None:
            self.band_gains = [max(0.0, min(2.0, float(g))) for g in band_gains]
            self._rebuild_eq()
        if band_edges is not None:
            self.band_edges = [max(30.0, min(200.0, float(e))) for e in band_edges]
            self._rebuild_eq()

    def _rebuild_eq(self):
        """根据 EQ_KEYFRAMES + band_gains + band_edges 重建 eq_table。"""
        base = np.interp(self.freqs, *zip(*EQ_KEYFRAMES))
        for i, (lo, hi) in enumerate(zip(self.band_edges[:-1], self.band_edges[1:])):
            mask = (self.freqs >= lo) & (self.freqs < hi)
            base[mask] *= self.band_gains[i]
        self.eq_table = base

    def _parabolic_peak_hz(self, mag, peak_i, bins):
        """峰值左右相邻格抛物线插值,返回 Hz。mag/bins 已是 30–130Hz 切片。"""
        if peak_i <= 0 or peak_i >= mag.size - 1:
            return float(bins[peak_i])
        a, b, c = float(mag[peak_i - 1]), float(mag[peak_i]), float(mag[peak_i + 1])
        denom = a - 2.0 * b + c
        delta = 0.5 * (a - c) / denom if abs(denom) > 1e-12 else 0.0
        bin_hz = SAMPLE_RATE / FREQ_EST_WINDOW
        return float(bins[peak_i] + delta * bin_hz)

    def _update_pitch_estimate(self):
        """独立 125ms 估频。last_amp 在 process_block 里用压缩后标量写入。"""
        spectrum = np.abs(np.fft.rfft(self.freq_buffer * self.freq_window))
        mag = spectrum[self.freq_band_mask]
        bins = self.freq_bins[self.freq_band_mask]
        power = mag * mag
        total = float(np.sum(power))
        edges = self.band_edges
        energies = []
        for lo, hi in zip(edges[:-1], edges[1:]):
            m = (self.freq_bins >= lo) & (self.freq_bins < hi)
            chunk = spectrum[m]
            energies.append(float(np.sqrt(np.mean(chunk ** 2))) if chunk.size else 0.0)
        self.last_band_energies = energies[:3] + [0.0] * max(0, 3 - len(energies))
        self.last_band_energies = self.last_band_energies[:3]

        if total < ENERGY_SILENCE or mag.size == 0:
            self._smooth_freq_hz = 0.0
            self.last_freq_hz = 0.0
            self.last_centroid_hz = 0.0
            self.last_pitch_norm = 0.0
            self.last_pitch_confidence = 0.0
            return

        peak_i = int(np.argmax(mag))
        lo = max(0, peak_i - PITCH_PEAK_NEIGHBORS)
        hi = min(mag.size, peak_i + PITCH_PEAK_NEIGHBORS + 1)
        conf = float(np.sum(power[lo:hi]) / (total + 1e-18))
        centroid = float(np.sum(bins * power) / (total + 1e-18))
        self.last_centroid_hz = centroid
        self.last_pitch_confidence = conf

        if conf < PITCH_CONF_MIN:
            self._smooth_freq_hz = 0.0
            self.last_freq_hz = 0.0
            self.last_pitch_norm = 0.0
            return

        raw_hz = self._parabolic_peak_hz(mag, peak_i, bins)
        if self._smooth_freq_hz <= 0.0:
            self._smooth_freq_hz = raw_hz
        else:
            self._smooth_freq_hz += (raw_hz - self._smooth_freq_hz) * PITCH_SMOOTH_ALPHA
        self.last_freq_hz = float(self._smooth_freq_hz)
        span = PITCH_FREQ_MAX - PITCH_FREQ_MIN
        pitch = (self.last_freq_hz - PITCH_FREQ_MIN) / span if span > 1e-9 else 0.0
        self.last_pitch_norm = float(np.clip(pitch, 0.0, 1.0))

    def set_band_gains(self, band_gains):
        """UI 调频段增益时调用。"""
        self.reconfigure(band_gains=band_gains)

    def set_band_edges(self, band_edges):
        """UI 拖频段边界时调用。"""
        self.reconfigure(band_edges=band_edges)

    def _detect_transient(self, flux):
        self._elapsed += self.block_period
        if self.cfg["transient_vol"] <= 0:
            return False
        if self.freq_env <= 1e-6:
            return False
        if self._elapsed - self._last_beat_t < self.refractory:
            return False
        prominence = self.cfg.get("prominence", 0.4)
        if flux / (self.freq_env + 1e-9) > prominence * 8:  # 通量显著超过基线
            self.transient_amp = self.cfg["transient_vol"]
            dur = self.cfg.get("transient_dur", 0.022)  # 雷云 22ms
            self.transient_decay = np.exp(-self.block_period / max(dur, 1e-6))
            self._transient_fresh = True  # 触发块满幅输出,下一块起再衰减
            self.beat_count += 1
            self._last_beat_t = self._elapsed
            return True
        return False

    def process_block(self, samples):
        """输入 20ms 块,返回 (left, right, band, transient)。"""
        samples = np.asarray(samples, dtype=np.float64).reshape(-1)
        n = samples.size
        self.buffer = np.concatenate([self.buffer[n:], samples])
        if n >= FREQ_EST_WINDOW:
            self.freq_buffer = samples[-FREQ_EST_WINDOW:].copy()
        else:
            self.freq_buffer = np.concatenate([self.freq_buffer[n:], samples])
        amp, flux = self._eq_weighted_band()
        env = self._envelope(amp)
        smoothed = self._frequency_smooth(env)

        gate = self.cfg["gate"]
        gated = smoothed if smoothed > gate else 0.0

        # 压缩器:gamma 感知映射,固定参考值归一化,不依赖 gate
        # 这样所有模式在相同输入能量下输出强度一致,模式差异只来自门限/gamma/瞬态
        gamma = self.cfg["gamma"]
        compressed = np.clip((gated / 0.3) ** (1.0 / gamma), 0.0, 1.0) \
            if gated > 0 else 0.0

        self._detect_transient(flux)
        if self._transient_fresh:
            self._transient_fresh = False
        elif self.transient_amp > 0:
            self.transient_amp *= self.transient_decay
            if self.transient_amp < 0.02:
                self.transient_amp = 0.0

        band_level = compressed * self.cfg["band_scale"]
        left = np.clip(band_level + self.transient_amp * 0.7, 0.0, 1.0) * self.gain
        right = np.clip(self.transient_amp + band_level * 0.4, 0.0, 1.0) * self.gain
        self._update_pitch_estimate()
        # last_amp = 压缩后标量 × mixer gain,与左右马达拆分前的力度同量纲
        self.last_amp = float(compressed * self.gain)
        return float(left), float(right), float(smoothed), self.transient_amp > 0
