#!/usr/bin/env python3
"""T14：WebRTC 网关 —— 把板内 RTP(127.0.0.1:5004, H.265) 用 webrtcbin 送给浏览器。

只用 Python 标准库 + gi(Gst/GstWebRTC/GstSdp)。信令走 :8001 的 /offer /answer /stats。
同一时间只服务一个客户端：每次 GET /offer 会把上一个管道拆掉重建。
不用 STUN/TURN —— 手机和板子在同一个局域网。

页面在 :8002（或 :8000）而网关在 :8001，属于跨源，所以**每个响应都要带
Access-Control-Allow-Origin: ***，否则浏览器把 fetch 拦掉。
"""

import argparse
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import gi

gi.require_version("Gst", "1.0")
gi.require_version("GstWebRTC", "1.0")
gi.require_version("GstSdp", "1.0")
from gi.repository import GLib, Gst, GstSdp, GstWebRTC  # noqa: E402

ARGS = None
LOOP = None
LOCK = threading.Lock()          # 同一时间只有一个线程碰 GStreamer
PIPE = None                      # 当前 webrtcbin 所在的 pipeline
WEBRTC = None
STATS_PATH = "/tmp/webrtc_stats.log"
START = time.time()

CAPS_RTP = ("application/x-rtp,media=video,encoding-name=H265,"
            "clock-rate=90000,payload=96")


def build():
    """建一条新管道，返回 webrtcbin；失败返回 None。

    注意：这版 GStreamer(1.24) 的 webrtcbin 不接受 parse_launch 的自动链接
    （它的 sink_%u 是 sometimes 模板），实测报 `could not link queue0 to w`。
    所以手工搭：udpsrc ! queue ! webrtcbin，中间用 get_request_pad 显式申请 sink 垫。
    """
    global PIPE, WEBRTC
    teardown()

    src = Gst.ElementFactory.make("udpsrc", "src")
    src.set_property("port", ARGS.rtp_port)
    src.set_property("caps", Gst.Caps.from_string(CAPS_RTP))
    q = Gst.ElementFactory.make("queue", "q")
    q.set_property("max-size-buffers", 0)
    q.set_property("max-size-bytes", 0)
    q.set_property("max-size-time", 50000000)
    q.set_property("leaky", 2)                      # 2 = downstream
    bin_ = Gst.ElementFactory.make("webrtcbin", "w")
    if bin_ is None:
        log("FAIL webrtcbin 工厂没有（gst-plugins-webrtc 没装？）")
        return None
    bin_.set_property("bundle-policy", getattr(
        GstWebRTC, "WebRTCBundlePolicy", None) and GstWebRTC.WebRTCBundlePolicy.MAX_BUNDLE or 3)
    bin_.set_property("latency", 0)

    PIPE = Gst.Pipeline.new("gw")
    for el in (src, q, bin_):
        PIPE.add(el)

    # 必须先让元素进 PLAYING：udpsrc 的 src 垫是 sometimes 模板，
    # 没状态时 get_static_pad("src") 拿不到东西，链接必然失败。
    PIPE.set_state(Gst.State.PLAYING)

    sp = None
    for _ in range(40):
        sp = src.get_static_pad("src")
        if sp is not None:
            break
        time.sleep(0.05)
    if sp is None:
        log("FAIL udpsrc 没长出 src 垫")
        return None
    if not sp.link(q.get_static_pad("sink")):
        log("FAIL udpsrc -> queue 链接失败")
        return None

    sinkpad = bin_.get_request_pad("sink_%u")
    if sinkpad is None:
        log("FAIL 申请不到 webrtcbin 的 sink 垫")
        return None
    if not q.get_static_pad("src").link(sinkpad):
        log("FAIL queue -> webrtcbin sink 垫链接失败")
        return None

    # 等 webrtcbin 把进来的 pad 接好、生成 0 号 transceiver
    tr = None
    for _ in range(40):
        try:
            tr = bin_.emit("get-transceiver", 0)
        except Exception:
            tr = None
        if tr is not None:
            break
        time.sleep(0.05)
    if tr is None:
        log("FAIL 等不到 transceiver 0")
        return None
    tr.set_property("direction", GstWebRTC.WebRTCRtpTransceiverDirection.SENDONLY)
    WEBRTC = bin_
    return bin_


def log(msg):
    sys.stderr.write("%s %s\n" % (time.strftime("%H:%M:%S"), msg))
    sys.stderr.flush()


