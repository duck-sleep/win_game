#!/usr/bin/env python3
"""K11C 设备端服务：把 JSON-RPC 调用变成 /dev/hidg* 上的 HID 报文。

方法名与 jetkvm/kvm 的 jsonrpc.go 保持一致（见同目录 PORTING.md），
这样以后直接搬它的 useKeyboard.ts / useMouse.ts 就能接上。
只用标准库 —— 板子现在还没网，装不了 pip 包。

  python3 k11cd.py --host 0.0.0.0 --port 8080
  curl -s localhost:8080/rpc -d '{"method":"keyboardReport","params":{"modifiers":0,"keys":[8]}}'
  python3 k11cd.py --selftest          # 不连板子也能验字节对不对
"""

import argparse
import json
import os
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HID = {}
HID_ARGS = {}
HID_LOCK = threading.Lock()
START = time.time()


def open_hid(name, path):
    """按需打开；写失败就丢掉句柄下次重开。
    JetKVM 在 RV1106 上遇到过重绑后 /dev/hidgX 永久 ENXIO 的坑，所以它每次写完出错就重开——照做。"""
    ent = HID.get(name)
    if ent and ent.get("fh"):
        return ent
    if not os.path.exists(path):
        return None
    ent = {"path": path, "fh": open(path, "wb", buffering=0)}
    HID[name] = ent
    return ent


def write_hid(name, payload):
    with HID_LOCK:
        ent = open_hid(name, HID_ARGS.get(name, ""))
        if not ent:
            raise FileNotFoundError(f"{name} 的设备节点不存在")
        try:
            ent["fh"].write(bytes(payload))
        except OSError:
            try:
                ent["fh"].close()
            except OSError:
                pass
            ent["fh"] = open(ent["path"], "wb", buffering=0)
            ent["fh"].write(bytes(payload))  # 重开后再试一次，仍失败就抛出去


# ---------- 报文（布局照 jetkvm internal/usbgadget） ----------

def keyboard_report(modifiers, keys):
    k = [int(x) & 0xFF for x in keys][:6]
    k += [0] * (6 - len(k))
    write_hid("keyboard", [int(modifiers) & 0xFF, 0] + k)


def abs_mouse(x, y, buttons):
    x = max(0, min(32767, int(x)))
    y = max(0, min(32767, int(y)))
    write_hid("abs", [1, int(buttons) & 0xFF, x & 0xFF, x >> 8, y & 0xFF, y >> 8])


def rel_mouse(buttons, dx, dy, wheel=0, wheelx=0):
    def s8(v):
        return int(v) & 0xFF

    write_hid("rel", [int(buttons) & 0xFF, s8(dx), s8(dy), s8(wheel), s8(wheelx)])


def wheel_report(y, x=0):
    write_hid("abs", [2, int(y) & 0xFF, int(x) & 0xFF, 0, 0, 0])


# ---------- JSON-RPC ----------

CAPABILITIES = ["usb_serial"]  # 只报真有的，前端菜单会自己藏掉其余


def rpc_call(method, params):
    p = params or {}
    if method == "ping":
        return "pong"
    if method == "getDeviceCapabilities":
        return CAPABILITIES
    if method == "getLocalVersion":
        return {"current": os.uname().release, "build": os.uname().version.strip()}
    if method == "getUsbEmulationState":
        return {"keyboard": "hidg0" in HID, "absoluteMouse": "abs" in HID,
                "relativeMouse": "rel" in HID}
    if method == "keyboardReport":
        keys = p.get("keys")
        if keys is None:
            keys = [p.get(f"keys{i}", 0) for i in range(1, 7)]
        keyboard_report(p.get("modifiers", 0), keys)
        return None
    if method == "keypressReport":
        code = int(p.get("keyCode", 0))
        pressed = bool(p.get("pressed", True))
        keyboard_report(p.get("modifiers", 0), [code] if pressed else [])
        return None
    if method == "absMouseReport":
        abs_mouse(p.get("x", 0), p.get("y", 0), p.get("buttons", 0))
        return None
    if method == "relMouseReport":
        rel_mouse(p.get("buttons", 0), p.get("dx", 0), p.get("dy", 0),
                  p.get("wheel", 0), p.get("wheelX", 0))
        return None
    if method == "wheelReport":
        wheel_report(p.get("y", 0), p.get("x", 0))
        return None
    raise ValueError(f"未实现的方法: {method}")


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/state"):
            self._send(200, {"uptime_s": round(time.time() - START),
                             "hid": {k: v["path"] for k, v in HID.items()}})
        else:
            self._send(404, {"error": "用 POST /rpc；画面流在 P3 之后再接"})

    def do_POST(self):
        if not self.path.startswith("/rpc"):
            return self._send(404, {"error": "not found"})
        n = int(self.headers.get("Content-Length") or 0)
        rid = None
        try:
            req = json.loads(self.rfile.read(n) or b"{}")
            rid = req.get("id")
            result = rpc_call(req.get("method"), req.get("params"))
            if rid is None:
                return self._send(200, b"")  # 通知型，不回结果
            self._send(200, {"jsonrpc": "2.0", "id": rid, "result": result})
        except Exception as exc:  # JSON-RPC 错误体
            self._send(200, {"jsonrpc": "2.0", "id": rid,
                             "error": {"code": -32000, "message": str(exc)}})

    def log_message(self, *a):
        pass


def selftest():
    """把报文写到临时文件，验字节布局（不需要板子）。"""
    import subprocess
    import tempfile

    d = tempfile.mkdtemp()
    paths = {k: os.path.join(d, k) for k in ("keyboard", "abs", "rel")}
    for p in paths.values():
        open(p, "wb").close()
    global HID_ARGS
    HID_ARGS = paths
    keyboard_report(0x02, [0x04, 0x04])          # Shift + a a
    abs_mouse(32767, 0, 0x01)                    # 左上角 + 左键
    wheel_report(-3, 0)
    rel_mouse(0, 5, -3, 1, 0)
    for name in paths:
        hexs = subprocess.run(["xxd", "-p", paths[name]], capture_output=True,
                              text=True).stdout.replace("\n", "")
        print(f"{name:9s} {hexs}")
    print("期望: keyboard=0200 0404 0000 0000  abs=0101 ffff 0000  wheel=02fd 0000 0000  rel=0005 fd01 00")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--hid-keyboard", default="/dev/hidg0")
    ap.add_argument("--hid-abs", default="/dev/hidg1")
    ap.add_argument("--hid-rel", default="/dev/hidg2")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    global HID_ARGS
    HID_ARGS = {"keyboard": a.hid_keyboard, "abs": a.hid_abs, "rel": a.hid_rel}
    for name, path in HID_ARGS.items():
        if os.path.exists(path):
            open_hid(name, path)
        else:
            print(f"警告: {name} 的 {path} 不存在（先跑 k11c_gadget.sh start）")
    print(f"RPC on http://{a.host}:{a.port}/rpc  hid={HID_ARGS}")
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
