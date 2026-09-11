"""profiles_shot.py — 启动 App、切到配置文件页签、截屏、退出。"""
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from capture_window import capture, find_window


def bmp2png(src, dst):
    d = open(src, "rb").read()
    off = struct.unpack("<I", d[10:14])[0]
    w, h = struct.unpack("<ii", d[18:26])
    top_down = h < 0
    h = abs(h)
    rows = []
    stride = (w * 3 + 3) & ~3
    raw = d[off:]
    order = range(h) if top_down else range(h - 1, -1, -1)
    for y in order:
        row = bytearray()
        base = y * stride
        for x in range(w):
            b_, g_, r_ = raw[base + x * 3: base + x * 3 + 3]
            row += bytes((r_, g_, b_))
        rows.append(b"\x00" + bytes(row))

    def chunk(tag, data):
        # PNG 规范：chunk 长度和 CRC 都是大端（>I）。之前用 "<I" 产出的 PNG 是坏图，
        # 会导致读图的会话报"图片格式不支持"(11135) 直接挂掉。
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(b"".join(rows), 6))
    png += chunk(b"IEND", b"")
    open(dst, "wb").write(png)
    return w, h


def main():
    from app import App
    app = App()

    def step1():
        app._show_haptic_tab("profiles")
        app.update_idletasks()
        app.update()

    def step2():
        wins = find_window("HapticX")
        if wins:
            w, h = capture(wins[0][0], "ui_preview_profiles.bmp")
            bmp2png("ui_preview_profiles.bmp", "ui_preview_profiles.png")
            print(f"SHOT_OK {w}x{h}")
        else:
            print("WINDOW_NOT_FOUND")
        app.after(200, app._on_close)

    app.after(1500, step1)
    app.after(2500, step2)
    app.mainloop()


if __name__ == "__main__":
    main()
