#!/usr/bin/env python3
"""Synthesize a held SENSA Feature-4 tone from one captured seed frame.

Observed on unique frames (~100ms): copy1 bytes
  b11 += 4, b13 += 32, b14 += 1, b16 += 8
copy2 (offset 24) is copy1 shifted right 4 bits with a high nibble prefix
  prefix = seed[24] & 0xF0  (0x90 at 50Hz / C2; 0xA0 at 80Hz+)
Each unique frame is repeated `repeat` times at 20ms (USB refresh).
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import replay_sensa_star as rs

CAP = Path(r"D:\win_game_project\13_win_cap\captures")


def load_seed(name: str, tmin: float = 2.0) -> bytes:
    rows = rs.load_out_txt(CAP / name)
    body = [b for t, b in rows if t >= tmin]
    return body[len(body) // 2]


def copy2_from_copy1(copy1: bytes, prefix_hi: int) -> bytes:
    n = len(copy1)
    acc = int.from_bytes(copy1, "big") >> 4
    shifted = acc.to_bytes(n, "big")
    out = bytearray(shifted)
    out[0] = (prefix_hi & 0xF0) | (copy1[0] >> 4)
    return bytes(out)


def step_copy1(copy1: bytearray) -> None:
    copy1[0] = (copy1[0] + 4) & 0xFF  # b11
    copy1[2] = (copy1[2] + 32) & 0xFF  # b13
    copy1[3] = (copy1[3] + 1) & 0xFF  # b14
    copy1[5] = (copy1[5] + 8) & 0xFF  # b16


def synthesize(seed: bytes, n_unique: int, repeat: int = 5) -> list[bytes]:
    pkt = bytearray(seed)
    copy1 = bytearray(pkt[11:24])
    prefix_hi = pkt[24] & 0xF0
    out: list[bytes] = []
    ctr = pkt[2]
    for _ in range(n_unique):
        pkt[11:24] = copy1
        c2 = copy2_from_copy1(bytes(copy1), prefix_hi)
        pkt[24 : 24 + len(c2)] = c2
        for _r in range(repeat):
            pkt[2] = ctr & 0xFF
            ctr = (ctr + 1) & 0xFF
            out.append(bytes(pkt))
        step_copy1(copy1)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", default="F050_A20_sensa_out.txt")
    ap.add_argument("--unique", type=int, default=8)
    ap.add_argument("--repeat", type=int, default=5)
    ap.add_argument("--patch-b12", type=int, default=None, help="overwrite pitch b12 on seed")
    ap.add_argument("--patch-b15", type=int, default=None, help="overwrite pitch b15 on seed")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    seed = bytearray(load_seed(args.seed))
    if args.patch_b12 is not None:
        seed[12] = args.patch_b12 & 0xFF
    if args.patch_b15 is not None:
        seed[15] = args.patch_b15 & 0xFF
    seed = bytes(seed)
    frames = synthesize(seed, args.unique, args.repeat)
    print(f"seed b12={seed[12]} b15={seed[15]} prefix={seed[24] & 0xF0:02x}")
    print(f"frames={len(frames)} unique={args.unique} repeat={args.repeat}")
    print("u0", frames[0][11:37].hex())
    print("u1", frames[args.repeat][11:37].hex())
    if args.dry_run:
        return
    kernel32, hid, handle, path = rs.open_col04()
    print("path", path)
    ok = fail = 0
    t0 = time.perf_counter()
    for blob in frames:
        if rs.set_feature(hid, handle, blob):
            ok += 1
        else:
            fail += 1
        # paced like capture (~20ms)
        target = t0 + (ok + fail) * 0.02
        now = time.perf_counter()
        if target > now:
            time.sleep(target - now)
    got = rs.get_feature(hid, handle)
    print(f"write ok={ok} fail={fail} get b12={got[12]} b15={got[15]}")
    rs.set_feature(hid, handle, bytes([4]) + bytes(90))
    kernel32.CloseHandle(handle)


if __name__ == "__main__":
    main()
