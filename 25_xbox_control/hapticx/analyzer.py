"""analyzer.py — FFT 频段分析 + 雷云 A2H 映射引擎。

参数全部对标雷云 RzAudioCapture.log 中挖出的 A2H 配方(见 razer_probe.py):
  频段 30-130Hz / EQ(0:1, 50:1, 100:0.3, 150:0.3) / 振幅窗 40ms /
  频率窗 125ms / 门限 0.03 / 压缩器 gamma 3 / 瞬态 prominence 0.4、时长 22ms。
"""
import numpy as np

from audio_capture import SAMPLE_RATE

FFT_WINDOW = 2400  # 50ms,雷云 period_ms_fft=50
FFT_HOP = 960      # 20ms

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
        self.buffer = np.concatenate([self.buffer[samples.size:], samples])
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
        return float(left), float(right), float(smoothed), self.transient_amp > 0
