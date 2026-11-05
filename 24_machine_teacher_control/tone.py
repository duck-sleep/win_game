"""单音测试：`tone.py --hz 320 --amp 0.6 --sec 3 --side L`。

高频和低频振荡器设成同一个 Hz、同一个振幅（低频超过 626 Hz 编不进去，就把低频振幅设 0）。
没选中的那只手发静止。
"""

from __future__ import annotations

import argparse
import time

from ns_rumble.codec import NEUTRAL, encode_side
from ns_rumble.device import NSController

LF_HZ_MAX = 626.0


def side_bytes(hz: float, amp: float) -> bytes:
    amp = min(max(amp, 0.0), 1.0)
    lf_amp = 0.0 if hz > LF_HZ_MAX else amp
    return encode_side(hz, amp, hz, lf_amp)


def main() -> int:
    ap = argparse.ArgumentParser(description="单音振动测试")
    ap.add_argument("--hz", type=float, default=160.0)
    ap.add_argument("--amp", type=float, default=0.4)
    ap.add_argument("--sec", type=float, default=1.0)
    ap.add_argument("--side", choices=["L", "R", "both"], default="both")
    ap.add_argument("--send-ms", type=float, default=20.0)
    a = ap.parse_args()

    one = side_bytes(a.hz, a.amp)
    left = one if a.side in ("L", "both") else NEUTRAL
    right = one if a.side in ("R", "both") else NEUTRAL
    print(f"hz={a.hz:g} amp={min(max(a.amp, 0.0), 1.0):g} side={a.side} "
          f"左={left.hex(' ')} 右={right.hex(' ')} 每 {a.send_ms:g} ms 一个包，共 {a.sec:g} s")

    ns = NSController()
    ns.open()
    try:
        ns.init_usb()
        ns.enable_vibration()
        until = time.monotonic() + a.sec
        period = a.send_ms / 1000.0
        while time.monotonic() < until:
            ns.send(left, right)
            time.sleep(period)
    finally:
        ns.close()
    print("停")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
