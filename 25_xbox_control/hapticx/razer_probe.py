"""razer_probe.py — M0 雷云侦察:从雷云4日志中提取手柄型号与 A2H 触觉参数。

情报源(已在本机验证):
  %LOCALAPPDATA%\\Razer\\RazerAppEngine\\User Data\\Logs\\
    products_2636_*.log   → 设备型号 / VID / PID / 序列号
    RzAudioCapture.log    → A2H 配方:频段、EQ、瞬态、压缩器、马达特性、编码器DLL
    sensa.log / chroma-app_sensa-hd.log → SENSA 模块状态
"""
import glob
import json
import os
import re

LOG_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", ""), "Razer", "RazerAppEngine",
    "User Data", "Logs")

RAZER_PROC_NAMES = ("RazerAppEngine", "RazerSynapse", "RazerService",
                    "razer_elevation_service", "RazerExperienceService")


def find_logs():
    if not os.path.isdir(LOG_DIR):
        return []
    return glob.glob(os.path.join(LOG_DIR, "*.log"))


def _read_tail(path, max_bytes=2_000_000):
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        if size > max_bytes:
            f.seek(size - max_bytes)
        return f.read(max_bytes).decode("utf-8", errors="replace")


def detect_process():
    try:
        import psutil
    except ImportError:
        return None
    for p in psutil.process_iter(["name"]):
        name = (p.info["name"] or "").lower()
        if any(r.lower() in name for r in RAZER_PROC_NAMES):
            return p.info["name"]
    return None


def scan_device():
    """从 products_*.log 提取设备信息(VID/PID/型号/序列号)。"""
    dev = {}
    for path in find_logs():
        if not re.search(r"products_\d+", os.path.basename(path)):
            continue
        text = _read_tail(path)
        m = re.search(
            r'getRazerDevices.*?\[(\{.*?"productName":"([^"]+)".*?"productId":(\d+).*?"vendorId":(\d+).*?\})',
            text)
        if m:
            dev.update({
                "productName": m.group(2),
                "productId": m.group(3),
                "productIdHex": format(int(m.group(3)), "04X"),
                "vendorId": m.group(4),
                "sourceLog": os.path.basename(path),
            })
            break
        m = re.search(r'productName:\s*([^,]+),', text)
        if m and not dev.get("productName"):
            dev["productName"] = m.group(1).strip()
    for path in find_logs():
        text = _read_tail(path)
        m = re.search(r'serialNumber["\s:]+([0-9A-F]{14,16})', text)
        if m:
            dev["serialNumber"] = m.group(1)
            break
    return dev


def scan_a2h_profile():
    """从 RzAudioCapture.log 提取雷云 A2H(音效转触觉)配方。"""
    out = {}
    for path in find_logs():
        if "RzAudioCapture" not in os.path.basename(path):
            continue
        text = _read_tail(path)
        m = re.search(r'"profile":"(\{.*?\})","encoderDLLPath"', text)
        if m:
            raw = m.group(1).replace('\\"', '"')
            try:
                out["profile"] = json.loads(raw)
            except json.JSONDecodeError:
                out["profileRaw"] = raw
        m = re.search(r'"report":"(\{.*?\})","profile"', text)
        if m:
            raw = m.group(1).replace('\\"', '"')
            try:
                out["deviceReport"] = json.loads(raw)
            except json.JSONDecodeError:
                pass
        m = re.search(r'"encoderDLLPath":"([^"]+)"', text)
        if m:
            out["encoderDLL"] = m.group(1).replace("\\\\", "\\")
        m = re.search(r"AcquireAV config: (\{.*?\})", text)
        if m:
            try:
                out["avConfig"] = json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        m = re.findall(r"SetHapticMixerGain source=(\d+) gain=(\d+)", text)
        if m:
            out["mixerGains"] = {f"source_{s}": int(g) for s, g in m}
    return out


def scan_sensa():
    """SENSA 模块在日志中的活跃痕迹。"""
    out = {}
    for path in find_logs():
        base = os.path.basename(path)
        if base == "sensa.log":
            out["sensaLogExists"] = True
        if "sensa-hd" in base:
            text = _read_tail(path, 200_000)
            m = re.findall(r'"audioToHapticsProfile":"(\w+)"', text)
            if m:
                out["audioToHapticsProfiles"] = sorted(set(m))
            if "getHapticGameProfiles" in text:
                out["sensaHdActive"] = True
    return out


def probe_all():
    result = {
        "logDir": LOG_DIR,
        "logDirExists": os.path.isdir(LOG_DIR),
        "process": detect_process(),
        "device": scan_device(),
        "a2h": scan_a2h_profile(),
        "sensa": scan_sensa(),
    }
    return result


def format_summary(info):
    lines = []
    dev = info.get("device", {})
    if dev:
        lines.append("手柄型号 : {productName}  (VID {vendorId} / PID {productIdHex})".format(**dev)
                     if "vendorId" in dev else f"手柄型号 : {dev.get('productName')}")
        if dev.get("serialNumber"):
            lines.append(f"序列号   : {dev['serialNumber']}")
    else:
        lines.append("手柄型号 : 未在雷云日志中找到")
    proc = info.get("process")
    lines.append(f"雷云进程 : {proc if proc else '未检测到(建议先开雷云插好手柄再探测)'}")

    a2h = info.get("a2h", {})
    prof = a2h.get("profile", {})
    if prof:
        bands = prof.get("underlying_bands", {}).get("bands", [{}])[0]
        fr = bands.get("frequency_range", {})
        lines.append(f"A2H 频段 : 输入 {fr.get('min')}-{fr.get('max')}Hz")
        eq = prof.get("haptic_EQ", {}).get("keyframes", [])
        eq_str = ", ".join(f"{k['frequency']}Hz:{k['volume']}" for k in eq)
        lines.append(f"A2H EQ   : {eq_str}")
        tr = prof.get("transients", {})
        lines.append(f"瞬态检测 : prominence={tr.get('prominence')} duration={tr.get('duration')}s")
        comp = prof.get("compressor", {})
        lines.append(f"压缩器   : gamma={comp.get('gamma')} amp_comp={comp.get('amp_comp')}")
        lines.append(f"振幅窗口 : {bands.get('amplitude_window_length')}s  频率窗口: {bands.get('frequency_window_length')}s")
        lines.append(f"最小门限 : {bands.get('minimal_amplitude_threshold')}")
    else:
        lines.append("A2H 配方 : 未找到")
    if a2h.get("encoderDLL"):
        lines.append(f"编码器DLL: {a2h['encoderDLL']}")
    rep = a2h.get("deviceReport", {})
    if rep:
        lines.append(f"触觉报告 : {rep.get('DeviceName')} 部位x{rep.get('NumberBodyPart')} "
                     f"马达频率{rep['Bodypart'][0]['Characteristics']['ValueReport'][0]['FrequencyMin']}"
                     f"-{rep['Bodypart'][0]['Characteristics']['ValueReport'][0]['FrequencyMax']}Hz")
    return "\n".join(lines)


if __name__ == "__main__":
    info = probe_all()
    print("========== 雷云4 侦察结果 ==========")
    print(format_summary(info))
    print("\n========== 原始JSON ==========")
    print(json.dumps(info, indent=2, ensure_ascii=False))
