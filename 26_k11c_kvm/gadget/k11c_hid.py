#!/usr/bin/env python3
"""往 K11C 的 HID gadget 里写报文，用来验证"被控机真的收到键鼠了"。

报文格式照 jetkvm/kvm：
  键盘 /dev/hidg0  8 字节 = [modifier, 0, key1..key6]      （boot protocol，无 report id）
  绝对鼠标 /dev/hidg1 6 字节 = [1, buttons, x_lo, x_hi, y_lo, y_hi]，x/y 为 0..32767
  滚轮   /dev/hidg1 4 字节 = [2, wheelY, wheelX(AC Pan), 0] （report id 2）

用法:
  k11c_hid.py type "HELLO 123"      # 打字
  k11c_hid.py move 0.5 0.5          # 光标移到屏幕正中（0..1 归一化，也可给 0..32767 的整数）
  k11c_hid.py click [left|right]    # 点一下
  k11c_hid.py wheel 3               # 向下滚 3 格
需要在板子上以 root 跑（/dev/hidg* 属 root）。
"""

import sys
import time

KB = "/dev/hidg0"
MOUSE = "/dev/hidg1"
DELAY = 0.012  # 每帧之间留一点，给主机轮询；JetKVM 的写超时是 100ms

MOD = {"ctrl": 0x01, "shift": 0x02, "alt": 0x04, "gui": 0x08}

# 只用得着的 US 键码
KEY = {
    " ": 0x2C,
    "\n": 0x28,
    "\t": 0x2B,
    "-": 0x2D,
    "=": 0x2E,
    "[": 0x2F,
    "]": 0x30,
    "\\": 0x31,
    ";": 0x33,
    "'": 0x34,
    ",": 0x36,
    ".": 0x37,
    "/": 0x38,
    "`": 0x35,
}
for i, c in enumerate("1234567890"):
    KEY[c] = 0x1E + i
for i, c in enumerate("abcdefghijklmnopqrstuvwxyz"):
    KEY[c] = 0x04 + i

# 需要 Shift 的字符 → (未移位字符, 是否移位)
SHIFTED = {c: KEY[c] for c in "!@#$%^&*()_+{}|:\"<>?~"
           if c in KEY}
SHIFT_MAP = {
    "!": "1", "@": "2", "#": "3", "$": "4", "%": "5", "^": "6", "&": "7",
    "*": "8", "(": "9", ")": "0", "_": "-", "+": "=", "{": "[", "}": "]",
    "|": "\\", ":": ";", '"': "'", "<": ",", ">": ".", "?": "/", "~": "`",
}


def write(dev, payload):
    with open(dev, "wb", buffering=0) as f:
        f.write(bytes(payload))
    time.sleep(DELAY)


def kb(mod=0, keys=()):
    k = list(keys)[:6] + [0] * (6 - len(list(keys)[:6]))
    write(KB, [mod, 0] + k)


def type_text(s):
    for ch in s:
        mod, base = 0, ch
        if ch.isupper():
            mod, base = MOD["shift"], ch.lower()
        elif ch in SHIFT_MAP:
            mod, base = MOD["shift"], SHIFT_MAP[ch]
        code = KEY.get(base)
        if code is None:
            kb()  # 松手，跳过不支持的字符
            continue
        write(KB, [mod, 0, code, 0, 0, 0, 0, 0])
        kb()


def norm(v):
    v = float(v)
    return int(v) if v > 32767 else int(v * 32767 if v <= 1.0 else v)


def move(x, y):
    xi, yi = norm(x), norm(y)
    write(MOUSE, [1, 0, xi & 0xFF, xi >> 8, yi & 0xFF, yi >> 8])


def click(button="left", x=None, y=None):
    bit = {"left": 0x01, "right": 0x02, "middle": 0x04}[button]
    if x is not None and y is not None:
        move(x, y)
    xi = yi = 0x7FFF
    write(MOUSE, [1, bit, xi & 0xFF, xi >> 8, yi & 0xFF, yi >> 8])
    write(MOUSE, [1, 0, xi & 0xFF, xi >> 8, yi & 0xFF, yi >> 8])


def wheel(n):
    v = max(-127, min(127, int(n)))
    write(MOUSE, [2, v & 0xFF, 0, 0])
    write(MOUSE, [2, 0, 0, 0])


def usage(msg=""):
    if msg:
        print(msg, file=sys.stderr)
    print(__doc__.strip().split("用法:")[-1])
    sys.exit(1)


def main():
    if len(sys.argv) < 2:
        usage()
    cmd = sys.argv[1]
    a = sys.argv[2:]
    if cmd == "type" and a:
        type_text(" ".join(a))
    elif cmd == "move" and len(a) >= 2:
        move(a[0], a[1])
    elif cmd == "click":
        click(*(a or ["left"]))
    elif cmd == "wheel" and a:
        wheel(a[0])
    else:
        usage(f"不认识: {cmd} {a}")


if __name__ == "__main__":
    main()
