"""机械师 G6 V2（NS 模式）USB 探测。默认不震。

python probe_ns_usb.py            只握手，打印设备回复
python probe_ns_usb.py --rumble   握手后按 160 / 320 / 640 Hz 各震 0.6 秒
"""
from __future__ import annotations

import sys
import time

import hid

VID, PID = 0x057E, 0x2009
USB_LEN = 64
NEUTRAL = bytes([0x00, 0x01, 0x40, 0x40])


def hexs(b) -> str:
    return " ".join(f"{x:02x}" for x in b)


def write(dev, payload: bytes) -> int:
    buf = bytes(payload) + bytes(USB_LEN - len(payload))
    return dev.write(buf)


def read_until(dev, want0: int, want1: int | None = None, ms: int = 200):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        r = dev.read(USB_LEN, 20)
        if r and r[0] == want0 and (want1 is None or (len(r) > 1 and r[1] == want1)):
            return bytes(r)
    return None


def proprietary(dev, cmd: int, wait: bool = True):
    n = write(dev, bytes([0x80, cmd]))
    rep = read_until(dev, 0x81, cmd) if wait else None
    print(f"80 {cmd:02x}  write={n}  reply={hexs(rep[:12]) if rep else '无'}")
    return rep


def enc_freq(hz: float) -> int:
    hz = min(max(hz, 0.0), 1252.0)
    import math
    return int(round(math.log2(hz / 10.0) * 32.0)) if hz > 0 else 0


def enc_amp(amp: float) -> int:
    """振幅档 0–100（dekuNukem 振幅表第 i 行，HA=2i）。100 = 1.003，再高伤 LRA。"""
    import math
    if amp <= 0:
        return 0
    if amp > 0.23:
        i = round(math.log2(amp * 8.7) * 32.0)
    elif amp > 0.12:
        i = round(math.log2(amp * 17.0) * 16.0)
    else:
        i = max(1, round(15 + 4 * math.log2(amp / 0.112491)))
    return max(0, min(100, int(i)))


def rumble4(hz: float, amp: float) -> bytes:
    """同一个频率放进高频和低频两路，两路同一振幅。"""
    if amp <= 0:
        return NEUTRAL
    e = enc_freq(hz)
    i = enc_amp(min(amp, 1.0))
    hf = max(0x04, min(0x1FC, (e - 0x60) * 4))
    lf = max(0x01, min(0x7F, e - 0x40))
    hf_amp = i * 2
    lf_amp = ((i & 1) << 15) | (0x40 + (i >> 1))
    return bytes([
        hf & 0xFF,
        (hf_amp | ((hf >> 8) & 0x01)) & 0xFF,
        (lf | ((lf_amp >> 8) & 0x80)) & 0xFF,
        lf_amp & 0xFF,
    ])


def main() -> None:
    infos = [d for d in hid.enumerate(VID, PID)]
    print(f"enumerate {VID:04x}:{PID:04x} -> {len(infos)}")
    for d in infos:
        print(f"  path={d['path']!r} manufacturer={d['manufacturer_string']!r} "
              f"product={d['product_string']!r} serial={d['serial_number']!r} "
              f"usage_page={d['usage_page']:#x} usage={d['usage']:#x} if={d['interface_number']}")
    if not infos:
        sys.exit("没找到 057e:2009，确认手柄在 NS 模式并用 USB 线连着")
    dev = hid.device()
    dev.open_path(infos[0]["path"])
    dev.set_nonblocking(False)
    early = dev.read(USB_LEN, 100)
    print("握手前读到", hexs(early[:12]) if early else "无")
    st = proprietary(dev, 0x01)
    if st:
        print(f"  设备类型字节 {st[3]:02x}（3=Pro），MAC 倒序 {hexs(st[4:10])}")
    proprietary(dev, 0x02)
    proprietary(dev, 0x03)
    proprietary(dev, 0x02)
    proprietary(dev, 0x04, wait=False)
    n = write(dev, bytes([0x01, 0x00]) + NEUTRAL + NEUTRAL + bytes([0x48, 0x01]))
    rep = read_until(dev, 0x21, ms=300)
    print(f"子命令 48 01（开振动） write={n} reply={hexs(rep[:16]) if rep else '无'}")
    if "--rumble" in sys.argv:
        counter = 1
        for hz in (160.0, 320.0, 640.0):
            data = rumble4(hz, 0.5)
            print(f"{hz:.0f} Hz amp 0.5 -> {hexs(data)}")
            t_end = time.time() + 0.6
            while time.time() < t_end:
                write(dev, bytes([0x10, counter & 0x0F]) + data + data)
                counter += 1
                time.sleep(0.03)
            write(dev, bytes([0x10, counter & 0x0F]) + NEUTRAL + NEUTRAL)
            counter += 1
            time.sleep(0.4)
    seen = {}
    t_end = time.time() + 0.5
    while time.time() < t_end:
        r = dev.read(USB_LEN, 20)
        if r:
            seen[r[0]] = seen.get(r[0], 0) + 1
    print("握手后 0.5 秒收到的输入报告号", {f"{k:02x}": v for k, v in seen.items()})
    dev.close()


if __name__ == "__main__":
    main()
