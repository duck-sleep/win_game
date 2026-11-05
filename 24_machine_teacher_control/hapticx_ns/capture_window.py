"""capture_window.py - capture a window by title prefix to BMP (no deps)."""
import ctypes
import ctypes.wintypes as wt
import struct
import sys

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

SRCCOPY = 0x00CC0020
BI_RGB = 0
DIB_RGB_COLORS = 0


def find_window(prefix):
    result = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def cb(hwnd, _l):
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if buf.value.startswith(prefix):
                r = wt.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(r))
                area = max(0, r.right - r.left) * max(0, r.bottom - r.top)
                result.append((area, hwnd, buf.value))
        return True

    user32.EnumWindows(cb, 0)
    # 取面积最大的(避免抓到同名的幽灵/托盘小窗口)
    result.sort(reverse=True)
    return [(hwnd, title) for _a, hwnd, title in result]


def capture(hwnd, path):
    r = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    user32.SetForegroundWindow(hwnd)
    import time
    time.sleep(0.6)
    hdc = user32.GetWindowDC(hwnd)
    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mem, bmp)
    gdi32.BitBlt(mem, 0, 0, w, h, hdc, 0, 0, SRCCOPY)

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32),
                    ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16),
                    ("biBitCount", ctypes.c_uint16),
                    ("biCompression", ctypes.c_uint32),
                    ("biSizeImage", ctypes.c_uint32),
                    ("biXPelsPerMeter", ctypes.c_int32),
                    ("biYPelsPerMeter", ctypes.c_int32),
                    ("biClrUsed", ctypes.c_uint32),
                    ("biClrImportant", ctypes.c_uint32)]

    bmi = BITMAPINFOHEADER()
    bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.biWidth = w
    bmi.biHeight = -h
    bmi.biPlanes = 1
    bmi.biBitCount = 32
    bmi.biCompression = BI_RGB
    size = w * h * 4
    buf = ctypes.create_string_buffer(size)
    gdi32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bmi), DIB_RGB_COLORS)

    row = w * 4
    header = struct.pack("<2sIHHI", b"BM", 54 + size, 0, 0, 54)
    ihdr = struct.pack("<IiiHHIIiiII", 40, w, -h, 1, 24, 0, w * h * 3, 0, 0, 0, 0)
    out = bytearray(header + ihdr)
    px = buf.raw
    stride3 = (w * 3 + 3) & ~3
    pad = b"\x00" * (stride3 - w * 3)
    for y in range(h):
        rowbytes = bytearray()
        base = y * row
        for x in range(w):
            b_, g_, r_, _a = px[base + x * 4: base + x * 4 + 4]
            rowbytes += bytes((b_, g_, r_))
        out += rowbytes + pad
    with open(path, "wb") as f:
        f.write(out)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem)
    user32.ReleaseDC(hwnd, hdc)
    return w, h


if __name__ == "__main__":
    prefix = sys.argv[1]
    path = sys.argv[2]
    wins = find_window(prefix)
    if not wins:
        print("WINDOW_NOT_FOUND")
        sys.exit(1)
    hwnd, title = wins[0]
    w, h = capture(hwnd, path)
    print(f"SAVED {w}x{h} -> {path} ({title})")
