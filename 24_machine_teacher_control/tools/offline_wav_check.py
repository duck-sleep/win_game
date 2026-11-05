r"""离线验证：把一段真实 wav 喂进和 live_a2h.py **完全同一条链**，看吐出来的字节会不会变。

无人值守时能拿到的最强证据 —— 不需要手柄、不需要耳朵，只回答一个问题：
**真实音频经过编码器 + 映射之后，发出去的 8 字节是"一直在动"还是"死的"。**

  python tools\offline_wav_check.py [wav路径] [增益]
  默认用 D:\win_game_project\25_xbox_control\test_50hz.wav（只读，不改它）
"""

from __future__ import annotations

import sys
import wave
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))      # 工程根

from ns_rumble.a2h_map import A2HToNS                                # noqa: E402
from ns_rumble.codec import NEUTRAL                                   # noqa: E402
from ns_rumble.vendor.a2h_encoder import A2HEncoder                   # noqa: E402
from ns_rumble.vendor.har_pack import frame_scaled                    # noqa: E402

DEF_WAV = r"D:\win_game_project\25_xbox_control\test_50hz.wav"
LOG = Path(__file__).with_name("offline_wav_check.out.txt")
BLOCK = 960                        # 20 ms @48k，和 live_a2h 一致
_lines: list[str] = []


def say(msg: str = "") -> None:
    print(msg)
    _lines.append(msg)


def read_wav(path: str) -> tuple[np.ndarray, int]:
    with wave.open(path, "rb") as w:
        rate = w.getframerate()
        nch = w.getnchannels()
        if w.getsampwidth() != 2:
            raise SystemExit(f"只支持 16 bit，这份是 {w.getsampwidth() * 8} bit")
        raw = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
    x = raw.reshape(-1, nch).astype(np.float32) / 32768.0
    if nch == 1:
        x = np.repeat(x, 2, axis=1)
    return x[:, :2], rate


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else DEF_WAV
    gain = float(sys.argv[2]) if len(sys.argv) > 2 else 0.67
    x, rate = read_wav(path)
    peak = float(np.max(np.abs(x))) if x.size else 0.0
    say(f"输入 {path}")
    say(f"  {rate} Hz  {x.shape[0]} 帧（{x.shape[0] / rate:.2f} 秒）  峰值 {peak:.4f}  增益 {gain}")

    enc = A2HEncoder(gain=1.0)
    mapper = A2HToNS(float(rate))
    total = 0
    combos: Counter = Counter()
    live = 0
    blocks = 0
    amp_max = [0.0, 0.0]
    hz_seen: Counter = Counter()
    samples: list[str] = []

    for start in range(0, x.shape[0] - BLOCK + 1, BLOCK):
        blk = x[start:start + BLOCK]
        enc.process_block(blk, rate)
        total += blk.shape[0]
        frame = frame_scaled(enc.last_frame, gain)
        left4, right4 = mapper.frame_to_bytes(frame, total, len(enc._raw_l))
        blocks += 1
        combos[(left4, right4)] += 1
        if left4 != NEUTRAL or right4 != NEUTRAL:
            live += 1
        for hand, part in enumerate(frame.parts[:2]):
            for a, hz in part.curves:
                amp_max[hand] = max(amp_max[hand], float(a))
                if float(a) > 0.05:
                    hz_seen[round(float(hz), 1)] += 1
        if blocks <= 12 or blocks % 50 == 0:
            c = [[(round(float(a), 3), round(float(h), 1)) for a, h in p.curves]
                 for p in frame.parts[:2]]
            samples.append(f"  {start / rate:5.2f}s  左={left4.hex(' ')}  右={right4.hex(' ')}  曲线={c}")

    say(f"块数 {blocks}，非静止块 {live}（{live / max(1, blocks) * 100:.0f}%），"
        f"出现过的字节组合 {len(combos)} 种")
    say("最常见 5 种：")
    for (l, r), n in combos.most_common(5):
        tag = "静止" if l == NEUTRAL and r == NEUTRAL else "有振动"
        say(f"  {n:4d} 次  左={l.hex(' ')} 右={r.hex(' ')}  [{tag}]")
    say(f"左手最大力度 {amp_max[0]:.3f}，右手最大力度 {amp_max[1]:.3f}")
    say("有信号的音高（力度>0.05）前几名：" +
        ", ".join(f"{hz} Hz×{n}" for hz, n in hz_seen.most_common(6)))
    say("\n前 12 块 + 每 50 块一行的样本：")
    for s in samples:
        say(s)

    if blocks == 0:
        say("\n❌ 一块都没喂进去 → wav 太短或采样率不对。")
    elif len(combos) <= 1:
        say("\n❌ 全程只有一种字节组合 → 这条链在真实音频上是死的，先查编码器输入范围（是不是 /32768 弄错）。")
    elif live == 0:
        say("\n❌ 组合虽然变过，但全是静止包 → 映射把力度判成 0 了，查增益和 amp_index。")
    else:
        say(f"\n✅ 真实音频能驱动出变化的振动包：{live}/{blocks} 块非静止、{len(combos)} 种组合。"
            "剩下要人耳判的只有『听起来像不像』，不是『有没有动』。")

    LOG.write_text("\r\n".join(_lines) + "\r\n", encoding="utf-8")
    print(f"（写到 {LOG.name}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
