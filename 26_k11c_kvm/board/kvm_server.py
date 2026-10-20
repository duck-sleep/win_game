#!/usr/bin/env python3
"""K11C IP-KVM 板端服务：假源 JPEG 帧分发（T4）+ JSON-RPC 键鼠控制（T6）。

只用标准库。所有客户端共享"最新一帧"，慢客户端自动跳帧、不排队。
RPC 方法名与 jetkvm/kvm 的 jsonrpc.go 对齐（见 port/PORTING.md），
这样以后搬它的 useKeyboard.ts / useMouse.ts 能直接接上。
"""

import argparse
import collections
import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
SOI = b"\xff\xd8"
EOI = b"\xff\xd9"
FPS_WINDOW = 5.0

SRC = None
MJPEG = True
START = time.monotonic()

RPC_LOCK = threading.Lock()
RPC_STATS = {
    "total": 0,
    "by_method": {},
    "last_peer": "",
    "last_method": "",
    "last_err": "",
    "last_ms": 0.0,
}

HID_PATHS = {"keyboard": "/dev/hidg0", "abs": "/dev/hidg1"}
HID_FDS = {}
HID_LOCK = threading.Lock()


def log(msg):
    sys.stderr.write("%s %s\n" % (time.strftime("%H:%M:%S"), msg))
    sys.stderr.flush()


class HidBusy(Exception):
    """电脑没在收报文（睡眠/没枚举/线拔了），非阻塞写返回 EAGAIN。"""


# ---------- HID ----------


def _hid_open(name):
    path = HID_PATHS[name]
    if not os.path.exists(path):
        raise FileNotFoundError("%s 的设备节点 %s 不存在" % (name, path))
    # 非阻塞：电脑不收时 write 不能把线程卡死（坑 4）
    fd = os.open(path, os.O_WRONLY | os.O_NONBLOCK)
    HID_FDS[name] = fd
    return fd


def _hid_reopen(name):
    fd = HID_FDS.pop(name, None)
    if fd is not None:
        try:
            os.close(fd)
        except OSError:
            pass
    return _hid_open(name)


def write_hid(name, payload, retries=20, delay=0.005):
    """写一个 HID 报文。

    端点的 IN 队列只有 1 深：连着发两枪（按下 + 松开）时第二枪常拿到 EAGAIN，
    所以先有界重试（默认最多 20 次 × 5ms = 100ms），仍失败才报错。
    不重试的话按键会丢，松开丢了电脑就会一直重复那个键。
    """
    data = bytes(payload)
    with HID_LOCK:
        for attempt in range(retries + 1):
            fd = HID_FDS.get(name)
            if fd is None:
                fd = _hid_open(name)
            try:
                os.write(fd, data)
                return
            except BlockingIOError:
                if attempt >= retries:
                    raise HidBusy("%s: 电脑没在收报文" % name)
                time.sleep(delay)
            except OSError:
                # 设备重绑后旧 fd 可能废掉（JetKVM 在 RV1106 上踩过 ENXIO），重开一次
                _hid_reopen(name)
        raise OSError("%s: 重开后仍写不进去" % name)


# ---------- 报文（布局照 jetkvm internal/usbgadget） ----------


def keyboard_report(modifiers, keys):
    k = [int(x) & 0xFF for x in keys][:6]
    k += [0] * (6 - len(k))
    write_hid("keyboard", [int(modifiers) & 0xFF, 0] + k)


def abs_mouse(x, y, buttons):
    x = max(0, min(32767, int(x)))
    y = max(0, min(32767, int(y)))
    write_hid("abs", [1, int(buttons) & 0xFF, x & 0xFF, x >> 8, y & 0xFF, y >> 8])


def wheel_report(y, x=0):
    # 描述符 Report ID 2 只有 2 个数据字节，写 3 字节
    write_hid("abs", [2, int(y) & 0xFF, int(x) & 0xFF])


# ---------- 字符 → 键码（US 布局，§7.3） ----------

KEYMAP = {}
for _i, _ch in enumerate("abcdefghijklmnopqrstuvwxyz"):
    KEYMAP[_ch] = (0, 0x04 + _i)
for _i, _ch in enumerate("123456789"):
    KEYMAP[_ch] = (0, 0x1E + _i)
KEYMAP["0"] = (0, 0x27)
for _ch, _code in {
    " ": 0x2C, "-": 0x2D, "=": 0x2E, "[": 0x2F, "]": 0x30, "\\": 0x31,
    ";": 0x33, "'": 0x34, "`": 0x35, ",": 0x36, ".": 0x37, "/": 0x38,
}.items():
    KEYMAP[_ch] = (0, _code)
