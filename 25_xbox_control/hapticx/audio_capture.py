"""audio_capture.py — WASAPI 环回捕获线程(soundcard)。

对标雷云 RzAudioCapture 的采集参数:
  48kHz / float32 / 立体声 → 混音单声道,周期 20ms(雷云 period_ms=20)。
"""
import threading

import numpy as np
import soundcard as sc

SAMPLE_RATE = 48000
PERIOD_MS = 20
BLOCKSIZE = SAMPLE_RATE * PERIOD_MS // 1000  # 960


class LoopbackCapture(threading.Thread):
    def __init__(self, on_block, device_name=None):
        super().__init__(daemon=True, name="loopback-capture")
        self.on_block = on_block
        self.device_name = device_name
        self.stop_event = threading.Event()
        self.last_error = None
        self.active_device = None

    def _open_mic(self):
        if self.device_name:
            speaker = sc.get_speaker(self.device_name)
        else:
            speaker = sc.default_speaker()
        self.active_device = speaker.name
        return sc.get_microphone(id=str(speaker.name), include_loopback=True)

    def run(self):
        try:
            mic = self._open_mic()
        except Exception as exc:  # noqa: BLE001
            self.last_error = f"打开环回设备失败: {exc}"
            return
        try:
            with mic.recorder(samplerate=SAMPLE_RATE, blocksize=BLOCKSIZE) as rec:
                while not self.stop_event.is_set():
                    data = rec.record(numframes=BLOCKSIZE)
                    mono = np.mean(data, axis=1) if data.ndim == 2 else data
                    if mono.size:
                        self.on_block(mono)
        except Exception as exc:  # noqa: BLE001
            if not self.stop_event.is_set():
                self.last_error = f"捕获中断: {exc}"

    def stop(self):
        self.stop_event.set()


def list_output_devices():
    return [(s.name, s.id) for s in sc.all_speakers()]
