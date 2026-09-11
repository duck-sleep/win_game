"""pipeline.py — HapticX 运行时管线:捕获 → 分析 → XInput,线程安全共享状态。

UI 线程通过 set_* 方法改参数(锁保护),捕获线程每 20ms 写一次快照,
UI 以 30fps 读取 state 渲染频谱与马达电平。
"""
import threading
import time

from analyzer import (A2HAnalyzer, MODES, band_edges_for, band_gains_for)
from audio_capture import LoopbackCapture
from xinput_out import ERROR_DEVICE_NOT_CONNECTED, XInputDevice


class HapticPipeline:
    def __init__(self, config):
        self.config = config
        self.lock = threading.Lock()
        mode = config.get("mode", "balanced")
        self.state = {
            "running": False,
            "vibration_on": bool(config.get("vibration_on", True)),
            "mode": mode,
            "gain": float(config.get("gain", 0.67)),
            "band": 0.0, "left": 0.0, "right": 0.0,
            "beat": False, "beats": 0,
            "viz": [0.0] * 16,
            "connected": False,
            "audio_device": None,
            "error": None,
            "band_gains": band_gains_for(config, mode),
            "band_edges": band_edges_for(config, mode),
        }
        self._pending = {}
        self._analyzer = A2HAnalyzer(
            mode=self.state["mode"], gain=self.state["gain"],
            overrides=config.get("custom_overrides") if self.state["mode"] == "custom" else None,
            band_gains=self.state["band_gains"],
            band_edges=self.state["band_edges"])
        self._device = XInputDevice(int(config.get("user_index", 0)))
        self._capture = None
        self._last_conn_check = 0.0

    # ---------- UI 调用的控制接口 ----------
    def set_vibration(self, on):
        with self.lock:
            self.state["vibration_on"] = bool(on)
            if not on:
                self.state["left"] = self.state["right"] = 0.0
                self._device.stop()

    def set_mode(self, mode):
        if mode not in MODES:
            return
        with self.lock:
            self.state["mode"] = mode
            # 每个模式有各自的频段增益曲线与边界,切换时一并加载
            gains = band_gains_for(self.config, mode)
            edges = band_edges_for(self.config, mode)
            self.state["band_gains"] = gains
            self.state["band_edges"] = edges
            self._analyzer.reconfigure(
                mode=mode, overrides=self.config.get("custom_overrides"),
                band_gains=gains, band_edges=edges)

    def set_gain(self, gain):
        with self.lock:
            self.state["gain"] = max(0.05, min(1.5, float(gain)))
            self._analyzer.reconfigure(gain=self.state["gain"])

    def set_band_gains(self, band_gains):
        with self.lock:
            gains = [max(0.0, min(2.0, float(g))) for g in band_gains]
            # 记到当前模式名下,切走再切回时保留这次的调整
            self.config.setdefault("mode_band_gains", {})[self.state["mode"]] = gains
            self.state["band_gains"] = list(gains)
            self._analyzer.set_band_gains(gains)

    def set_band_edges(self, band_edges):
        with self.lock:
            edges = [max(30.0, min(200.0, float(e))) for e in band_edges]
            # 边界同样记到当前模式名下
            self.config.setdefault("mode_band_edges", {})[self.state["mode"]] = edges
            self.state["band_edges"] = list(edges)
            self._analyzer.set_band_edges(edges)

    def set_custom_overrides(self, overrides):
        with self.lock:
            self.config["custom_overrides"].update(overrides)
            if self.state["mode"] == "custom":
                self._analyzer.reconfigure(
                    mode="custom", overrides=self.config["custom_overrides"])

    def snapshot(self):
        with self.lock:
            return dict(self.state)

    # ---------- 生命周期 ----------
    def start(self, device_name=None):
        if self.state["running"]:
            return True
        if not self._device.available:
            self.state["error"] = "未找到 xinput DLL"
            return False
        self.state["connected"] = self._device.is_connected()
        if not self.state["connected"]:
            self.state["error"] = "XInput 未检测到手柄(请切到 Xbox 模式)"
            return False

        self._capture = LoopbackCapture(self._on_block, device_name=device_name)
        self._capture.start()
        time.sleep(0.3)
        if self._capture.last_error:
            self.state["error"] = self._capture.last_error
            self._capture = None
            return False
        self.state["running"] = True
        self.state["error"] = None
        self.state["audio_device"] = self._capture.active_device
        return True

    def restart_capture(self, device_name):
        self.stop_capture()
        return self.start(device_name)

    def stop_capture(self):
        if self._capture:
            self._capture.stop()
            self._capture.join(timeout=2)
            self._capture = None
        self.state["running"] = False
        self._device.stop()
        with self.lock:
            self.state["viz"] = [0.0] * 16
            self.state["band"] = self.state["left"] = self.state["right"] = 0.0

    def shutdown(self):
        self.stop_capture()
        self._device.stop()

    # ---------- 捕获线程回调 ----------
    def _on_block(self, samples):
        with self.lock:
            analyzer = self._analyzer
            left, right, band, beat = analyzer.process_block(samples)
            vibration_on = self.state["vibration_on"]
            self.state["band"] = band
            self.state["left"] = left if vibration_on else 0.0
            self.state["right"] = right if vibration_on else 0.0
            self.state["beat"] = beat
            self.state["viz"] = analyzer.viz.tolist()
            if beat:
                self.state["beats"] += 1
            if vibration_on:
                ok = self._device.set_vibration(left, right)
                if not ok and self._device.last_error == ERROR_DEVICE_NOT_CONNECTED:
                    self.state["connected"] = False
                    self.state["left"] = self.state["right"] = 0.0
        # 断连后每 1s 探测一次重连
        if not self.state["connected"] and time.time() - self._last_conn_check > 1.0:
            self._last_conn_check = time.time()
            if self._device.is_connected():
                with self.lock:
                    self.state["connected"] = True
                    self.state["error"] = None
