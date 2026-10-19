#!/bin/sh
echo "== modetest"; which modetest
echo "== pkg-config"
for p in libdrm gstreamer-1.0 gstreamer-app-1.0 gstreamer-video-1.0 gstreamer-allocators-1.0 gstreamer-webrtc-1.0; do
  printf "%s: " $p; pkg-config --modversion $p 2>&1 | head -1
done
echo "== python gi webrtc"
python3 -c "import gi; gi.require_version('Gst','1.0'); gi.require_version('GstWebRTC','1.0'); gi.require_version('GstSdp','1.0'); from gi.repository import Gst, GstWebRTC, GstSdp; print('gi webrtc ok')" 2>&1 | tail -1
echo "== apt candidates"
apt-cache policy libdrm-tests libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev libgstreamer-plugins-bad1.0-dev gir1.2-gst-plugins-bad-1.0 python3-gi 2>/dev/null | grep -E "^[a-z]|Installed|Candidate"
echo "== drm planes (sysfs/debugfs)"
ls /sys/kernel/debug/dri/0 2>/dev/null | head
