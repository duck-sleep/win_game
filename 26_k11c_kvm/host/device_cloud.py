#!/usr/bin/env python3
"""K11C -> JetKVM cloud probe (experiment, 2026-10-28).

Two modes:
  serve  : HTTP on :8010. GET / shows a form that POSTs to api.jetkvm.com/oidc/google
           with {deviceId, returnTo}; GET /adopt captures tempToken and exchanges it
           for a secretToken at POST /devices/token, saving it to /tmp/k11c-cloud.json.
  ws     : dial wss://api.jetkvm.com/ with the saved secretToken and log every message.

Deliberate choices:
  * SKU is "k11c-rk3566" (unknown to their cloud -> ignored). NEVER send "jetkvm-v2":
    their SKUS table maps that SKU to an RV1106 system image; an OTA to this board bricks it.
  * deviceId is this board's real chip serial from /proc/cpuinfo.
"""
import asyncio
import json
import os
import re
import sys
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

CLOUD = "https://api.jetkvm.com"
SKU = "k11c-rk3566"
STATE = "/tmp/k11c-cloud.json"
PORT = 8010


def device_id():
    try:
        txt = open("/proc/cpuinfo").read()
        m = re.search(r"Serial\s*:\s*(\S+)", txt)
        if m:
            return m.group(1)
    except OSError:
        pass
    return "unknown_device_id"


def http_post_json(url, payload, bearer=None):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    if bearer:
        req.add_header("Authorization", "Bearer " + bearer)
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status, r.read().decode()


PAGE = """<!doctype html><meta charset=utf-8><title>K11C cloud probe</title>
<style>body{font:16px/1.6 system-ui;margin:3em auto;max-width:44em;padding:0 1em}
code{background:#eee;padding:.1em .3em}table{border-collapse:collapse}
td,th{border:1px solid #ccc;padding:.3em .6em;text-align:left}</style>
<h2>K11C &rarr; JetKVM cloud (probe)</h2>
<table>
<tr><th>deviceId</th><td><code>%s</code></td></tr>
<tr><th>SKU</th><td><code>%s</code></td></tr>
<tr><th>returnTo</th><td><code>%s</code></td></tr>
</table>
<p>Next step opens Google login for the account that will own this device.</p>
<form action="https://api.jetkvm.com/oidc/google" method="POST">
  <input type="hidden" name="deviceId" value="%s">
  <input type="hidden" name="returnTo" value="%s">
  <button style="font-size:1.1em;padding:.6em 1.2em">用 Google 登录并注册这台设备</button>
</form>
"""


class H(BaseHTTPRequestHandler):
    def _send(self, code, text, ctype="text/html; charset=utf-8"):
        b = text.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path)
        host = self.headers.get("Host") or ("192.168.31.89:%d" % PORT)
        if u.path == "/":
            rt = "http://%s/adopt" % host
            self._send(200, PAGE % (device_id(), SKU, rt, device_id(), rt))
            return
        if u.path == "/adopt":
            q = parse_qs(u.query)
            temp = (q.get("tempToken") or [""])[0]
            dev = (q.get("deviceId") or [""])[0]
            if not temp:
                self._send(400, "<h3>no tempToken in callback</h3><pre>%s</pre>" % self.path)
                return
            try:
                st, body = http_post_json(CLOUD + "/devices/token", {"tempToken": temp})
            except Exception as e:
                self._send(502, "<h3>token exchange failed</h3><pre>%r</pre>" % (e,))
                return
            print("[adopt] token exchange HTTP %s -> %s" % (st, body[:200]), flush=True)
            secret = ""
            try:
                secret = json.loads(body).get("secretToken", "")
            except Exception:
                pass
            if not secret:
                self._send(502, "<h3>no secretToken</h3><pre>%s</pre>" % body)
                return
            with open(STATE, "w") as f:
                json.dump({"deviceId": dev or device_id(), "sku": SKU,
                           "secretToken": secret, "oidcGoogleLen": len((q.get("oidcGoogle") or [""])[0])}, f)
            os.chmod(STATE, 0o600)
            self._send(200, "<h3>registered</h3><p>deviceId <code>%s</code></p>"
                            "<p>secretToken saved on the board. Now run: "
                            "<code>device_cloud.py ws</code></p>" % (dev or device_id()))
            return
        self._send(404, "not found")

    def log_message(self, fmt, *args):
        print("[http] " + fmt % args, flush=True)


async def ws_main():
    import websockets
    st = json.load(open(STATE))
    did, token = st["deviceId"], st["secretToken"]
    hdr = [("Authorization", "Bearer " + token),
           ("X-Device-ID", did),
           ("X-App-Version", "0.5.0-k11c"),
           ("X-Device-SKU", st.get("sku", SKU))]
    url = "wss://api.jetkvm.com/"
    print("[ws] dialing %s as %s sku=%s" % (url, did, st.get("sku")), flush=True)
    async with websockets.connect(url, extra_headers=hdr, ping_interval=20) as ws:
        print("[ws] connected", flush=True)
        n = 0
        async for msg in ws:
            n += 1
            text = msg if isinstance(msg, str) else msg.decode("utf-8", "replace")
            print("[ws] #%d recv %d bytes: %s" % (n, len(text), text[:300]), flush=True)
            # keep the full message for offline analysis (SDP is long)
            with open("/tmp/cloud_msgs.log", "a") as f:
                f.write("=== #%d %s ===\n%s\n" % (n, asyncio.get_event_loop().time(), text))


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "serve"
    if mode == "serve":
        print("[http] serving on 0.0.0.0:%d  deviceId=%s" % (PORT, device_id()), flush=True)
        ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
    elif mode == "ws":
        asyncio.run(ws_main())
    else:
        print("usage: device_cloud.py serve|ws")
