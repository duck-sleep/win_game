#!/usr/bin/env python3
"""诊断：udpsrc(caps) -> queue -> webrtcbin(sink_%u) 到底哪一步、为什么链不上。"""
import sys
import time

import gi

gi.require_version("Gst", "1.0")
gi.require_version("GstWebRTC", "1.0")
from gi.repository import Gst, GstWebRTC  # noqa: E402

Gst.init(None)

src = Gst.ElementFactory.make("udpsrc", "src")
src.set_property("port", 5004)
caps = Gst.Caps.from_string("application/x-rtp,media=video,encoding-name=H265,"
                            "clock-rate=90000,payload=96")
print("caps:", None if caps is None else caps.to_string())
src.set_property("caps", caps)

q = Gst.ElementFactory.make("queue", "q")
b = Gst.ElementFactory.make("webrtcbin", "w")
print("webrtcbin 有吗:", b is not None)

p = Gst.Pipeline.new("t")
for e in (src, q, b):
    p.add(e)
print("set_state:", p.set_state(Gst.State.PLAYING))
time.sleep(1.0)

sp = src.get_static_pad("src")
print("udpsrc src pad:", sp)
if sp is not None:
    print("  caps:", sp.get_current_caps(), " template presence:",
          sp.get_pad_template().presence.value_nick if sp.get_pad_template() else "-")
    r = sp.link(q.get_static_pad("sink"))
    print("link udpsrc->queue:", r)

qp = q.get_static_pad("src")
print("queue src pad linked:", qp.is_linked())
sk = b.get_request_pad("sink_%u")
print("request sink pad:", sk)
if sk is not None:
    print("link queue->webrtcbin:", qp.link(sk))

for _ in range(20):
    m = p.get_bus().poll(Gst.MessageType.ERROR, 200 * Gst.MSECOND)
    if m is not None:
        err = m.parse_error()[0]
        print("BUS ERROR:", err.message, "| src:", m.src.get_name() if m.src else "-")
        break
    time.sleep(0.1)
print("state now:", p.get_state(0).state)
p.set_state(Gst.State.NULL)
sys.exit(0)
