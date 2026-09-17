#!/usr/bin/env python3
"""Replay captured SENSA Feature report ID 4 onto Wolverine 0a4c MI_01 COL04.

Does not use XInput. Turn 雷云 SENSA / HapticX off first so they do not overwrite.
Default: STAR_sensa_out.txt at captured timestamps, then a zero report.
"""
from __future__ import annotations

import argparse
import ctypes
import time
from ctypes import wintypes
from pathlib import Path

CAP_DEFAULT = Path(r"D:\win_game_project\13_win_cap\captures")
VID = "vid_1532"
PID = "pid_0a4c"
COL = "col04"

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
OPEN_EXISTING = 3
DIGCF_PRESENT = 2
DIGCF_DEVICEINTERFACE = 0x10
INVALID = ctypes.c_void_p(-1).value


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("InterfaceClassGuid", GUID),
        ("Flags", wintypes.DWORD),
        ("Reserved", ctypes.POINTER(ctypes.c_ulong)),
    ]


class DETAIL(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("DevicePath", ctypes.c_wchar * 512)]


def _dlls():
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
    hid = ctypes.WinDLL("hid", use_last_error=True)
    hid.HidD_GetHidGuid.argtypes = [ctypes.POINTER(GUID)]
    setupapi.SetupDiGetClassDevsW.restype = wintypes.HANDLE
    setupapi.SetupDiEnumDeviceInterfaces.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        ctypes.POINTER(GUID),
        wintypes.DWORD,
        ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
    ]
    setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    ]
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    hid.HidD_SetFeature.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.ULONG]
    hid.HidD_GetFeature.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.ULONG]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    return kernel32, setupapi, hid


def open_col04():
    kernel32, setupapi, hid = _dlls()
    guid = GUID()
    hid.HidD_GetHidGuid(ctypes.byref(guid))
    hdev = setupapi.SetupDiGetClassDevsW(
        ctypes.byref(guid), None, None, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE
    )
    i = 0
    path = None
    while True:
        did = SP_DEVICE_INTERFACE_DATA()
        did.cbSize = ctypes.sizeof(did)
        if not setupapi.SetupDiEnumDeviceInterfaces(
            hdev, None, ctypes.byref(guid), i, ctypes.byref(did)
        ):
            break
        i += 1
        needed = wintypes.DWORD()
        setupapi.SetupDiGetDeviceInterfaceDetailW(
            hdev, ctypes.byref(did), None, 0, ctypes.byref(needed), None
        )
        detail = DETAIL()
        detail.cbSize = 8
        if not setupapi.SetupDiGetDeviceInterfaceDetailW(
            hdev, ctypes.byref(did), ctypes.byref(detail), needed.value, None, None
        ):
            continue
        p = detail.DevicePath
        if VID in p.lower() and PID in p.lower() and COL in p.lower():
            path = p
            break
    if not path:
        raise SystemExit("COL04 HID path not found for 1532:0a4c")
    handle = kernel32.CreateFileW(
        path,
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        0,
        None,
    )
    if handle == INVALID:
        raise SystemExit(f"CreateFile failed err={ctypes.get_last_error()} path={path}")
    return kernel32, hid, handle, path


def load_out_txt(path: Path):
    rows = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            while len(parts) < 6:
                parts.append("")
            hx = parts[4].strip() or parts[5].strip()
            if not hx:
                continue
            blob = bytes.fromhex(hx)
            if len(blob) == 91 and blob[0] == 4:
                rows.append((float(parts[1]), blob))
    if not rows:
        raise SystemExit(f"no 91-byte report-id-4 payloads in {path}")
    return rows


def set_feature(hid, handle, payload: bytes) -> bool:
    buf = (ctypes.c_ubyte * 91)(*payload)
    return bool(hid.HidD_SetFeature(handle, buf, 91))


def get_feature(hid, handle) -> bytes:
    buf = (ctypes.c_ubyte * 91)()
    buf[0] = 4
    hid.HidD_GetFeature(handle, buf, 91)
    return bytes(buf)


def replay(rows, hid, handle) -> tuple[int, int]:
    ok = fail = 0
    t_wall = time.perf_counter()
    t0 = rows[0][0]
    for t, blob in rows:
        target = t_wall + (t - t0)
        now = time.perf_counter()
        if target > now:
            time.sleep(target - now)
        if set_feature(hid, handle, blob):
            ok += 1
        else:
            fail += 1
    return ok, fail


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--src",
        default=str(CAP_DEFAULT / "STAR_sensa_out.txt"),
        help="tshark OUT txt with 91-byte SENSA payloads",
    )
    parser.add_argument("--no-zero", action="store_true")
    args = parser.parse_args()
    rows = load_out_txt(Path(args.src))
    kernel32, hid, handle, path = open_col04()
    print(f"path={path}")
    print(f"packets={len(rows)} dur={rows[-1][0] - rows[0][0]:.3f}s")
    before = get_feature(hid, handle)
    print(f"before b12={before[12]} b15={before[15]}")
    ok, fail = replay(rows, hid, handle)
    after = get_feature(hid, handle)
    print(f"replay ok={ok} fail={fail} after b12={after[12]} b15={after[15]}")
    if not args.no_zero:
        set_feature(hid, handle, bytes([4]) + bytes(90))
        time.sleep(0.05)
        z = get_feature(hid, handle)
        print(f"zero b12={z[12]}")
    kernel32.CloseHandle(handle)


if __name__ == "__main__":
    main()
