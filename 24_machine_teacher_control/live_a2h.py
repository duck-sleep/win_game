r"""N7：抓电脑正在放的声音，实时变成手柄 HD 振动。

  python live_a2h.py                     一直跑，Ctrl+C 停
  python live_a2h.py --gain 0.5          改力度（音高不乘，和雷云口径一致）
  python live_a2h.py --no-transients     关瞬态（对比有没有「敲击感」）
  python live_a2h.py --print             每 10 块打一次左右 4 字节 + 两条曲线
  python live_a2h.py --seconds 6         只跑 6 秒（自检用）

链路（一块 20 ms，全在主线程，不开第二个定时器）：
  WasapiLoopback.read_block → A2HEncoder.process_block → frame_scaled(gain)
  → A2HToNS.frame_to_bytes → NSController.send
"""

from __future__ import annotations

import argparse
import time

from ns_rumble.a2h_map import A2HToNS
from ns_rumble.device import NSController
from ns_rumble.vendor.a2h_encoder import A2HEncoder
from ns_rumble.vendor.har_pack import frame_scaled
from ns_rumble.vendor.wasapi_loopback import WasapiLoopback


def main() -> int:
    ap = argparse.ArgumentParser(description="系统声音 → 手柄 HD 振动")
    ap.add_argument("--gain", type=float, default=0.67, help="力度增益，0-1（雷云滑条 67）")
    ap.add_argument("--no-transients", action="store_true", help="关掉瞬态叠加")
    ap.add_argument("--print", dest="do_print", action="store_true",
                    help="每 10 块打一行：左右 4 字节 + 两条曲线")
    ap.add_argument("--seconds", type=float, default=0.0, help="0 = 一直跑")
    a = ap.parse_args()
    gain = min(max(a.gain, 0.0), 1.0)

    cap = WasapiLoopback()
    cap.open()
    enc = A2HEncoder(gain=1.0)                       # 增益只在 frame_scaled 这里乘一次
    mapper = A2HToNS(cap.sample_rate, enable_transients=not a.no_transients)
    print(f"采集：{cap.sample_rate} Hz {cap.n_channels} 声道，每块 {cap.period_ms} ms；"
          f"增益 {gain:g}；瞬态 {'关' if a.no_transients else '开'}")

    ns = NSController()
    ns.open()
    ns.init_usb()
    ns.enable_vibration()
    print("手柄已握手、振动已使能。开始放音乐 —— Ctrl+C 停。")

    total = 0
    n = 0
    t0 = time.monotonic()
    try:
        while True:
            blk = cap.read_block()                   # 没声音也按时返回全零
            if blk is None or blk.shape[0] == 0:
                continue
            enc.process_block(blk, cap.sample_rate)
            total += blk.shape[0]
            frame = frame_scaled(enc.last_frame, gain)
            left4, right4 = mapper.frame_to_bytes(frame, total, len(enc._raw_l))
            ns.send(left4, right4)
            n += 1
            if a.do_print and n % 10 == 0:
                curves = [[(round(float(x), 3), round(float(y), 1)) for x, y in p.curves]
                          for p in frame.parts[:2]]
                print(f"  左={left4.hex(' ')}  右={right4.hex(' ')}  曲线={curves}")
            if a.seconds and time.monotonic() - t0 >= a.seconds:
                break
    except KeyboardInterrupt:
        print("\n（停了）")
    finally:
        ns.close()                                   # 里面会连发 3 个静止包
        cap.close()
        print(f"跑了 {n} 块（{time.monotonic() - t0:.1f} 秒），已发静止并关闭。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
