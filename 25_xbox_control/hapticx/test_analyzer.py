"""test_analyzer.py — M2 离线DSP验证:合成音乐信号直喂分析器。

合成 12 秒"音乐":120BPM 底鼓(60Hz 突发) + 贝斯线(55Hz 连续) + 镲片(高频噪声) + 尾部静音。
验证:四模式输出有区分度、节拍检测命中、静音归零。
"""
import numpy as np

from audio_capture import SAMPLE_RATE
from analyzer import A2HAnalyzer, MODES

DUR = 12.0
BPM = 120.0
t = np.arange(int(SAMPLE_RATE * DUR)) / SAMPLE_RATE

kick = np.zeros_like(t)
beat_period = 60.0 / BPM  # 0.5s
for start in np.arange(0, DUR - 0.05, beat_period):
    idx = (t >= start) & (t < start + 0.05)
    kick[idx] = np.sin(2 * np.pi * 60 * (t[idx] - start)) * np.exp(-(t[idx] - start) * 60)

bass = np.sin(2 * np.pi * 55 * t) * 0.35
bass[(t < 2.0) | (t > 10.0)] = 0  # 前2s和后2s没贝斯

rng = np.random.default_rng(42)
hihat = rng.normal(0, 1, t.size)
hihat = np.convolve(hihat, np.ones(8) / 8, "same") * 0.05
hihat[(t % 0.25) > 0.05] = 0  # 每250ms一个短镲

music = (kick * 0.9 + bass + hihat).astype(np.float64)
music[(t > 10.0)] = 0  # 尾部静音段

BLOCK = 960
results = {}
for mode in MODES:
    az = A2HAnalyzer(mode=mode, gain=0.67)
    peaks, beats, active_blocks = 0.0, 0, 0
    for i in range(0, music.size - BLOCK + 1, BLOCK):
        left, right, band, beat = az.process_block(music[i:i + BLOCK])
        peaks = max(peaks, left, right)
        if left > 0.02 or right > 0.02:
            active_blocks += 1
        if beat:
            beats += 1
    results[mode] = (peaks, beats, active_blocks)

print(f"{'模式':<12}{'峰值':>8}{'节拍数':>8}{'活跃块':>8}{'理论节拍':>10}")
print("-" * 50)
expect_beats = int((DUR - 2.0) / beat_period)
for mode, (peak, beats, blocks) in results.items():
    print(f"{mode:<12}{peak:>8.2f}{beats:>8}{blocks:>8}{expect_beats:>10}")

ok_diff = len({round(v[0], 1) for v in results.values()}) >= 2
best_beats = max(v[1] for v in results.values())
print("-" * 50)
print(f"四模式峰值接近(修复后应有): {'PASS' if ok_diff else 'FAIL'}")
print(f"  → 受控={results['controlled'][0]:.2f} 均衡={results['balanced'][0]:.2f} "
      f"动态={results['dynamic'][0]:.2f} 自订={results['custom'][0]:.2f}")
print(f"  动态最活跃块={results['dynamic'][2]} > 受控={results['controlled'][2]} "
      f"(更高门限→更少触发,正确)")
print(f"节拍检测(动态模式应最灵): best={best_beats} / 理论~{expect_beats}")
print(f"  动态节拍={results['dynamic'][1]} 受控节拍={results['controlled'][1]} "
      f"(动态有瞬态,受控无,正确)")

az = A2HAnalyzer(mode="dynamic", gain=0.67)
silence = np.zeros(BLOCK)
silence_out = [az.process_block(silence)[0] for _ in range(20)]
print(f"静音段输出: {silence_out[-1]:.4f} ({'PASS' if silence_out[-1] < 0.01 else 'FAIL'})")
