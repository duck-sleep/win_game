"""pipeline.py（机械师 NS 版）— 采集 → 编码 → **NS HD 振动**出口。

和 25 那版的关系：界面、采集、编码器**全部照抄**，只把出口从
「雷蛇 Feature 4 / XInput」换成「任天堂 Pro Controller 的 0x10 振动报告」。
类名和 UI 调用的方法签名保持不变，所以 app.py 几乎不用动。

四层：
  采集  audio_capture.LoopbackCapture（WASAPI 环回，跟 mix 采样率，立体声，约 20 ms）
  编码  a2h_encoder.A2HEncoder（= ns_rumble/vendor 里那份，和雷云 DLL 逐帧对过）
  映射  ns_rumble.a2h_map.A2HToNS（两条曲线 + 瞬态 → 左右各 4 字节）
  出口  ns_rumble.device.NSController（0x10 报告，跟采集块走，约 20 ms 一个）

三处**有意偏离**（README 和工单里都记了）：
  1. 不 LoadLibrary 任何供应商 DLL，也不发 SENSA 比特流；
  2. 不用 haptic_mixer / har_engine —— 那是雷蛇多部位马达的混音层，本手柄只有左右两只；
  3. UI 的「配置文件模式」和「频段增益编辑」驱动不了对齐配方（配方写死在 SYNAPSE_PROFILE），
     所以那两个控件在这里是**关着的**，不假装能调。
"""

from __future__ import annotations

import threading
import time

from a2h_encoder import A2HEncoder
from analyzer import MODES, band_edges_for, band_gains_for
from audio_capture import LoopbackCapture
from ns_rumble.a2h_map import A2HToNS
from ns_rumble.codec import NEUTRAL
from ns_rumble.device import NSController
from ns_rumble.vendor.har_pack import frame_scaled


def _device_present() -> bool:
    try:
        import hid
        return bool(hid.enumerate(NSController.VID, NSController.PID))
    except Exception:                                        # noqa: BLE001
        return False


