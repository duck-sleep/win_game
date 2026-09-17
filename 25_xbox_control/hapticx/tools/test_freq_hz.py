#!/usr/bin/env python3
"""test_freq_hz.py — W2.2 离线主频/pitch 验收。"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analyzer import A2HAnalyzer  # noqa: E402
from audio_capture import SAMPLE_RATE  # noqa: E402

BLOCK = 960
DROP = 10
TONES = [50.0, 65.41, 80.0, 98.0, 110.0, 130.0]
AMP = 0.3
DUR = 1.0


def feed_tone(hz, dur=DUR, amp=AMP):
    n = int(SAMPLE_RATE * dur)
    t = np.arange(n) / SAMPLE_RATE
    sig = (amp * np.sin(2.0 * np.pi * hz * t)).astype(np.float64)
    az = A2HAnalyzer(mode="balanced", gain=0.67)
    freqs, pitches, confs = [], [], []
    for i in range(0, sig.size - BLOCK + 1, BLOCK):
        az.process_block(sig[i:i + BLOCK])
        freqs.append(az.last_freq_hz)
        pitches.append(az.last_pitch_norm)
        confs.append(az.last_pitch_confidence)
    use = slice(DROP, None)
    return (
        float(np.median(freqs[use])),
        float(np.median(pitches[use])),
        float(np.median(confs[use])),
        freqs,
    )


def switch_settle_ms(hz_a=50.0, hz_b=110.0):
    """切音后 last_freq 进入 ±5Hz 目标所需毫秒。"""
    az = A2HAnalyzer(mode="balanced", gain=0.67)
    n = int(SAMPLE_RATE * 1.0)
    t = np.arange(n) / SAMPLE_RATE
    a = (AMP * np.sin(2.0 * np.pi * hz_a * t)).astype(np.float64)
    b = (AMP * np.sin(2.0 * np.pi * hz_b * t)).astype(np.float64)
    for i in range(0, a.size - BLOCK + 1, BLOCK):
        az.process_block(a[i:i + BLOCK])
    hops = 0
    for i in range(0, b.size - BLOCK + 1, BLOCK):
        az.process_block(b[i:i + BLOCK])
        hops += 1
        if abs(az.last_freq_hz - hz_b) <= 5.0:
            return hops * (BLOCK / SAMPLE_RATE) * 1000.0
    return 1e9


def main():
    ok = True
    med_f = []
    print(f"{'tone':>8} {'median_freq':>12} {'median_pitch':>13} {'conf':>8}")
    for hz in TONES:
        mf, mp, mc, _ = feed_tone(hz)
        med_f.append(mf)
        print(f"{hz:8.2f} {mf:12.2f} {mp:13.3f} {mc:8.3f}")
        if abs(mf - hz) > 5.0:
            print(f"  FAIL 误差 {abs(mf - hz):.2f}Hz > 5")
            ok = False
        if not (0.0 <= mp <= 1.0):
            print("  FAIL pitch 不在 0–1")
            ok = False
    for a, b in zip(med_f, med_f[1:]):
        if not (b > a):
            print(f"  FAIL 主频未严格递增 {a:.2f} -> {b:.2f}")
            ok = False
    p50 = feed_tone(50.0)[1]
    p110 = feed_tone(110.0)[1]
    if not (p110 > p50):
        print(f"  FAIL 110 pitch ({p110:.3f}) 不大于 50 ({p50:.3f})")
        ok = False
    settle = switch_settle_ms()
    print(f"switch 50->110 settle_ms={settle:.1f}")
    if settle > 150.0:
        print("  FAIL 切音收敛 >150ms")
        ok = False

    az = A2HAnalyzer(mode="balanced")
    silence = np.zeros(BLOCK)
    for _ in range(30):
        az.process_block(silence)
    print(f"silence freq={az.last_freq_hz:.2f} pitch={az.last_pitch_norm:.3f}")
    if az.last_freq_hz != 0.0:
        print("  FAIL 静音 freq 应为 0")
        ok = False

    rng = np.random.default_rng(0)
    noise = rng.normal(0, 0.3, BLOCK * 40)
    az = A2HAnalyzer(mode="balanced")
    jumps = 0
    last = None
    for i in range(0, noise.size - BLOCK + 1, BLOCK):
        az.process_block(noise[i:i + BLOCK])
        if az.last_pitch_confidence >= 0.55 and az.last_freq_hz > 0:
            jumps += 1
        last = az.last_freq_hz
    print(f"noise high-conf blocks={jumps} last_freq={last:.2f}")
    if jumps > 15:
        print("  FAIL 噪声被当成明确音符过多")
        ok = False

    print("PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
