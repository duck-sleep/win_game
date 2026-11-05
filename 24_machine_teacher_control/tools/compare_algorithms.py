r"""算法层面一样吗？—— 同一首歌、同一份曲线，两边落到设备上的数值差多少。

分三层看，全部离线，不用耳朵：

  A 来源层：两边编码器输出的 (力度, Hz) 曲线  —— 同一份代码，应该完全相同（compare_two_apps 已证）
  B 量化层：同一组曲线，雷蛇的 q6_amp/q7_hz 和 NS 的 amp_index/freq_code 各把它变成什么值
  C 旋钮层：两边现在的 config 增益/模式不一样 —— 这会让"听起来不一样"，但和算法无关

用法：python tools\compare_algorithms.py
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ns_rumble.a2h_map import A2HToNS                          # noqa: E402
from ns_rumble.codec import encode_side                        # noqa: E402
from ns_rumble.vendor.har_pack import frame_scaled             # noqa: E402
from tools.compare_two_apps import (cents, decode_side, load_razer_encoder,
                                    read_wav)                   # noqa: E402

RAZER_DIR = Path(r"D:\win_game_project\25_xbox_control\hapticx")
BLOCK, SR = 960, 48000
BUCKETS = [(30, 60), (60, 120), (120, 250), (250, 400), (400, 2000)]


def load_razer_pack():
    """把 25 的 har_pack 单独装进来（它自己也是平级导入，靠 sys.path 追加）。"""
    if str(RAZER_DIR) not in sys.path:
        sys.path.append(str(RAZER_DIR))
    spec = importlib.util.spec_from_file_location("razer_har_pack", RAZER_DIR / "har_pack.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["razer_har_pack"] = mod
    spec.loader.exec_module(mod)
    return mod


def razer_lands(hz: float, amp: float, rp) -> tuple[float, float]:
    """雷蛇那条实际发到设备的值：6 位振幅 + 7 位音高（30–400 Hz 等分 128 格）。"""
    amp_q = rp.q6_amp(amp) / 63.0
    hz_q = rp.q7_hz(hz)
    hz_back = rp.MOTOR_FMIN + hz_q * (rp.MOTOR_FMAX - rp.MOTOR_FMIN) / 127.0
    return hz_back, amp_q


def ns_lands(hz: float, amp: float) -> tuple[float, float]:
    """NS 这条实际发到设备的值：4 字节反解（高频 + 低频都设成同一个目标）。"""
    b = encode_side(hz, amp, hz, 0.0 if hz > 626.29 else amp)
    hf_hz, hf_amp, lf_hz, lf_amp = decode_side(b)
    return (hf_hz, hf_amp) if hz > 626.29 else (lf_hz, lf_amp)


def bucket_of(hz: float) -> str:
    for lo, hi in BUCKETS:
        if lo <= hz < hi:
            return f"{lo}-{hi} Hz"
    return "<30 Hz"


def configs() -> None:
    print("【C · 旋钮层】两边现在的配置（这会让『听起来不一样』，和算法无关）：")
    r = json.loads((RAZER_DIR / "config.json").read_text(encoding="utf-8"))
    try:
        m = json.loads((ROOT / "hapticx_ns" / "config.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        m = {"note": "还没存过，用的是代码默认"}
    print(f"  雷蛇版  ：gain={r.get('gain')}  mode={r.get('mode')}  encoder={r.get('encoder')}")
    print(f"  机械师版：gain={m.get('gain', 0.67)}  mode={m.get('mode', 'balanced')}  "
          f"encoder=a2h（唯一）")
    print("  → 想公平对比，先把两边 gain/mode 拨到一样再听。\n")


def main() -> int:
    configs()

    rp = load_razer_pack()
    RazerEnc = load_razer_encoder()
    from ns_rumble.vendor.a2h_encoder import A2HEncoder as OurEnc

    for name, path in [("50 Hz 单音", str(RAZER_DIR.parent / "test_50hz.wav")),
                       ("40→900 扫频+鼓点", str(ROOT / "tools" / "sweep_drum.wav"))]:
        x = read_wav(path)
        e1, e2 = RazerEnc(gain=1.0), OurEnc(gain=1.0)
        mapper = A2HToNS(float(SR))
        GAIN = 0.67                                   # 两边用同一个增益，把旋钮差剔掉
        rows: dict[str, list[float]] = {}
        same_curve = True
        total = 0
        for start in range(0, x.shape[0] - BLOCK + 1, BLOCK):
            blk = x[start:start + BLOCK]
            e1.process_block(blk, SR)
            e2.process_block(blk, SR)
            total += BLOCK
            f1 = frame_scaled(e1.last_frame, GAIN)
            f2 = frame_scaled(e2.last_frame, GAIN)
            for p1, p2 in zip(f1.parts, f2.parts):
                if p1.curves != p2.curves:
                    same_curve = False
            left4, _ = mapper.frame_to_bytes(f2, total, len(e2._raw_l))
            (a0, h0), (a1, h1) = (f1.parts[0].curves + [(0.0, 0.0), (0.0, 0.0)])[:2]
            for want_hz, want_amp in ((h0, a0), (h1, a1)):
                if want_amp <= 0.01 or want_hz <= 0:
                    continue
                rz_hz, rz_amp = razer_lands(want_hz, want_amp, rp)
                ns_hz, ns_amp = ns_lands(want_hz, want_amp)
                key = bucket_of(want_hz)
                rows.setdefault(key, []).extend([
                    cents(want_hz, rz_hz), cents(want_hz, ns_hz), abs(rz_amp - want_amp),
                    abs(ns_amp - want_amp), cents(rz_hz, ns_hz)])

        print(f"【B · 量化层】{name}（两边增益都取 {GAIN}，来源曲线相同：{same_curve}）")
        print("  频段            样本   雷蛇音高误差(音分)   NS音高误差(音分)   雷蛇振幅误差   NS振幅误差   两边互差(音分)")
        for key in [f"{lo}-{hi} Hz" for lo, hi in BUCKETS]:
            v = rows.get(key)
            if not v:
                continue
            n = len(v) // 5
            m = [sum(v[i::5]) / n for i in range(5)]
            print(f"  {key:<14} {n:>5}   {m[0]:>14.1f}   {m[1]:>14.1f}   {m[2]:>12.3f}   {m[3]:>10.3f}   {m[4]:>10.1f}")
        print()

    print("【读法】")
    print("  · 雷蛇的音高是 **30–400 Hz 等分 128 格**（每格 2.91 Hz）⇒ 频率越低误差越大：")
    print("    47 Hz 处一格 ≈ 106 音分，400 Hz 处一格 ≈ 12.6 音分")
    print("  · NS 的音高是 **1/32 八度等比**（±18.75 音分恒定），但有两个硬下限：")
    print("    高频振荡器 ≥81.75 Hz、低频振荡器 ≥40.88 Hz ⇒ 低于下限会被夹（就是上次那条 🔴）")
    print("  · 振幅：雷蛇 6 位线性（1/63 ≈ 0.016 一格），NS 101 档对数（约 2.2% 一格）⇒ 都远小于听阈")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