class HapticPipeline:
    def __init__(self, config):
        self.config = config
        self.lock = threading.Lock()
        mode = config.get("mode", "balanced")
        ok = _device_present()
        self.state = {
            "running": False,
            "vibration_on": bool(config.get("vibration_on", True)),
            "mode": mode,
            "gain": float(config.get("gain", 0.67)),
            "band": 0.0, "left": 0.0, "right": 0.0,
            "amp_l": 0.0, "amp_r": 0.0,
            "beat": False, "beats": 0,
            "viz": [0.0] * 16,
            "connected": ok,
            "audio_device": None,
            "error": None if ok else "没找到 057E:2009：切 NS 模式、插 USB 线",
            "band_gains": band_gains_for(config, mode),
            "band_edges": band_edges_for(config, mode),
            "audio_freq_hz": 0.0,
            "centroid_hz": 0.0,
            "pitch_norm": 0.0,
            "pitch_confidence": 0.0,
            "amp": 0.0,
            "encoder": "a2h",                # 只有这一种：和雷云 DLL 逐帧对过的那份
            "output": "ns-hd",               # 任天堂 0x10 振动报告
            "sample_rate": 48000,
            "n_channels": 2,
            "hid_voice": None,               # 这里放「最近一次发出去的 8 字节」
            "packets": 0,
        }
        self._enc = A2HEncoder(gain=1.0)     # 增益只在 frame_scaled 乘一次
        self._mapper = A2HToNS(48000.0)
        self._ns: NSController | None = None
        self._capture: LoopbackCapture | None = None
        self._total = 0
        self._last_conn_check = 0.0

    # ---------- UI 调用的控制接口（签名和 25 一致） ----------

    def set_vibration(self, on):
        with self.lock:
            self.state["vibration_on"] = bool(on)
            if not on:
                self._silence_out()

    def set_mode(self, mode):
        if mode not in MODES:
            return
        with self.lock:
            self.state["mode"] = mode
            self.state["band_gains"] = band_gains_for(self.config, mode)
            self.state["band_edges"] = band_edges_for(self.config, mode)
            # 对齐配方的模式写死在 SYNAPSE_PROFILE 里，这里不假装能切

    def set_gain(self, gain):
        with self.lock:
            self.state["gain"] = max(0.0, min(1.0, float(gain)))

    def set_band_gains(self, band_gains):
        with self.lock:
            self.state["band_gains"] = [max(0.0, min(2.0, float(g))) for g in band_gains]

    def set_band_edges(self, band_edges):
        with self.lock:
            self.state["band_edges"] = [max(30.0, min(200.0, float(e))) for e in band_edges]

    def set_encoder(self, kind):
        with self.lock:
            self.state["error"] = "本程序只有「对齐雷云」这一种编码器（不加载供应商 DLL）"

    def set_custom_overrides(self, overrides):
        self.config.setdefault("custom_overrides", {}).update(overrides)

    def snapshot(self):
        with self.lock:
            return dict(self.state)

    # ---------- 生命周期 ----------

    def start(self, device_name=None):
        if self.state["running"]:
            return True
        if not self._open_pad():
            return False
        self._capture = LoopbackCapture(self._on_block, device_name=device_name)
        self._capture.start()
        time.sleep(0.3)
        if self._capture.last_error:
            with self.lock:
                self.state["error"] = self._capture.last_error
            self._capture = None
            self._close_pad()
            return False
        with self.lock:
            self.state["running"] = True
            self.state["audio_device"] = self._capture.active_device
            self.state["sample_rate"] = int(getattr(self._capture, "sample_rate", 48000))
            self.state["n_channels"] = int(getattr(self._capture, "n_channels", 2))
            self.state["error"] = None
        return True

    def _open_pad(self) -> bool:
        if self._ns is not None:
            return True
        ns = NSController()
        try:
            ns.open()
            ns.init_usb()
            ns.enable_vibration()
        except Exception as exc:                              # noqa: BLE001
            with self.lock:
                self.state["connected"] = False
                self.state["error"] = f"手柄打不开/握手失败：{exc}"
            return False
        self._ns = ns
        self._total = 0
        sr = float(getattr(self._capture, "sample_rate", 48000) or 48000)
        self._mapper = A2HToNS(sr)
        with self.lock:
            self.state["connected"] = True
        return True

    def _close_pad(self):
        if self._ns is not None:
            try:
                self._ns.close()
            except Exception:                                # noqa: BLE001
                pass
            self._ns = None

    def _silence_out(self):
        self.state["left"] = self.state["right"] = 0.0
        self.state["hid_voice"] = None
        if self._ns is not None:
            try:
                self._ns.send(NEUTRAL, NEUTRAL)
            except Exception:                                # noqa: BLE001
                pass

    def restart_capture(self, device_name):
        self.stop_capture()
        return self.start(device_name)

    def stop_capture(self):
        if self._capture:
            self._capture.stop()
            self._capture.join(timeout=2)
            self._capture = None
        with self.lock:
            self.state["running"] = False
            self._silence_out()
            self.state["viz"] = [0.0] * 16
            for k in ("band", "audio_freq_hz", "centroid_hz", "pitch_norm",
                      "pitch_confidence", "amp", "amp_l", "amp_r"):
                self.state[k] = 0.0

    def shutdown(self):
        self.stop_capture()
        self._close_pad()
        with self.lock:
            self.state["connected"] = _device_present()

    # ---------- 采集线程回调 ----------

    def _on_block(self, samples):
        try:
            self._on_block_inner(samples)
        except Exception as exc:                              # noqa: BLE001
            with self.lock:
                self.state["error"] = f"链路异常：{exc}"

    def _on_block_inner(self, samples):
        with self.lock:
            sr = int(getattr(self._capture, "sample_rate", 48000) or 48000)
            gain = self.state["gain"]
            vibration_on = self.state["vibration_on"]
            self.state["sample_rate"] = sr
            self.state["n_channels"] = int(getattr(self._capture, "n_channels", 2) or 2)

        left, right, band, beat = self._enc.process_block(samples, sample_rate=sr)
        frame = frame_scaled(self._enc.last_frame, gain)
        self._total += int(getattr(samples, "shape", (0,))[0] or 0)
        left4, right4 = self._mapper.frame_to_bytes(
            frame, self._total, len(self._enc._raw_l))       # 只读编码器私有历史长度

        sent = None
        if vibration_on and self._ns is not None:
            self._ns.send(left4, right4)
            sent = f"{left4.hex(' ')} | {right4.hex(' ')}"

        curves = [list(p.curves) for p in frame.parts[:2]]
        amp_l = max((float(a) for a, _ in curves[0]), default=0.0) if curves else 0.0
        amp_r = max((float(a) for a, _ in curves[1]), default=0.0) if len(curves) > 1 else 0.0
        hz_first = curves[0][0][1] if curves and curves[0] else 0.0

        with self.lock:
            self.state["band"] = band
            self.state["left"] = left if vibration_on else 0.0
            self.state["right"] = right if vibration_on else 0.0
            self.state["amp_l"] = amp_l
            self.state["amp_r"] = amp_r
            self.state["beat"] = beat
            self.state["viz"] = self._enc.viz.tolist()
            self.state["audio_freq_hz"] = float(getattr(self._enc, "last_freq_hz", 0.0) or hz_first)
            self.state["centroid_hz"] = float(getattr(self._enc, "last_centroid_hz", 0.0) or 0.0)
            self.state["pitch_norm"] = float(getattr(self._enc, "last_pitch_norm", 0.0) or 0.0)
            self.state["pitch_confidence"] = float(getattr(self._enc, "last_pitch_confidence", 0.0) or 0.0)
            self.state["amp"] = float(getattr(self._enc, "last_amp", 0.0) or 0.0)
            self.state["hid_voice"] = sent
            if beat:
                self.state["beats"] += 1
            if vibration_on and self._ns is not None:
                self.state["packets"] += 1
            if not vibration_on:
                self._silence_out()

        if not self.state["connected"] and time.time() - self._last_conn_check > 1.0:
            self._last_conn_check = time.time()
            if _device_present():
                with self.lock:
                    self.state["connected"] = True
                    self.state["error"] = None
