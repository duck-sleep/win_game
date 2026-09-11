#!/usr/bin/env python3
"""crosscheck_gen.py — 生成 DSP 对拍 fixture(Windows 基准端)。

用确定性合成信号(鼓点+正弦混合)跑 Windows 版 analyzer.py 的 A2HAnalyzer,
把逐块输入样本与期望输出(left/right/level/transient)写入 CSV,
供安卓端 Kotlin A2HAnalyzer 数值对拍(验收标准见 10_安卓雷云技术.md §参数迁移)。

用法:
  cd D:\\win_game_project\\25_xbox_control\\hapticx
  python tools\\crosscheck_gen.py     # 生成 ../hapticx-android/tools/crosscheck_fixture.csv
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analyzer import A2HAnalyzer, BAND_EDGES  # noqa: E402

BLOCK = 960          # 20ms @48k
N_BLOCKS = 60        # 共 1.2s,足够触发多次瞬态节拍

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "..", "hapticx-android", "tools", "crosscheck_fixture.csv")

# 动态模式 + 自定频段增益/边界:把三条代码路径全部压进对拍
MODE = "dynamic"
GAIN = 0.67
BAND_GAINS = [1.3, 0.6, 0.2]          # dynamic 预设
BAND_EDGES_CUSTOM = [30.0, 65.0, 105.0, 200.0]  # 拖过的边界,验证 edge 路径


def make_signal():
    """确定性信号:48k 采样,45/80/115Hz 正弦 + 鼓点冲击 + 低噪底。"""
    rng = np.random.RandomState(42)
    n = BLOCK * N_BLOCKS
    t = np.arange(n) / 48000.0
    sig = 0.10 * np.sin(2 * np.pi * 45.0 * t)          # 超低音持续
    sig += 0.06 * np.sin(2 * np.pi * 80.0 * t)          # 低音持续
    # 鼓点:每 0.24s 一个指数衰减冲击(触发瞬态检测)
    for hit in np.arange(0.0, t[-1], 0.24):
        idx = int(hit * 48000)
        dur = int(0.09 * 48000)
        env = np.exp(-np.linspace(0, 9, dur))
        sig[idx:idx + dur] += 0.85 * env * np.sin(
            2 * np.pi * 55.0 * np.linspace(0, dur / 48000, dur))
    sig += 0.004 * rng.randn(n)                          # 噪底
    return sig


def main():
    sig = make_signal()
    an = A2HAnalyzer(mode=MODE, gain=GAIN,
                     band_gains=BAND_GAINS, band_edges=BAND_EDGES_CUSTOM)
    rows = []
    for b in range(N_BLOCKS):
        blk = sig[b * BLOCK:(b + 1) * BLOCK]
        left, right, level, transient = an.process_block(blk)
        rows.append((b, left, right, level, 1 if transient else 0, blk))
    viz_final = an.viz.copy()

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write(f"# crosscheck fixture v1 | mode={MODE} gain={GAIN} "
                f"band_gains={BAND_GAINS} band_edges={BAND_EDGES_CUSTOM} "
                f"blocks={N_BLOCKS} block={BLOCK} beat_count={an.beat_count}\n")
        for (b, l, r, s, t, blk) in rows:
            f.write(f"B,{l:.12g},{r:.12g},{s:.12g},{t}\n")
            f.write(",".join(f"{x:.12g}" for x in blk) + "\n")
        f.write("V," + ",".join(f"{v:.12g}" for v in viz_final) + "\n")
    print(f"written: {os.path.abspath(OUT)}  beat_count={an.beat_count}")
    print("sample outputs (block: left right):")
    for b in range(0, N_BLOCKS, 10):
        print(f"  {b}: {rows[b][1]:.6f} {rows[b][2]:.6f}")


if __name__ == "__main__":
    main()
