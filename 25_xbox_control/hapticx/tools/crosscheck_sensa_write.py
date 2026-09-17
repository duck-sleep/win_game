#!/usr/bin/env python3
"""Cross-check SENSA Feature-4 writeback without relying on hand-feel.

1. Idle GetFeature: is another writer (雷云) changing the report?
2. Five rounds: F50 echo, F110 echo, zero echo.
3. Two more STAR replays: last-note codebook must land on G2 (~186-189).
4. USBPcap while writing F50 then STAR; tshark OUT must match sent body[6:].
"""
from __future__ import annotations

import statistics
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import replay_sensa_star as rs

CAP = Path(r"D:\win_game_project\13_win_cap\captures")
USBC = Path(r"C:\Program Files\USBPcap\USBPcapCMD.exe")
TSHARK = Path(r"C:\Program Files\Wireshark\tshark.exe")
ZERO = bytes([4]) + bytes(90)
LOG = CAP / "writeback_crosscheck.log"


def log(msg: str) -> None:
    line = msg
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_mid(name: str) -> bytes:
    rows = []
    with open(CAP / name, encoding="utf-8", errors="replace") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            while len(p) < 6:
                p.append("")
            hx = p[4].strip() or p[5].strip()
            if not hx:
                continue
            t = float(p[1])
            b = bytes.fromhex(hx)
            if t >= 2.0 and len(b) == 91:
                rows.append(b)
    return rows[len(rows) // 2]


def stream(hid, handle, pkt: bytes, seconds: float) -> tuple[int, int]:
    ok = fail = 0
    t0 = time.perf_counter()
    body = bytearray(pkt)
    while time.perf_counter() - t0 < seconds:
        body[2] = (body[2] + 1) & 0xFF
        if rs.set_feature(hid, handle, bytes(body)):
            ok += 1
        else:
            fail += 1
        time.sleep(0.02)
    return ok, fail


def body6(b: bytes) -> bytes:
    return b[6:]


def tshark_out(pcap: Path, txt: Path) -> None:
    filt = "usb.bus_id == 1 and usb.device_address == 18 and usb.endpoint_address.direction == 0"
    cmd = [
        str(TSHARK),
        "-r",
        str(pcap),
        "-Y",
        filt,
        "-T",
        "fields",
        "-e",
        "frame.number",
        "-e",
        "frame.time_relative",
        "-e",
        "usb.transfer_type",
        "-e",
        "usb.endpoint_address",
        "-e",
        "usb.data_fragment",
        "-e",
        "usb.capdata",
    ]
    with txt.open("w", encoding="utf-8") as out:
        subprocess.run(cmd, stdout=out, stderr=subprocess.DEVNULL, check=False)


def start_pcap(path: Path) -> subprocess.Popen:
    if path.exists():
        path.unlink()
    return subprocess.Popen(
        [str(USBC), "-d", r"\\.\USBPcap1", "-A", "--inject-descriptors", "-o", str(path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def stop_pcap(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
    time.sleep(0.5)


def star_bins(rows, t0_shift=1.3, width=0.7):
    bins = defaultdict(list)
    for t, b in rows:
        bins[int((t - t0_shift) / width)].append(b[12])
    return {k: int(statistics.median(v)) for k, v in sorted(bins.items()) if v}


def main() -> None:
    LOG.write_text("", encoding="utf-8")
    f50 = load_mid("F050_A20_sensa_out.txt")
    f110 = load_mid("F110_A20_sensa_out.txt")
    star = rs.load_out_txt(CAP / "STAR_sensa_out.txt")
    orig_bins = star_bins(star)
    log(f"F50 b12={f50[12]} F110 b12={f110[12]} star_n={len(star)}")
    log(f"orig STAR b12 bins {orig_bins}")

    kernel32, hid, handle, path = rs.open_col04()
    log(f"hid {path}")

    idle = []
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 2.0:
        idle.append(rs.get_feature(hid, handle)[12])
        time.sleep(0.1)
    log(f"IDLE n={len(idle)} uniq={sorted(set(idle))} last={idle[-1]}")
    idle_live = len(set(idle)) > 1
    log(f"IDLE_OTHER_WRITER={'YES' if idle_live else 'NO'}")

    echo_ok = 0
    echo_n = 0
    for i in range(5):
        stream(hid, handle, f50, 0.25)
        g50 = rs.get_feature(hid, handle)
        stream(hid, handle, f110, 0.25)
        g110 = rs.get_feature(hid, handle)
        rs.set_feature(hid, handle, ZERO)
        time.sleep(0.04)
        gz = rs.get_feature(hid, handle)
        p50 = g50[12] == f50[12]
        p110 = g110[12] == f110[12]
        pz = gz[12] == 0
        b50 = body6(g50) == body6(f50)
        b110 = body6(g110) == body6(f110)
        echo_n += 3
        echo_ok += int(p50) + int(p110) + int(pz)
        log(
            f"ECHO{i+1} b12 F50 {g50[12]}={'PASS' if p50 else 'FAIL'} "
            f"F110 {g110[12]}={'PASS' if p110 else 'FAIL'} "
            f"zero {gz[12]}={'PASS' if pz else 'FAIL'} "
            f"body6 F50={b50} F110={b110}"
        )
    log(f"ECHO_SCORE {echo_ok}/{echo_n}")

    star_last = []
    for i in range(3):
        ok, fail = rs.replay(star, hid, handle)
        got = rs.get_feature(hid, handle)
        star_last.append(got[12])
        log(f"STAR_REPLAY{i+1} write_ok={ok} fail={fail} last_b12={got[12]} last_b15={got[15]}")
        rs.set_feature(hid, handle, ZERO)
        time.sleep(0.05)
    log(f"STAR_LAST_B12 {star_last} expected~186..190")

    kernel32.CloseHandle(handle)

    # USB: F50 stream
    pcap50 = CAP / "WRITE_F50_cross.pcap"
    proc = start_pcap(pcap50)
    time.sleep(0.8)
    kernel32, hid, handle, _ = rs.open_col04()
    stream(hid, handle, f50, 1.0)
    kernel32.CloseHandle(handle)
    stop_pcap(proc)
    txt50 = CAP / "WRITE_F50_cross_out.txt"
    tshark_out(pcap50, txt50)
    wire50 = rs.load_out_txt(txt50) if txt50.stat().st_size else []
    match50 = sum(1 for _, b in wire50 if body6(b) == body6(f50) or b[12] == f50[12])
    log(f"USB_F50 file={pcap50.stat().st_size if pcap50.exists() else 0} wire91={len(wire50)} b12_or_body_match={match50}")
    if wire50:
        log(f"USB_F50 sample_b12={Counter(b[12] for _,b in wire50).most_common(4)}")

    # USB: STAR replay
    pcap_star = CAP / "WRITE_STAR_cross.pcap"
    proc = start_pcap(pcap_star)
    time.sleep(0.8)
    kernel32, hid, handle, _ = rs.open_col04()
    rs.replay(star, hid, handle)
    rs.set_feature(hid, handle, ZERO)
    kernel32.CloseHandle(handle)
    stop_pcap(proc)
    txt_star = CAP / "WRITE_STAR_cross_out.txt"
    tshark_out(pcap_star, txt_star)
    wire_star = rs.load_out_txt(txt_star) if txt_star.exists() and txt_star.stat().st_size else []
    log(f"USB_STAR file={pcap_star.stat().st_size if pcap_star.exists() else 0} wire91={len(wire_star)} orig={len(star)}")
    if wire_star:
        wb = star_bins(wire_star, t0_shift=wire_star[0][0], width=0.7)
        ob = star_bins(star, t0_shift=star[0][0], width=0.7)
        log(f"USB_STAR bins {wb}")
        log(f"ORIG_STAR bins_from_t0 {ob}")
        # pair by index: how many wire packets have same b12 as orig at same sequence position
        n = min(len(wire_star), len(star))
        same12 = sum(1 for i in range(n) if wire_star[i][1][12] == star[i][1][12])
        same6 = sum(1 for i in range(n) if body6(wire_star[i][1]) == body6(star[i][1]))
        log(f"USB_STAR aligned n={n} same_b12={same12}/{n} same_body6={same6}/{n}")

    log("DONE")


if __name__ == "__main__":
    main()
