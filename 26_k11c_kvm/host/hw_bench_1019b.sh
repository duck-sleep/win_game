#!/bin/sh
export DISPLAY=:0 XAUTHORITY=/home/kickpi/.Xauthority
echo kickpi | sudo -S systemctl start lightdm; sleep 8
pkill -f 'tv[.]sh'; pkill -x ffplay; pkill -x onboard; sleep 1
G=gst-launch-1.0
SRC="videotestsrc pattern=smpte num-buffers=1 ! video/x-raw,format=NV12,width=1920,height=1080 ! imagefreeze is-live=true ! video/x-raw,framerate=60/1"
OSD="timeoverlay font-desc=Sans,48 halignment=center valignment=bottom"
cpu() { sleep 7; top -bn1 | sed -n '3p'; ps -eo pcpu,comm --sort=-pcpu | sed -n '2,4p' | tr '\n' ';'; echo; }
last() { grep -E 'last-message' "$1" | grep -E "$2" | tail -1 | grep -oE 'rendered: [0-9]+, dropped: [0-9]+.*' ; grep -iE 'ERROR' "$1" | head -2; }

echo '=== C1 frozen src + timeoverlay -> fakesink (source+OSD cost) ==='
timeout 12 $G $SRC ! $OSD ! fpsdisplaysink video-sink=fakesink text-overlay=false sync=true -v > /tmp/c1.log 2>&1 &
cpu; wait; last /tmp/c1.log .

echo '=== C2 -> rkximagesink sync=false (raw to TV, no decode) ==='
timeout 12 $G $SRC ! $OSD ! fpsdisplaysink video-sink=rkximagesink text-overlay=false sync=false -v > /tmp/c2.log 2>&1 &
cpu; wait; last /tmp/c2.log .

echo '=== C3 -> rkximagesink sync=true max-lateness=-1 ==='
timeout 12 $G $SRC ! $OSD ! fpsdisplaysink video-sink="rkximagesink max-lateness=-1" text-overlay=false sync=true -v > /tmp/c3.log 2>&1 &
cpu; wait; last /tmp/c3.log .

echo '=== C4 tee: [rkximagesink] + [mpph264enc 1080p60] ==='
timeout 12 $G $SRC ! $OSD ! tee name=t \
  t. ! queue max-size-buffers=1 leaky=downstream ! fpsdisplaysink name=tv video-sink=rkximagesink text-overlay=false sync=false \
  t. ! queue max-size-buffers=2 leaky=downstream ! mpph264enc bps=8000000 gop=60 ! h264parse ! fpsdisplaysink name=enc video-sink=fakesink text-overlay=false sync=false -v > /tmp/c4.log 2>&1 &
cpu; wait; echo tv:; last /tmp/c4.log 'tv:'; echo enc:; last /tmp/c4.log 'enc:'