for _ch, _base in {
    "!": "1", "@": "2", "#": "3", "$": "4", "%": "5", "^": "6", "&": "7",
    "*": "8", "(": "9", ")": "0", "_": "-", "+": "=", "{": "[", "}": "]",
    "|": "\\", ":": ";", '"': "'", "~": "`", "<": ",", ">": ".", "?": "/",
}.items():
    KEYMAP[_ch] = (0x02, KEYMAP[_base][1])
for _ch in "abcdefghijklmnopqrstuvwxyz":
    KEYMAP[_ch.upper()] = (0x02, KEYMAP[_ch][1])


def type_text(text):
    """逐字符：按下报文 → 全 0 松开报文，间隔 10 ms。只认可打印 ASCII。"""
    skipped = 0
    for ch in text:
        ent = KEYMAP.get(ch)
        if ent is None:
            skipped += 1
            continue
        mod, code = ent
        keyboard_report(mod, [code])
        keyboard_report(0, [])
        time.sleep(0.010)
    return skipped


def key_combo(modifiers, key):
    keyboard_report(int(modifiers) & 0xFF, [int(key) & 0xFF])
    keyboard_report(0, [])


# ---------- 假源 ----------


class FrameSource:
    """跑 fakesrc.sh，把它的 stdout 切成一帧一帧 JPEG，只保留最新一帧。"""

    def __init__(self, cmd):
        self.cmd = cmd
        self.cond = threading.Condition()
        self.latest = None
        self.seq = 0
        self.stamps = collections.deque()
        self.clients = 0
        self.restarts = 0
        self.alive = False
        self._stop = threading.Event()

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.is_set():
            try:
                self._pump()
            except Exception as exc:
                log("fakesrc crashed: %r" % (exc,))
            with self.cond:
                self.alive = False
            if self._stop.is_set():
                break
            self.restarts += 1
            log("fakesrc restarts in 1s (#%d)" % self.restarts)
            time.sleep(1.0)

    def _pump(self):
        log("exec: %s" % " ".join(self.cmd))
        proc = subprocess.Popen(self.cmd, stdout=subprocess.PIPE)
        with self.cond:
            self.alive = True
        buf = bytearray()
        try:
            while True:
                # read1：有多少读多少，不等满 64K，否则帧会被攒着、延迟变大
                chunk = proc.stdout.read1(65536)
                if not chunk:
                    break
                buf += chunk
                while True:
                    i = buf.find(SOI)
                    if i < 0:
                        # SOI 可能被切成两半，留住最后一个字节
                        if len(buf) > 1:
                            del buf[: len(buf) - 1]
                        break
                    if i > 0:
                        del buf[:i]
                    j = buf.find(EOI, 2)
                    if j < 0:
                        break
                    self._publish(bytes(buf[: j + 2]))
                    del buf[: j + 2]
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.wait()
        log("fakesrc exited rc=%s" % proc.returncode)

    def _publish(self, frame):
        now = time.monotonic()
        with self.cond:
            self.latest = frame
            self.seq += 1
            self.stamps.append(now)
            while self.stamps and now - self.stamps[0] > FPS_WINDOW:
                self.stamps.popleft()
            self.cond.notify_all()

    def wait_frame(self, last_seq, timeout=2.0):
        with self.cond:
            if self.seq == last_seq:
                self.cond.wait(timeout)
            return self.seq, self.latest

    def fps(self):
        with self.cond:
            if len(self.stamps) < 2:
                return 0.0
            span = self.stamps[-1] - self.stamps[0]
            return (len(self.stamps) - 1) / span if span > 0 else 0.0


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
        return {
            "keyboard": os.path.exists(HID_PATHS["keyboard"]),
            "absoluteMouse": os.path.exists(HID_PATHS["abs"]),
            "relativeMouse": False,  # 固件没挂 hidg2
        }
    if method == "keyboardReport":
        keys = p.get("keys")
        if keys is None:
            keys = [p.get("keys%d" % i, 0) for i in range(1, 7)]
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
    if method == "wheelReport":
        wheel_report(p.get("y", 0), p.get("x", 0))
        return None
    if method == "typeText":
        text = p.get("text", "")
        return {"typed": len(text), "skipped": type_text(text)}
    if method == "keyCombo":
        key_combo(p.get("modifiers", 0), p.get("key", 0))
        return None
    raise ValueError("未实现的方法: %s" % method)


