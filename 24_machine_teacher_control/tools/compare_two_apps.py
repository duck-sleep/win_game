r"""两边跑效果一样吗？—— 同一首歌，雷蛇版和机械师版各自拿到什么。

分两层量，都不用耳朵：

  第 1 层（输入）：25 的 a2h_encoder 和 24 用的那一份，逐块对比 (力度, Hz) 曲线。
                   同一份代码就该完全相同 ⇒ 有差别就是复制坏了。
  第 2 层（输出）：曲线交给 NS 的 4 字节之后，**再从这 4 字节反解回来**，
                   看这只手柄实际收到的频率/振幅和"想要的"差多少（量化台阶）。

  用法：python tools\compare_two_apps.py [wav路径]
"""

from __future__ import annotations

import importlib.util
import math
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]                 # 24_machine_teacher_control
sys.path.insert(0, str(ROOT))

from ns_rumble.a2h_map import A2HToNS                        # noqa: E402
from ns_rumble.codec import NEUTRAL                          # noqa: E402
from ns_rumble.vendor.a2h_encoder import A2HEncoder as OurEncoder   # noqa: E402
from ns_rumble.vendor.har_pack import frame_scaled           # noqa: E402

RAZER_DIR = Path(r"D:\win_game_project\25_xbox_control\hapticx")     # 只读，不改它
DEF_WAV = str(RAZER_DIR.parent / "test_50hz.wav")
BLOCK, SR = 960, 48000
GAIN = 0.67


