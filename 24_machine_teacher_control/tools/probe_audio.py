r"""听音频探针：只回答一个问题 —— **电脑正在放的声音，环回抓不抓得到**。

不碰手柄、不发任何声音。你自己在它跑的这几秒里放点音乐。

  用法：双击上级目录的「听音频探针.bat」，或
  python tools\probe_audio.py [秒数]

跑完把过程写进同目录 probe_audio.out.txt —— 模型直接读那个文件，不用你抄屏幕。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))      # 工程根

from ns_rumble.vendor.wasapi_loopback import WasapiLoopback          # noqa: E402

LOG = Path(__file__).with_name("probe_audio.out.txt")
_lines: list[str] = []


def say(msg: str = "") -> None:
    print(msg)
    _lines.append(msg)


def main() -> int:
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 8.0

    cap = WasapiLoopback()
    try:
        cap.open()
    except Exception as e:                                    # noqa: BLE001
        say(f"❌ 环回打不开：{e!r}")
        say("   → 这本身就是结论：音频采集这条路不通，先查默认播放设备/独占模式。")
        LOG.write_text("\r\n".join(_lines) + "\r\n", encoding="utf-8")
        return 1

    say(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 抓的是默认播放设备：{cap.endpoint_id}")
    say(f"  {cap.sample_rate} Hz  {cap.n_channels} 声道  {cap._bits} bit  "
        f"每块 {cap.period_ms} ms")
    say(f">>> 现在开始放音乐（浏览器、播放器都行，音量开到平时听歌的大小），"
        f"我录 {seconds:g} 秒 <<<")

    t0 = time.monotonic()
    blocks = 0
    empty = 0
    peak_all = 0.0
    while time.monotonic() - t0 < seconds:
        blk = cap.read_block()
        blocks += 1
        if blk is None or blk.size == 0:
            empty += 1
            continue
        peak = float(np.max(np.abs(blk)))
        peak_all = max(peak_all, peak)
        if blocks % 5 == 0:                                   # 每 100 ms 打一行
            say(f"{time.monotonic() - t0:5.2f}s  峰值 {peak:.4f}  {'#' * min(50, int(peak * 50))}")

    cap.close()

    say(f"采到 {blocks} 块（空块 {empty}），全程最大峰值 {peak_all:.4f}")
    if blocks == 0:
        say("❌ 一块都没回来 → 环回没跑起来。")
    elif peak_all < 0.001:
        say("⚠️ 块按时回来了但全程没信号。两种可能：")
        say("   ① 你这几秒确实没放声音（最常见）→ 再跑一次，边跑边放；")
        say("   ② 声音出在**另一个设备**上（耳机/外接/浏览器选了别的输出），"
            "而这里抓的是系统默认播放设备 → 把播放设备和默认设备对齐再试。")
    elif peak_all < 0.05:
        say("🟡 有信号但很弱 → 通是通了，音量偏小；唱歌那条线增益会不够，先把音量调大。")
    else:
        say("✅ 音频这条路是通的：环回能抓到、也有实信号。"
            "接下来该判的是手柄那三段振动（工单 N1），不是音频。")

    LOG.write_text("\r\n".join(_lines) + "\r\n", encoding="utf-8")
    print(f"（过程已写到 {LOG}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
