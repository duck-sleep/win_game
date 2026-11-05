"""audio_capture.py — 系统混音环回线程。

对标雷云 CAudioRecorder<float> 的行为，自己写 WASAPI，不加载 RzAudioCapture：
  跟设备 mix 采样率 / 多声道 float32 / 完整帧 / 约 20ms。
COM 打不开时退回 soundcard（同样保留立体声，不再混成单声道）。
"""
import threading

import numpy as np
import soundcard as sc

from wasapi_loopback import PERIOD_MS, WasapiLoopback, resolve_endpoint

SAMPLE_RATE = 48000  # 仅 fallback；正式路径跟 mix format
BLOCKSIZE = SAMPLE_RATE * PERIOD_MS // 1000  # 960 @ 48k fallback


class LoopbackCapture(threading.Thread):
    def __init__(self, on_block, device_name=None):
        super().__init__(daemon=True, name="loopback-capture")
        self.on_block = on_block
        self.device_name = device_name
        self.stop_event = threading.Event()
        self.last_error = None
        self.active_device = None
        self.endpoint_id = None
        self.sample_rate = SAMPLE_RATE
        self.n_channels = 2
        self.backend = None

    def run(self):
        try:
            name, endpoint_id = resolve_endpoint(self.device_name)
        except Exception as exc:  # noqa: BLE001
            self.last_error = f"解析输出设备失败: {exc}"
            return
        self.active_device = name
        self.endpoint_id = endpoint_id
        try:
            self._run_wasapi(endpoint_id)
            return
        except Exception as exc:  # noqa: BLE001
            if self.stop_event.is_set():
                return
            wasapi_err = exc
        try:
            self._run_soundcard(wasapi_err)
        except Exception as exc:  # noqa: BLE001
            if not self.stop_event.is_set():
                self.last_error = f"捕获中断: {exc}"

    def _run_wasapi(self, endpoint_id):
        cap = WasapiLoopback(endpoint_id=endpoint_id, period_ms=PERIOD_MS)
        try:
            cap.open()
        except Exception:
            cap.close()
            raise
        self.backend = "wasapi"
        self.sample_rate = cap.sample_rate
        self.n_channels = cap.n_channels
        self.endpoint_id = cap.endpoint_id or endpoint_id
        try:
            while not self.stop_event.is_set():
                block = cap.read_block(self.stop_event)
                if block.size and (block.shape[0] * block.shape[1]) % block.shape[1] == 0:
                    self.on_block(block)
        finally:
            cap.close()

    def _run_soundcard(self, wasapi_err):
        mic = sc.get_microphone(id=str(self.active_device), include_loopback=True)
        self.backend = "soundcard"
        self.last_error = None
        self._fallback_note = f"WASAPI 失败已回退 soundcard: {wasapi_err}"
        with mic.recorder(samplerate=SAMPLE_RATE, blocksize=BLOCKSIZE) as rec:
            self.sample_rate = SAMPLE_RATE
            while not self.stop_event.is_set():
                data = rec.record(numframes=BLOCKSIZE)
                if data.ndim == 1:
                    data = data.reshape(-1, 1)
                self.n_channels = int(data.shape[1])
                if data.size:
                    self.on_block(np.ascontiguousarray(data, dtype=np.float32))

    def stop(self):
        self.stop_event.set()


def list_output_devices():
    return [(s.name, s.id) for s in sc.all_speakers()]
