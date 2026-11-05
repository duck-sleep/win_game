r"""振动手感测试：点一下，它自己念题，你慢慢摸，不用守着。

  双击上级目录「测试振动.bat」，或者：
  python tools\rumble_test.py            菜单
  python tools\rumble_test.py --all      直接四组全跑（频率→左右→强弱→持续）
  python tools\rumble_test.py --selftest 只做握手 + 0.3 秒一下，验证代码通路（模型用）

每段前 2 秒倒计时并打印要发哪 4 个字节；过程写进 tools\rumble_test.out.txt，
跑完把那句「回答我三句话」照着摸出来的感觉答一下就行。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))      # 工程根

from ns_rumble.codec import NEUTRAL, encode_side                     # noqa: E402
from ns_rumble.device import NSController                            # noqa: E402

LOG = Path(__file__).with_name("rumble_test.out.txt")
LF_HZ_MAX = 626.0
SEND_MS = 20.0
COUNTDOWN = 2.0
GAP = 2.0

_lines: list[str] = []


def say(msg: str = "") -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}" if msg else ""
    print(line, flush=True)
    _lines.append(line)


def side(hz: float, amp: float) -> bytes:
    lf_amp = 0.0 if hz > LF_HZ_MAX else amp
    return encode_side(hz, amp, hz, lf_amp)


def hold(ns: NSController, left: bytes, right: bytes, seconds: float) -> None:
    t0 = time.monotonic()
    while time.monotonic() - t0 < seconds:
        ns.send(left, right)
        time.sleep(SEND_MS / 1000.0)


def segment(ns: NSController, label: str, left: bytes, right: bytes, seconds: float) -> None:
    say(f"下一段：{label}  ——  {seconds:g} 秒，{COUNTDOWN:g} 秒后开始")
    say(f"        左={left.hex(' ')}  右={right.hex(' ')}")
    hold(ns, NEUTRAL, NEUTRAL, COUNTDOWN)
    hold(ns, left, right, seconds)
    hold(ns, NEUTRAL, NEUTRAL, GAP)


def test_freq(ns: NSController) -> None:
    say("\n===== 第 1 组：频率（工单 N1 的闸门题）=====")
    say("三段音高：160 低沉 → 320 中 → 640 尖。跑两遍，好比较。")
    for rnd in (1, 2):
        for hz in (160.0, 320.0, 640.0):
            b = side(hz, 0.5)
            segment(ns, f"第 {rnd} 遍 · {hz:g} Hz 双手", b, b, 3.0)


def test_lr(ns: NSController) -> None:
    say("\n===== 第 2 组：左右（N3 第 1 条）=====")
    b = side(320.0, 0.5)
    segment(ns, "只有左手", b, NEUTRAL, 3.0)
    segment(ns, "只有右手", NEUTRAL, b, 3.0)
    segment(ns, "两只手", b, b, 3.0)


def hf_only(hz: float, amp: float) -> bytes:
    return encode_side(hz, amp, 160.0, 0.0)


def lf_only(hz: float, amp: float) -> bytes:
    return encode_side(1000.0, 0.0, hz, amp)


def test_lr_matrix(ns: NSController) -> None:
    """单侧不震的隔离矩阵：把「哪一侧」和「哪个振荡器」两个变量拆开，再加一条混音判据。"""
    say("\n===== 左右隔离矩阵（查「单侧不震」）=====")
    say("请逐段记：震 / 不震 / 弱。最后一段 H 最关键 —— 听得出几个音？")
    full = side(320.0, 0.5)
    segment(ns, "A 左=320全 右=静止", full, NEUTRAL, 3.0)
    segment(ns, "B 左=静止 右=320全", NEUTRAL, full, 3.0)
    segment(ns, "C 左=320全 右=320全（对照，应该震）", full, full, 3.0)
    segment(ns, "D 左=只开高频 右=静止", hf_only(320.0, 0.5), NEUTRAL, 3.0)
    segment(ns, "E 左=只开低频 右=静止", lf_only(160.0, 0.5), NEUTRAL, 3.0)
    segment(ns, "F 左=静止 右=只开高频", NEUTRAL, hf_only(320.0, 0.5), 3.0)
    segment(ns, "G 左=静止 右=只开低频", NEUTRAL, lf_only(160.0, 0.5), 3.0)
    segment(ns, "H 左=200 Hz 右=500 Hz（听得出两个音吗）",
            side(200.0, 0.5), side(500.0, 0.5), 4.0)


def test_amp(ns: NSController) -> None:
    say("\n===== 第 3 组：强弱（N3 第 3 条）=====")
    for amp in (0.2, 0.5, 0.8):
        b = side(320.0, amp)
        segment(ns, f"320 Hz 振幅 {amp}", b, b, 3.0)


def test_hold(ns: NSController) -> None:
    say("\n===== 第 4 组：持续会不会中途停（N3 第 2 条，发包间隔 20 ms）=====")
    b = side(320.0, 0.5)
    segment(ns, "320 Hz 连续 8 秒", b, b, 8.0)


ALL_GROUPS = [("1", "频率", test_freq), ("2", "左右", test_lr),
              ("3", "强弱", test_amp), ("4", "持续", test_hold)]
GROUPS = ALL_GROUPS + [("6", "左右隔离矩阵（查「单侧不震」）", test_lr_matrix)]


def run_all(ns: NSController) -> None:
    for _, _, fn in ALL_GROUPS:
        fn(ns)


def main() -> int:
    args = sys.argv[1:]

    ns = NSController()
    try:
        ns.open()
    except Exception as e:                                    # noqa: BLE001
        say(f"❌ 打不开手柄：{e!r}")
        say("   → 检查：手柄在不在 NS 模式、USB 插没插、Steam/BetterJoy/DS4Windows 有没有开。")
        LOG.write_text("\r\n".join(_lines) + "\r\n", encoding="utf-8")
        return 1

    try:
        ns.init_usb()
        ns.enable_vibration()
        say("握手 + 开振动成功，可以拿在手上了。")

        if "--selftest" in args:
            b = side(160.0, 0.5)
            say(f"自检：只震 0.3 秒，字节 {b.hex(' ')}")
            hold(ns, b, b, 0.3)
            return 0

        if "--lr-matrix" in args:
            test_lr_matrix(ns)
            return 0

        if "--all" in args:
            choice = "5"
        else:
            print("\n选一组（输入数字回车）：")
            for key, name, _ in GROUPS:
                print(f"  {key}  {name}")
            print("  5  前四组按顺序全跑一遍（约 2 分钟）")
            print("  直接回车 = 5")
            choice = input("> ").strip() or "5"
            if choice == "5":
                pass
            else:
                hit = [fn for key, _, fn in GROUPS if key == choice]
                if not hit:
                    say("没这个选项，那就全跑一遍。")
                    choice = "5"
                else:
                    hit[0](ns)

        if choice == "5":
            run_all(ns)

        say("\n===== 跑完了。回答我三句话 =====")
        say("① 第 1 组那三段（160 / 320 / 640）：听得出/摸得出明显不同吗？（这是闸门题）")
        say("② 第 2 组：「只有左手」和「只有右手」分得清吗？左右有没有反？")
        say("③ 第 3 组强弱、第 4 组连续 8 秒：强弱分得出吗？8 秒中间有没有断？")
        return 0
    except KeyboardInterrupt:
        say("（你按了 Ctrl+C，停了）")
        return 130
    finally:
        ns.close()
        LOG.write_text("\r\n".join(_lines) + "\r\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
