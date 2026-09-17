#!/usr/bin/env python3
"""W3A.2 — 固定力度 0.5，三档 pitch 0.1 / 0.5 / 0.9，走官方 Interhaptics API。

不放 wav。调用 HAR.AddParametricEffect + Sensa/GameInput Provider。
freqMin/freqMax = 30/80（W0.3 A2H output_frequency_range）。
"""
from __future__ import annotations

import ctypes
import os
import sys
import time
from ctypes import POINTER, c_bool, c_char_p, c_double, c_int, c_void_p

ROOT = os.path.dirname(os.path.abspath(__file__))
SDK = os.path.join(ROOT, "InterhapticsEngine_CoreSDK")
HAR_DIR = os.path.join(SDK, "bin", "HapticEngine", "x64")
SENSA_DIR = os.path.join(SDK, "bin", "HapticProviders", "Sensa", "x64")
GI_DIR = os.path.join(SDK, "bin", "HapticProviders", "GameInput")
RAZER_COMMON = os.path.join(
    os.environ.get("LOCALAPPDATA", ""),
    "Razer", "RazerAppEngine", "User Data", "Apps", "Common",
)

FREQ_MIN = 30.0
FREQ_MAX = 80.0
AMP = 0.5
DURATION_S = 2.0
GAP_S = 1.0
PITCHES = (0.1, 0.5, 0.9)
RENDER_HZ = 100

# SharedTypes.h CommandData: Operator, GroupID, LateralFlag (three ints)
OP_PLUS = 1
GROUP_PALM = 400
LATERAL_GLOBAL = 0


class CommandData(ctypes.Structure):
    _fields_ = [
        ("Sign", c_int),
        ("Group", c_int),
        ("Side", c_int),
    ]


def log(msg):
    print(msg, flush=True)


def add_dirs():
    for d in (HAR_DIR, SENSA_DIR, GI_DIR, RAZER_COMMON):
        if d and os.path.isdir(d):
            os.add_dll_directory(d)
            log(f"dll_dir {d}")
        else:
            log(f"dll_dir MISSING {d}")


def load_har():
    path = os.path.join(HAR_DIR, "HAR.dll")
    log(f"LoadLibrary {path} exists={os.path.isfile(path)}")
    har = ctypes.CDLL(path)
    har.Init.restype = c_bool
    har.Quit.restype = None
    har.AddParametricEffect.argtypes = [
        POINTER(c_double), c_int,
        POINTER(c_double), c_int,
        c_double, c_double,
        POINTER(c_double), c_int,
        c_bool,
    ]
    har.AddParametricEffect.restype = c_int
    har.DeleteHM.argtypes = [c_int]
    har.DeleteHM.restype = c_bool
    har.PlayEvent.argtypes = [c_int, c_double, c_double, c_double]
    har.PlayEvent.restype = None
    har.StopEvent.argtypes = [c_int]
    har.StopEvent.restype = None
    har.AddTargetToEventMarshal.argtypes = [c_int, POINTER(CommandData), c_int]
    har.AddTargetToEventMarshal.restype = None
    har.ComputeAllEvents.argtypes = [c_double]
    har.ComputeAllEvents.restype = None
    har.GetConnectedDeviceCount.restype = c_int
    har.GetGlobalIntensity.restype = c_double
    har.SetGlobalIntensity.argtypes = [c_double]
    har.SetGlobalIntensity.restype = None
    return har


def load_provider(dll_path):
    log(f"LoadLibrary {dll_path} exists={os.path.isfile(dll_path)}")
    p = ctypes.CDLL(dll_path)
    p.ProviderInit.restype = c_bool
    p.ProviderIsPresent.restype = c_bool
    p.ProviderRenderHaptics.restype = None
    p.ProviderClean.restype = None
    if hasattr(p, "ProviderSetApplicationName"):
        p.ProviderSetApplicationName.argtypes = [c_char_p]
        p.ProviderSetApplicationName.restype = None
    return p


def kv_pairs(*vals):
    arr = (c_double * len(vals))(*vals)
    return arr, len(vals)