def teardown():
    global PIPE, WEBRTC
    if PIPE is not None:
        PIPE.set_state(Gst.State.NULL)
        PIPE.get_bus().pop_filtered(Gst.MessageType.ERROR)
        PIPE = None
        WEBRTC = None


def make_offer():
    bin_ = build()
    if bin_ is None:
        return None

    box = {}
    done = threading.Event()

    def on_created(promise):
        try:
            reply = promise.get_reply()
            if reply is None:
                box["err"] = "create-offer 没有 reply"
                return
            offer = reply.get_value("offer")
            p2 = Gst.Promise.new()
            bin_.emit("set-local-description", offer, p2)
            p2.interrupt()
            box["sdp"] = offer.sdp.as_text()
        finally:
            done.set()

    prom = Gst.Promise.new_with_change_func(on_created)
    bin_.emit("create-offer", None, prom)
    if not done.wait(5) or "sdp" not in box:
        log("FAIL 生成 offer 失败: %s" % box.get("err", "超时"))
        return None

    # 等 ICE 收集完（局域网，只有 host candidate，一般很快）
    complete = getattr(GstWebRTC.WebRTCIceGatheringState, "COMPLETE", None)
    t0 = time.time()
    while time.time() - t0 < 3.0:
        if complete is not None and bin_.get_property("ice-gathering-state") == complete:
            break
        time.sleep(0.05)
    return box["sdp"]


def apply_answer(text):
    if WEBRTC is None:
        return "没有活动管道，先 GET /offer"
    st, sdp_msg = GstSdp.SDPMessage.new_from_text(text)
    if st != GstSdp.SDPMessageError.OK:
        return "SDP 解析失败"
    desc = GstWebRTC.WebRTCSessionDescription.new(GstWebRTC.WebRTCSDPType.ANSWER, sdp_msg)
    prom = Gst.Promise.new()
    WEBRTC.emit("set-remote-description", desc, prom)
    prom.interrupt()
    return None


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "k11c-webrtc-gw/0.1"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, ctype, body):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path != "/offer":
            self._send(404, "text/plain", "404\n")
            return
        with LOCK:
            try:
                sdp = make_offer()
            except Exception as exc:
                log("FAIL make_offer: %r" % (exc,))
                sdp = None
        if sdp is None:
            self._send(500, "text/plain", "offer failed\n")
            return
        log("offer 已生成，%d 字节" % len(sdp))
        self._send(200, "text/plain", sdp)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n).decode("utf-8", "replace") if n else ""
        if path == "/answer":
            with LOCK:
                why = apply_answer(body)
            if why:
                log("answer 失败: %s" % why)
                self._send(500, "text/plain", why + "\n")
                return
            log("answer 已应用")
            self._send(200, "text/plain", "ok\n")
        elif path == "/stats":
            line = "%s %s\n" % (time.strftime("%H:%M:%S"), body.replace("\n", " "))
            try:
                with open(STATS_PATH, "a") as fh:
                    fh.write(line)
            except OSError as exc:
                self._send(500, "text/plain", str(exc) + "\n")
                return
            self._send(200, "text/plain", "ok\n")
        elif path == "/state":
            self._send(200, "application/json", json.dumps(
                {"uptime_s": round(time.time() - START, 1),
                 "peer": WEBRTC is not None,
                 "stats_lines": count_lines(STATS_PATH)}).encode())
        else:
            self._send(404, "text/plain", "404\n")


def count_lines(path):
    try:
        with open(path) as fh:
            return sum(1 for _ in fh)
    except OSError:
        return 0


def main():
    global ARGS, LOOP
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8001)
    ap.add_argument("--rtp-port", type=int, default=5004)
    ARGS = ap.parse_args()

    Gst.init(None)
    LOOP = GLib.MainLoop()
    threading.Thread(target=LOOP.run, daemon=True).start()
    log("GLib main loop started; gateway on %s:%d, RTP <- 127.0.0.1:%d"
        % (ARGS.host, ARGS.port, ARGS.rtp_port))

    httpd = ThreadingHTTPServer((ARGS.host, ARGS.port), Handler)
    httpd.daemon_threads = True
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        with LOCK:
            teardown()
        LOOP.quit()


if __name__ == "__main__":
    os.environ.setdefault("GST_DEBUG", "1")
    main()
