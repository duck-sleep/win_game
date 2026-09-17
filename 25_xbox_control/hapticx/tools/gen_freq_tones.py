#!/usr/bin/env python3
"""gen_freq_tones.py — W1.1/W1.2 频率听诊用测试音（同等 RMS、带淡入淡出）。

用法:
  cd D:\\win_game_project\\25_xbox_control\\hapticx
  python tools\\gen_freq_tones.py
"""
from __future__ import annotations

import argparse
import os
import struct
import wave

import numpy as np

SAMPLE_RATE = 48000
TARGET_RMS = 0.20
FADE_SEC = 0.015
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tones")

TONES = [
    ("tone_050.wav", 50.0, 8.0),
    ("tone_080.wav", 80.0, 8.0),
    ("tone_110.wav", 110.0, 8.0),
    ("tone_130.wav", 130.0, 8.0),
    ("tone_200.wav", 200.0, 8.0),
]

# 小星星首句 C2 C2 G2 G2 A2 A2 G2 (Hz)
STAR_NOTES = [65.41, 65.41, 98.0, 98.0, 110.0, 110.0, 98.0]
NOTE_SEC = 0.6
GAP_SEC = 0.1


def _apply_fade(x: np.ndarray, sr: int, fade_sec: float) -> np.ndarray:
    n = int(sr * fade_sec)
    if n <= 0 or x.size < 2 * n:
        return x
    ramp = np.linspace(0.0, 1.0, n)
    y = x.copy()
    y[:n] *= ramp
    y[-n:] *= ramp[::-1]
    return y


def _normalize_rms(x: np.ndarray, target: float) -> np.ndarray:
    rms = float(np.sqrt(np.mean(x.astype(np.float64) ** 2)))
    if rms < 1e-12:
        return x
    return (x * (target / rms)).astype(np.float64)


def _sine_tone(freq: float, duration: float, target_rms: float = TARGET_RMS) -> np.ndarray:
    n = int(SAMPLE_RATE * duration)
    t = np.arange(n, dtype=np.float64) / SAMPLE_RATE
    x = np.sin(2.0 * np.pi * freq * t)
    x = _apply_fade(x, SAMPLE_RATE, FADE_SEC)
    return _normalize_rms(x, target_rms)


def _star_wav() -> np.ndarray:
    parts = []
    for hz in STAR_NOTES:
        seg = _sine_tone(hz, NOTE_SEC)
        parts.append(seg)
        parts.append(np.zeros(int(SAMPLE_RATE * GAP_SEC), dtype=np.float64))
    if parts:
        parts.pop()  # 末尾不要多余静音
    return np.concatenate(parts)


def _write_wav(path: str, samples: np.ndarray) -> float:
    samples = np.clip(samples, -1.0, 1.0)
    pcm = (samples * 32767.0).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(struct.pack(f"<{pcm.size}h", *pcm))
    return float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate frequency test WAVs for W1/W3B.")
    parser.add_argument("--out", default=OUT_DIR, help="Output directory")
    parser.add_argument("--factor", action="store_true",
                        help="Also generate 3x3 factor tones (50/80/110 Hz x RMS 0.10/0.20/0.30)")
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)

    print(f"out_dir={os.path.abspath(args.out)}  target_rms={TARGET_RMS}")
    for name, freq, dur in TONES:
        path = os.path.join(args.out, name)
        rms = _write_wav(path, _sine_tone(freq, dur))
        print(f"{name}  freq={freq:.1f}Hz  dur={dur}s  rms={rms:.6f}  path={path}")

    star_path = os.path.join(args.out, "star.wav")
    star = _normalize_rms(_star_wav(), TARGET_RMS)
    star_rms = _write_wav(star_path, star)
    dur = star.size / SAMPLE_RATE
    print(f"star.wav  notes={len(STAR_NOTES)}  dur={dur:.2f}s  rms={star_rms:.6f}  path={star_path}")

    if args.factor:
        print("--- factor 3x3 ---")
        for freq in (50.0, 80.0, 110.0):
            for amp in (0.10, 0.20, 0.30):
                tag_f = f"{int(freq):03d}"
                tag_a = f"{int(amp * 100):02d}"
                name = f"factor_F{tag_f}_A{tag_a}.wav"
                path = os.path.join(args.out, name)
                rms = _write_wav(path, _sine_tone(freq, 4.0, amp))
                print(f"{name}  freq={freq:.1f}Hz  dur=4.0s  rms={rms:.6f}  path={path}")


if __name__ == "__main__":
    main()
