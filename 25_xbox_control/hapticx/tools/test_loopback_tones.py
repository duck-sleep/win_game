#!/usr/bin/env python3
"""W2.6: play tone wavs on the default speaker, loopback-capture, log AudioF/Pitch."""
from __future__ import annotations

import os
import sys
import threading
import time
import wave

import numpy as np
import soundcard as sc

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analyzer import A2HAnalyzer  # noqa: E402
from audio_capture import BLOCKSIZE, SAMPLE_RATE, LoopbackCapture  # noqa: E402

TONES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tones")
FILES = ["tone_050.wav", "tone_110.wav"]
DROP = 15


def load_wav_mono(path):
    with wave.open(path, "rb") as w:
        nch = w.getnchannels()
        sr = w.getframerate()
        sw = w.getsampwidth()
        n = w.getnframes()
        raw = w.readframes(n)
    if sw != 2:
        raise SystemExit(f"{path}: need 16-bit PCM")
    data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if nch > 1:
        data = data.reshape(-1, nch).mean(axis=1)
    if sr != SAMPLE_RATE:
        raise SystemExit(f"{path}: sr={sr}, need {SAMPLE_RATE}")
    return data


def play_and_analyze(path):
    samples = load_wav_mono(path)
    stereo = np.column_stack([samples, samples])
    az = A2HAnalyzer(mode="balanced", gain=0.67)
    freqs, pitches, confs, amps = [], [], [], []
    lock = threading.Lock()

    def on_block(block):
        az.process_block(block)
        with lock:
            freqs.append(az.last_freq_hz)
            pitches.append(az.last_pitch_norm)
            confs.append(az.last_pitch_confidence)
            amps.append(az.last_amp)

    cap = LoopbackCapture(on_block)
    cap.start()
    time.sleep(0.4)
    if cap.last_error:
        cap.stop()
        cap.join(timeout=2)
        raise SystemExit(f"loopback: {cap.last_error}")

    speaker = sc.default_speaker()
    # Play a bit of leading silence so capture is already running.
    silence = np.zeros((int(SAMPLE_RATE * 0.2), 2), dtype=np.float32)
    speaker.play(silence, samplerate=SAMPLE_RATE)
    speaker.play(stereo, samplerate=SAMPLE_RATE)
    speaker.play(silence, samplerate=SAMPLE_RATE)
    time.sleep(0.2)
    cap.stop()
    cap.join(timeout=3)

    with lock:
        f, p, c, a = list(freqs), list(pitches), list(confs), list(amps)
    use = slice(DROP, max(DROP + 1, len(f) - 5))
    if not f:
        return {
            "device": cap.active_device,
            "n": 0,
            "median_freq": 0.0,
            "median_pitch": 0.0,
            "median_conf": 0.0,
            "median_amp": 0.0,
        }
    chunk_f = f[use] or f
    return {
        "device": cap.active_device,
        "n": len(f),
        "median_freq": float(np.median(chunk_f)),
        "median_pitch": float(np.median((p[use] or p))),
        "median_conf": float(np.median((c[use] or c))),
        "median_amp": float(np.median((a[use] or a))),
    }


def main():
    print("default speaker:", sc.default_speaker().name)
    rows = []
    ok = True
    for name in FILES:
        path = os.path.join(TONES_DIR, name)
        if not os.path.isfile(path):
            print("MISSING", path)
            ok = False
            continue
        print("playing", path)
        rec = play_and_analyze(path)
        rec["file"] = name
        rows.append(rec)
        print(
            f"  device={rec['device']} n={rec['n']} "
            f"AudioF={rec['median_freq']:.1f} Pitch={rec['median_pitch']:.2f} "
            f"Conf={rec['median_conf']:.2f} A={rec['median_amp']:.2f}"
        )
        time.sleep(0.4)

    if len(rows) == 2:
        f50, f110 = rows[0]["median_freq"], rows[1]["median_freq"]
        p50, p110 = rows[0]["median_pitch"], rows[1]["median_pitch"]
        sep = abs(f110 - f50) >= 40 and f50 > 0
        print(f"separate 50 vs 110? {sep}  ({f50:.1f} vs {f110:.1f})")
        print(f"pitch 110>50? {p110 > p50}  ({p50:.2f} vs {p110:.2f})")
        if not sep or not (40 <= f50 <= 70) or not (90 <= f110 <= 130):
            ok = False
        if not (0 <= p50 <= 1 and 0 <= p110 <= 1 and p110 > p50):
            ok = False
    print("PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