def play_one(har, providers, pitch, t0):
    amp, amp_n = kv_pairs(0.0, AMP, DURATION_S, AMP)
    pit, pit_n = kv_pairs(0.0, pitch, DURATION_S, pitch)
    hid = har.AddParametricEffect(
        amp, amp_n, pit, pit_n, FREQ_MIN, FREQ_MAX, None, 0, False,
    )
    log(f"  AddParametricEffect pitch={pitch} -> id={hid}")
    if hid < 0:
        return hid
    target = CommandData(OP_PLUS, GROUP_PALM, LATERAL_GLOBAL)
    har.AddTargetToEventMarshal(hid, ctypes.byref(target), 1)
    har.PlayEvent(hid, 0.0, 0.0, 0.0)
    deadline = time.perf_counter() + DURATION_S
    while time.perf_counter() < deadline:
        har.ComputeAllEvents(time.perf_counter() - t0)
        for p in providers:
            p.ProviderRenderHaptics()
        time.sleep(1.0 / RENDER_HZ)
    har.StopEvent(hid)
    har.DeleteHM(hid)
    return hid


def main():
    log("=== W3A.2 official pitch probe ===")
    log(f"API=HAR.AddParametricEffect  amp={AMP}  freqMin={FREQ_MIN}  freqMax={FREQ_MAX}")
    log(f"pitches={PITCHES}  duration={DURATION_S}s  gap={GAP_S}s")
    log(f"SDK={SDK}")
    add_dirs()

    har = load_har()
    ok_init = bool(har.Init())
    log(f"HAR.Init -> {ok_init}")
    har.SetGlobalIntensity(1.0)
    log(f"HAR.GetGlobalIntensity -> {har.GetGlobalIntensity()}")

    providers = []
    sensa = load_provider(os.path.join(SENSA_DIR, "Interhaptics.RazerProvider.dll"))
    if hasattr(sensa, "ProviderSetApplicationName"):
        try:
            sensa.ProviderSetApplicationName(b"HapticX-pitch-probe")
            log("Sensa.ProviderSetApplicationName ok")
        except Exception as exc:  # noqa: BLE001
            log(f"Sensa.ProviderSetApplicationName error: {exc!r}")
    try:
        s_init = bool(sensa.ProviderInit())
    except Exception as exc:  # noqa: BLE001
        s_init = False
        log(f"Sensa.ProviderInit exception: {exc!r}")
    s_present = bool(sensa.ProviderIsPresent()) if s_init else False
    log(f"Sensa.ProviderInit -> {s_init}  ProviderIsPresent -> {s_present}")
    if s_init:
        providers.append(sensa)

    gi = load_provider(os.path.join(GI_DIR, "Interhaptics.GameInputProvider.dll"))
    try:
        g_init = bool(gi.ProviderInit())
    except Exception as exc:  # noqa: BLE001
        g_init = False
        log(f"GameInput.ProviderInit exception: {exc!r}")
    g_present = bool(gi.ProviderIsPresent()) if g_init else False
    log(f"GameInput.ProviderInit -> {g_init}  ProviderIsPresent -> {g_present}")
    if g_init:
        providers.append(gi)

    n_dev = har.GetConnectedDeviceCount()
    log(f"HAR.GetConnectedDeviceCount -> {n_dev}")

    if not providers:
        log("FAIL: no provider initialized")
        har.Quit()
        return 1

    t0 = time.perf_counter()
    ids = []
    for i, pitch in enumerate(PITCHES):
        log(f"-- clip {i + 1}/3 pitch={pitch}")
        ids.append(play_one(har, providers, pitch, t0))
        if i < len(PITCHES) - 1:
            gap_end = time.perf_counter() + GAP_S
            while time.perf_counter() < gap_end:
                har.ComputeAllEvents(time.perf_counter() - t0)
                for p in providers:
                    p.ProviderRenderHaptics()
                time.sleep(1.0 / RENDER_HZ)

    log(f"effect ids={ids}")
    for p in providers:
        try:
            p.ProviderClean()
        except Exception as exc:  # noqa: BLE001
            log(f"ProviderClean error: {exc!r}")
    har.Quit()
    if any(i < 0 for i in ids):
        log("FAIL: AddParametricEffect returned -1")
        return 1
    log("PROBE_CALLS_OK (API accepted; motor Hz still unverified without sensor/USB)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except OSError as exc:
        log(f"OSError: {exc}")
        sys.exit(2)
    except Exception as exc:  # noqa: BLE001
        log(f"UNCAUGHT: {type(exc).__name__}: {exc}")
        sys.exit(3)