# ---------- HTTP ----------


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "k11c-kvm/0.6"
    def log_message(self, fmt, *args):
        pass

    def _reply(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/snapshot.jpg", "/stream.mjpg") and not MJPEG:
            self._reply(404, "text/plain; charset=utf-8", b"mjpeg disabled (--no-mjpeg)\n")
        elif path == "/state":
            self._state()
        elif path == "/snapshot.jpg":
            self._snapshot()
        elif path == "/stream.mjpg":
            self._stream()
        elif path in ("/", "/index.html"):
            self._index()
        else:
            self._reply(404, "text/plain; charset=utf-8", b"404 not found\n")

    def do_POST(self):
        t0 = time.monotonic()
        method = "?"
        rid = None
        err = None
        if self.path.split("?", 1)[0] != "/rpc":
            self._reply(404, "application/json", json.dumps({"error": "not found"}).encode())
            return
        n = int(self.headers.get("Content-Length") or 0)
        try:
            req = json.loads(self.rfile.read(n) or b"{}")
            rid = req.get("id")
            method = req.get("method") or "?"
            result = rpc_call(method, req.get("params"))
            body = {"jsonrpc": "2.0", "id": rid, "result": result}
        except HidBusy as exc:
            err = str(exc)
            body = {"jsonrpc": "2.0", "id": rid, "error": {"code": -32001, "message": str(exc)}}
        except Exception as exc:
            err = str(exc)
            body = {"jsonrpc": "2.0", "id": rid, "error": {"code": -32000, "message": str(exc)}}
        # 不逐条刷日志（鼠标节流时每秒几十条），只累计，交给 /state 暴露
        with RPC_LOCK:
            RPC_STATS["total"] += 1
            RPC_STATS["by_method"][method] = RPC_STATS["by_method"].get(method, 0) + 1
            RPC_STATS["last_peer"] = "%s:%s" % self.client_address[:2]
            RPC_STATS["last_method"] = method
            RPC_STATS["last_err"] = err or ""
            RPC_STATS["last_ms"] = round((time.monotonic() - t0) * 1000, 1)
        self._reply(200, "application/json", json.dumps(body).encode())

    def _state(self):
        with RPC_LOCK:
            rpc = dict(RPC_STATS)
        body = json.dumps(
            {
                "fps": round(SRC.fps(), 1),
                "clients": SRC.clients,
                "uptime_s": round(time.monotonic() - START, 1),
                "frames": SRC.seq,
                "source_alive": SRC.alive,
                "source_restarts": SRC.restarts,
                "rpc": rpc,
            }
        ).encode()
        self._reply(200, "application/json", body)

    def _snapshot(self):
        with SRC.cond:
            frame = SRC.latest
        if frame is None:
            self._reply(503, "text/plain; charset=utf-8", b"no frame yet\n")
            return
        self._reply(200, "image/jpeg", frame)

    def _index(self):
        page = os.path.join(HERE, "www", "index.html")
        if os.path.exists(page):
            with open(page, "rb") as fh:
                self._reply(200, "text/html; charset=utf-8", fh.read())
            return
        self._reply(
            200,
            "text/plain; charset=utf-8",
            ("k11c-kvm up. fps=%.1f frames=%d\n" % (SRC.fps(), SRC.seq)).encode(),
        )

    def _stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        SRC.clients += 1
        last = -1
        try:
            while True:
                seq, frame = SRC.wait_frame(last)
                if frame is None or seq == last:
                    continue
                last = seq
                self.wfile.write(
                    b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n"
                    % len(frame)
                )
                self.wfile.write(frame)
                self.wfile.write(b"\r\n")
        except OSError:
            pass
        finally:
            SRC.clients -= 1


class Server(ThreadingHTTPServer):
    daemon_threads = True
    # 关掉 Nagle：RPC 是小请求小应答，Nagle + 延迟 ACK 会把每次往返顶到 ~58ms
    disable_nagle_algorithm = True


def main():
    global SRC, START, MJPEG
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--fakesrc", default=os.path.join(HERE, "fakesrc.sh"))
    ap.add_argument("--hid-keyboard", default="/dev/hidg0")
    ap.add_argument("--hid-abs", default="/dev/hidg1")
    ap.add_argument("--no-mjpeg", action="store_true",
                    help="不启软编 MJPEG 假源：画面改走 WebRTC，这一路整个关掉省 CPU")
    args = ap.parse_args()

    HID_PATHS["keyboard"] = args.hid_keyboard
    HID_PATHS["abs"] = args.hid_abs

    START = time.monotonic()
    MJPEG = not args.no_mjpeg
    SRC = FrameSource(["/bin/sh", args.fakesrc])
    if MJPEG:
        SRC.start()
    else:
        log("mjpeg 关闭：不启 fakesrc，/stream.mjpg 与 /snapshot.jpg 回 404")

    httpd = Server((args.host, args.port), Handler)
    log("listening on %s:%d" % (args.host, args.port))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log("interrupted")
    finally:
        SRC.stop()
        httpd.server_close()


if __name__ == "__main__":
    main()
