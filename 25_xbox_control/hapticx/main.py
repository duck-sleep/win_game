"""main.py — HapticX M1 命令行原型:系统音频 → FFT/A2H → XInput 双马达。

用法:
  python main.py                    # 默认均衡模式,持续到 Ctrl+C
  python main.py --mode dynamic     # 动态模式(节拍感强)
  python main.py --probe            # 只跑雷云侦察
  python main.py --list-audio       # 列出输出设备
  python main.py --test-vib 2       # 马达自检 2 秒
"""
import argparse
import sys
import time

from analyzer import A2HAnalyzer, MODES
from audio_capture import LoopbackCapture, list_output_devices
from razer_probe import format_summary, probe_all
from xinput_out import ERROR_DEVICE_NOT_CONNECTED, XInputDevice


def warn_if_synapse_running():
    info = probe_all()
    if info.get("process"):
        print(f"[!] 检测到雷云进程({info['process']})在运行。")
        print("    若振动表现异常(互相打断),请在雷云中关闭 SENSA/动态触觉开关。")
    return info


def do_probe():
    print(format_summary(probe_all()))


def do_list_audio():
    for name, dev_id in list_output_devices():
        mark = "*" if "realtek" in name.lower() else " "
        print(f" {mark} {name}  [{dev_id}]")


def do_test_vib(seconds, user_index):
    dev = XInputDevice(user_index)
    if not dev.available:
        print("[X] 系统未找到 xinput DLL")
        return
    if not dev.is_connected():
        print("[X] XInput 未检测到手柄。请确认手柄处于 Xbox 模式(非 PC/DirectInput 模式)。")
        return
    print(f"[OK] 手柄已连接(user {user_index}),左马达强震测试 {seconds}s ...")
    dev.set_vibration(1.0, 0.0)
    time.sleep(seconds)
    dev.stop()
    print("[OK] 测试完成")


def run_pipeline(args):
    dev = XInputDevice(args.user_index)
    if not dev.available:
        print("[X] 系统未找到 xinput DLL,无法输出振动")
        sys.exit(1)
    if not dev.is_connected():
        print("[X] XInput 未检测到手柄(user index={})。".format(args.user_index))
        print("    Wolverine V3 Pro 请切换到 Xbox 模式(2.4G/有线均可),再试 --test-vib 1")
        sys.exit(1)
    print("[OK] XInput 手柄已连接")

    analyzer = A2HAnalyzer(mode=args.mode, gain=args.gain)
    state = {"blocks": 0, "last_print": 0.0, "peak": 0.0, "beats": 0}
    stats_lock = __import__("threading").Lock()

    def on_block(samples):
        left, right, band, beat = analyzer.process_block(samples)
        ok = dev.set_vibration(left, right)
        with stats_lock:
            state["blocks"] += 1
            state["peak"] = max(state["peak"], left)
            if beat:
                state["beats"] += 1
        if not ok and dev.last_error == ERROR_DEVICE_NOT_CONNECTED:
            dev.stop()
        now = time.time()
        if args.verbose and now - state["last_print"] > 0.1:
            state["last_print"] = now
            bar_l = "#" * int(left * 40)
            bar_r = "#" * int(right * 40)
            print(f"band={band:6.3f} L[{bar_l:<40}] R[{bar_r:<40}] "
                  f"{'BEAT' if beat else '    '}", end="\r", flush=True)

    cap = LoopbackCapture(on_block, device_name=args.device)
    cap.start()
    time.sleep(0.5)
    if cap.last_error:
        print(f"[X] {cap.last_error}")
        cap.stop()
        sys.exit(1)
    print(f"[OK] 环回捕获已启动:{cap.active_device} @48kHz")
    print(f"[*] 模式:{args.mode}  增益:{args.gain}  Ctrl+C 停止\n")

    try:
        end_at = time.time() + args.duration if args.duration else None
        while cap.is_alive():
            time.sleep(0.2)
            if end_at and time.time() > end_at:
                break
    except KeyboardInterrupt:
        pass
    finally:
        cap.stop()
        cap.join(timeout=2)
        dev.stop()
        with stats_lock:
            secs = max(state["blocks"] * 0.02, 0.01)
            print(f"\n\n[统计] 运行 {secs:.1f}s | 峰值输出 {state['peak']:.2f} | "
                  f"节拍脉冲 {state['beats']} 次")
        print("[OK] 已停止振动并退出")


def main():
    parser = argparse.ArgumentParser(description="HapticX — 音频驱动手柄振动(M1 原型)")
    parser.add_argument("--mode", choices=list(MODES), default="balanced")
    parser.add_argument("--gain", type=float, default=0.67)
    parser.add_argument("--duration", type=float, default=0, help="秒,0=一直跑")
    parser.add_argument("--user-index", type=int, default=0)
    parser.add_argument("--device", default=None, help="指定输出设备名(环回源)")
    parser.add_argument("--verbose", action="store_true", help="实时打印能量条")
    parser.add_argument("--probe", action="store_true", help="雷云侦察后退出")
    parser.add_argument("--list-audio", action="store_true")
    parser.add_argument("--test-vib", type=float, metavar="SECONDS", help="马达自检")
    args = parser.parse_args()

    if args.probe:
        do_probe()
        return
    if args.list_audio:
        do_list_audio()
        return
    if args.test_vib is not None:
        do_test_vib(args.test_vib, args.user_index)
        return

    warn_if_synapse_running()
    run_pipeline(args)


if __name__ == "__main__":
    main()