def load_razer_encoder():
    """把 25 那份 a2h_encoder 单独装进一个模块名，它内部的 `from har_pack import …`
    靠把 25 目录追加到 sys.path 末尾来解析（追加而不是插到开头，免得反过来盖住我们的模块）。"""
    if str(RAZER_DIR) not in sys.path:
        sys.path.append(str(RAZER_DIR))
    spec = importlib.util.spec_from_file_location("razer_a2h", RAZER_DIR / "a2h_encoder.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["razer_a2h"] = mod
    spec.loader.exec_module(mod)
    return mod.A2HEncoder


def read_wav(path: str) -> np.ndarray:
    with wave.open(path, "rb") as w:
        if w.getsampwidth() != 2:
            raise SystemExit("只要 16 bit 的 wav")
        n, ch = w.getnframes(), w.getnchannels()
        x = np.frombuffer(w.readframes(n), dtype="<i2").reshape(-1, ch).astype(np.float32) / 32768.0
    return x if ch == 2 else np.repeat(x, 2, axis=1)


def amp_from_index(i: int) -> float:
    """amp_index 的反函数（按 i 落在哪一段分档，和编码时的三段一一对应）。"""
    if i <= 0:
        return 0.0
    if i > 32:
        return 2 ** (i / 32.0) / 8.7
    if i > 16:
        return 2 ** (i / 16.0) / 17.0
    return 0.112491 * 2 ** ((i - 15) / 4.0)


def decode_side(b: bytes) -> tuple[float, float, float, float]:
    """从一侧的 4 字节反解 (hf_hz, hf_amp, lf_hz, lf_amp)。"""
    hf_freq = ((b[1] & 0x01) << 8) | b[0]
    hf_i = (b[1] & 0xFE) >> 1
    lf_freq = b[2] & 0x7F
    raw = ((b[2] & 0x80) << 8) | b[3]
    odd = 1 if raw & 0x8000 else 0
    lf_i = (((raw & 0x7FFF) - 0x40) << 1) | odd
    hf_hz = 10.0 * 2.0 ** ((hf_freq / 4.0 + 0x60) / 32.0)
    lf_hz = 10.0 * 2.0 ** ((lf_freq + 0x40) / 32.0)
    return hf_hz, amp_from_index(hf_i), lf_hz, amp_from_index(lf_i)


def cents(a: float, b: float) -> float:
    return 0.0 if a <= 0 or b <= 0 else abs(1200.0 * math.log2(b / a))


def stat(name: str, vals: list[float]) -> None:
    if not vals:
        print(f"  {name}: 没有样本")
        return
    print(f"  {name}: 平均 {sum(vals) / len(vals):.2f}，最大 {max(vals):.2f}（n={len(vals)}）")


def layer1(path: str, x: np.ndarray) -> None:
    RazerEnc = load_razer_encoder()
    e1, e2 = RazerEnc(gain=1.0), OurEncoder(gain=1.0)
    d_amp = d_hz = 0.0
    n = 0
    for start in range(0, x.shape[0] - BLOCK + 1, BLOCK):
        blk = x[start:start + BLOCK]
        e1.process_block(blk, SR)
        e2.process_block(blk, SR)
        n += 1
        for p1, p2 in zip(e1.last_frame.parts, e2.last_frame.parts):
            for (a1, h1), (a2, h2) in zip(p1.curves, p2.curves):
                d_amp = max(d_amp, abs(float(a1) - float(a2)))
                d_hz = max(d_hz, abs(float(h1) - float(h2)))
    print(f"【第 1 层 · 输入】两边编码器逐块对比：{n} 块，"
          f"力度最大差 {d_amp:.2e}，Hz 最大差 {d_hz:.2e}")
    print("  → 差为 0 就说明 24 用的确实是 25 那份对齐过雷云 DLL 的编码器，没抄坏。\n")


def layer2(x: np.ndarray) -> None:
    enc = OurEncoder(gain=1.0)
    mapper = A2HToNS(float(SR))
    total = 0
    hf_cents, lf_cents, amp_err = [], [], []
    clamp_hi = clamp_lo = live = 0
    for start in range(0, x.shape[0] - BLOCK + 1, BLOCK):
        blk = x[start:start + BLOCK]
        enc.process_block(blk, SR)
        total += BLOCK
        frame = frame_scaled(enc.last_frame, GAIN)
        left4, _right4 = mapper.frame_to_bytes(frame, total, len(enc._raw_l))
        if left4 == NEUTRAL:
            continue
        live += 1
        # 用映射层的「本意值」比（含瞬态覆盖），拿编码器原曲线比会把瞬态也算成误差
        want_hf_hz, want_hf_amp, want_lf_hz, want_lf_amp = mapper.want[0]
        hf_hz, hf_amp, lf_hz, lf_amp = decode_side(left4)
        if want_hf_amp > 0.01:
            hf_cents.append(cents(want_hf_hz, hf_hz))
            amp_err.append(abs(hf_amp - want_hf_amp))
            if not (81.75 <= want_hf_hz <= 1252.57):
                clamp_hi += 1
        if want_lf_amp > 0.01:
            lf_cents.append(cents(want_lf_hz, lf_hz))
            amp_err.append(abs(lf_amp - want_lf_amp))
            if not (40.88 <= want_lf_hz <= 626.29):
                clamp_lo += 1
    print(f"【第 2 层 · 输出】曲线 → NS 4 字节 → 反解回来（{live} 块有振动）：")
    stat("高频振荡器音高误差（音分）", hf_cents)
    stat("低频振荡器音高误差（音分）", lf_cents)
    stat("振幅误差（0-1 绝对值）", amp_err)
    print(f"  超出可编码范围被夹掉的块：高频 {clamp_hi}，低频 {clamp_lo}")
    print("  参考：1 半音 = 100 音分；本编码 1 档 = 1/32 八度 ≈ 37.5 音分 ⇒ 音高最大 ±18.75 音分")


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else DEF_WAV
    x = read_wav(path)
    print(f"同一首歌：{path}   {x.shape[0] / SR:.2f} 秒  峰值 {np.abs(x).max():.3f}\n")
    layer1(path, x)
    layer2(x)
    print("\n【两边本质上不一样的四处（不是误差，是结构差别）】")
    print("  1. 雷蛇版把 float 力度/音高原样交给固件合成；NS 版由我们量化成「频率档 + 振幅档」⇒ 有台阶")
    print("  2. 瞬态：雷蛇固件自己处理；NS 版是我们设计的（高频临时改 160 Hz、持续 2 包）")
    print("  3. 包络：NS 那 4 字节里没有 attack/decay，靠每 20 ms 重发新值来「画」包络")
    print("  4. 左右：NS 协议分两半，但本手柄实测单侧不震（待 --lr-matrix 定性）"
          "⇒ 立体声分离可能是最大的一处实际差别")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
