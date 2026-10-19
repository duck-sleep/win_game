#!/bin/sh
# 10-19 hardware path probe: raw display without decode, MPP H.264 headroom, browser H.264 parts
export DISPLAY=:0 XAUTHORITY=/home/kickpi/.Xauthority
G=gst-launch-1.0
SRC="videotestsrc pattern=smpte is-live=true ! video/x-raw,format=NV12,width=1920,height=1080,framerate=60/1"
cpu() { sleep 6; top -bn1 | sed -n '3p'; ps -eo pcpu,comm --sort=-pcpu | sed -n '2,5p' | tr '\n' ';'; echo; }
fps() { grep -oE 'average: [0-9.]+' "$1" | tail -1; grep -oE 'dropped: [0-9]+' "$1" | tail -1; grep -iE 'error|erro' "$1" | head -3; }

echo '=== inventory ==='
for e in webrtcbin rtph264pay h264parse tee appsink timeoverlay clockoverlay mpph264enc rkximagesink xvimagesink kmssink x264enc; do
  printf '%s: ' $e; gst-inspect-1.0 $e >/dev/null 2>&1 && echo yes || echo no
done
ls /usr/lib/aarch64-linux-gnu 2>/dev/null | grep -iE 'rockit|rkmedia|rkmpi|rockchip_mpp|rga' | tr '\n' ' '; echo
command -v mediamtx xvinfo | tr '\n' ' '; echo
xvinfo 2>/dev/null | grep -E 'Adaptor|image formats|NV12' | head -6
gst-inspect-1.0 mpph264enc 2>/dev/null | grep -E '^  [a-z-]+ +:' | awk '{print $1}' | tr '\n' ' '; echo
gst-inspect-1.0 rkximagesink 2>/dev/null | grep -E '^  [a-z-]+ +:' | awk '{print $1}' | tr '\n' ' '; echo

echo '=== stop current soft path ==='
echo kickpi | sudo -S systemctl stop k11c-kvm 2>&1 | tail -1
pkill -f 'tv[.]sh'; pkill -x ffplay; sleep 2
ps -eo comm | grep -cE '^(ffmpeg|ffplay)$'

echo '=== B1 source only 1080p60 NV12 -> fakesink ==='
timeout 12 $G -q $SRC ! fpsdisplaysink video-sink=fakesink text-overlay=false sync=true -v > /tmp/b1.log 2>&1 &
cpu; wait; fps /tmp/b1.log

echo '=== B2 raw -> rkximagesink (no decode, via X) ==='
timeout 12 $G $SRC ! fpsdisplaysink video-sink=rkximagesink text-overlay=false sync=true -v > /tmp/b2.log 2>&1 &
cpu; wait; fps /tmp/b2.log

echo '=== B3 raw -> xvimagesink ==='
timeout 12 $G $SRC ! fpsdisplaysink video-sink=xvimagesink text-overlay=false sync=true -v > /tmp/b3.log 2>&1 &
cpu; wait; fps /tmp/b3.log

echo '=== B4 raw -> mpph264enc 1080p60 -> fakesink ==='
timeout 12 $G $SRC ! mpph264enc ! h264parse ! fpsdisplaysink video-sink=fakesink text-overlay=false sync=true -v > /tmp/b4.log 2>&1 &
cpu; wait; fps /tmp/b4.log

echo '=== B5 tee: timeoverlay -> [rkximagesink] + [mpph264enc] ==='
timeout 12 $G $SRC ! timeoverlay font-desc="Sans 48" halignment=center valignment=bottom ! tee name=t \
  t. ! queue max-size-buffers=1 leaky=downstream ! fpsdisplaysink name=tv video-sink=rkximagesink text-overlay=false sync=true \
  t. ! queue max-size-buffers=2 leaky=downstream ! mpph264enc ! h264parse ! fpsdisplaysink name=enc video-sink=fakesink text-overlay=false sync=false -v > /tmp/b5.log 2>&1 &
cpu; wait
grep -E 'tv.*average|enc.*average' /tmp/b5.log | grep -oE '(tv|enc)[^ ]*|average: [0-9.]+|dropped: [0-9]+' | tail -6 | tr '\n' ' '; echo
grep -iE 'error' /tmp/b5.log | head -3

echo '=== B6 lightdm stopped -> kmssink ==='
echo kickpi | sudo -S systemctl stop lightdm; sleep 3
fuser /dev/dri/card0 2>&1 | tr '\n' ' '; echo
echo kickpi | sudo -S timeout 10 $G videotestsrc pattern=smpte is-live=true ! video/x-raw,format=NV12,width=1920,height=1080,framerate=60/1 ! fpsdisplaysink video-sink=kmssink text-overlay=false sync=true -v > /tmp/b6.log 2>&1
fps /tmp/b6.log
echo '=== done; rebooting to restore ==='
