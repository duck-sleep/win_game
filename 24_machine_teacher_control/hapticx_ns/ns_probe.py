"""ns_probe.py — 机械师 G6 V2（NS 模式）的设备情报，接口和 25 的 razer_probe 一样：
`probe_all() -> dict`、`format_summary(dict) -> str`，这样 app.py 那页几乎不用改。

和雷蛇那版最大的区别：这里不读雷云日志，只看 HID 枚举结果 + 有没有软件在抢手柄。
"""

from __future__ import annotations

import subprocess
import time

NS_VID, NS_PID = 0x057E, 0x2009

# 会抢 Pro 手柄的常见软件（抢了就会出现"发进去没反应"或握手失败）
GRABBERS = {
    "steam.exe": "Steam（Steam Input 会接管 Switch Pro 手柄并自己发握手/振动）",
    "steamwebhelper.exe": "Steam",
    "ds4windows.exe": "DS4Windows",
    "betterjoy.exe": "BetterJoy",
    "ryujinx.exe": "Ryujinx",
    "yuzu.exe": "yuzu",
    "cemu.exe": "Cemu",
}


def _enumerate() -> list[dict]:
    try:
        import hid
        return hid.enumerate()
    except Exception as e:                                    # noqa: BLE001
        return [{"_error": repr(e)}]


def scan_device() -> dict:
    devs = [d for d in _enumerate() if d.get("vendor_id") == NS_VID and d.get("product_id") == NS_PID]
    if not devs:
        return {"found": False}
    d = devs[0]
    return {
        "found": True,
        "productName": (d.get("product_string") or "Pro Controller").strip(),
        "vendorId": f"{d.get('vendor_id', 0):04X}",
        "productIdHex": f"{d.get('product_id', 0):04X}",
        "serialNumber": (d.get("serial_number") or "").strip(),
        "usage": f"usage_page 0x{d.get('usage_page', 0):04X} / usage 0x{d.get('usage', 0):04X}",
        "interface": d.get("interface_number"),
        "path": (d.get("path") or b"").decode("utf-8", "replace"),
        "siblings": sorted({f"{x.get('vendor_id', 0):04X}:{x.get('product_id', 0):04X}"
                           for x in _enumerate() if x.get("vendor_id")}),
    }


def detect_grabber() -> str | None:
    try:
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True,
                             text=True, timeout=5).stdout.lower()
    except Exception:                                        # noqa: BLE001
        return None
    for exe, desc in GRABBERS.items():
        if exe in out:
            return desc
    return None


def probe_all() -> dict:
    return {
        "device": scan_device(),
        "process": detect_grabber(),
        "protocol": "任天堂 Pro Controller（USB 输出报告 0x10，每只手高频+低频振荡器）",
        "at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def format_summary(info: dict) -> str:
    dev = info.get("device") or {}
    lines: list[str] = []
    if dev.get("found"):
        lines.append(f"手柄       : {dev['productName']}  (VID {dev['vendorId']} / PID {dev['productIdHex']})")
        lines.append(f"序列号     : {dev.get('serialNumber') or '(无)'}")
        lines.append(f"HID 分类   : {dev.get('usage')}  interface {dev.get('interface')}")
        lines.append(f"协议       : {info.get('protocol')}")
        lines.append("状态       : ✅ 在，可以开震")
    else:
        lines.append("手柄       : ❌ 没找到 057E:2009")
        lines.append("")
        lines.append("按这个顺序查：")
        lines.append("  1) 手柄切到 NS 模式了吗（G6 V2 顶部有个模式开关/组合键）")
        lines.append("  2) USB 线插的是这台电脑吗（蓝牙/2.4G 接收器这条路本程序不管）")
        lines.append("  3) 有没有 Steam / BetterJoy / DS4Windows 在抢（下面会列出来）")
        lines.append("  4) 换个 USB 口试试；换完重开本程序")
        if dev.get("_error"):
            lines.append(f"  hidapi 报错：{dev['_error']}")
    sib = dev.get("siblings")
    if sib:
        lines.append(f"本机其它 HID：{'、'.join(sib[:8])}{'…' if len(sib) > 8 else ''}")
    proc = info.get("process")
    lines.append("")
    lines.append(f"抢手柄的软件：{proc if proc else '没检测到（很好）'}")
    lines.append(f"探测时间     : {info.get('at')}")
    return "\n".join(lines) + "\n"
