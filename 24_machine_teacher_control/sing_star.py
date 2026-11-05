"""让手柄唱小星星 / 唱音阶。

  sing_star.py                 唱小星星
  sing_star.py --scale         唱音阶 do→高音 do
  sing_star.py --octave 3      换八度（哪档好听由用户定）

每个音：前 `拍长 × legato` 发这个音，剩下的时间发静止 —— 这样「1 1」两个同音能分开。
发包是连续的（每 send-ms 一个包），不是只在换音时发。
"""

from __future__ import annotations

import argparse
import time

from ns_rumble.codec import NEUTRAL, freq_code
from ns_rumble.device import NSController
from ns_rumble.song import NAME, SCALE, TWINKLE, degree_hz
from tone import side_bytes


def real_hz(hz: float) -> float:
    """编码后真正落到的频率（1/32 八度一档，最大误差 ±18.75 音分）。"""
    return 10.0 * 2.0 ** (freq_code(hz) / 32.0)


def main() -> int:
    ap = argparse.ArgumentParser(description="手柄唱小星星")
    ap.add_argument("--octave", type=int, default=4)
    ap.add_argument("--bpm", type=float, default=100.0)
    ap.add_argument("--amp", type=float, default=0.5)
    ap.add_argument("--legato", type=float, default=0.85)
    ap.add_argument("--scale", action="store_true", help="唱音阶而不是小星星")
    ap.add_argument("--send-ms", type=float, default=20.0)
    a = ap.parse_args()

    seq = SCALE if a.scale else TWINKLE
    beat = 60.0 / a.bpm
    period = a.send_ms / 1000.0

    ns = NSController()
    ns.open()
    try:
        ns.init_usb()
        ns.enable_vibration()
        for i, (deg, beats) in enumerate(seq):
            octv = a.octave + (1 if (a.scale and i == len(seq) - 1) else 0)
            if deg == 0:
                sounding, b = 0.0, NEUTRAL
                print(f"休止                                                        静止")
            else:
                hz = degree_hz(deg, octv)
                b = side_bytes(hz, a.amp)
                sounding = beats * beat * a.legato
                print(f"{deg} {NAME[deg]}{octv:<3} 目标 {hz:7.2f} Hz  "
                      f"实际 {real_hz(hz):7.2f} Hz  左 {b.hex(' ')}  右 {b.hex(' ')}")
            total = beats * beat
            t0 = time.monotonic()
            while True:
                el = time.monotonic() - t0
                if el >= total:
                    break
                ns.send(b if el < sounding else NEUTRAL, b if el < sounding else NEUTRAL)
                time.sleep(period)
    except KeyboardInterrupt:
        print("（中断）")
    finally:
        ns.close()
    print("唱完")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
