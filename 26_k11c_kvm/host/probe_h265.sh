#!/bin/sh
SRC="videotestsrc pattern=smpte num-buffers=1 ! video/x-raw,format=NV12,width=1920,height=1080 ! imagefreeze is-live=true ! video/x-raw,framerate=60/1"
for ENC in "mpph265enc bps=6000000 gop=60 ! h265parse" "mpph264enc bps=8000000 gop=60 ! h264parse"; do
  echo "== $ENC"
  timeout 12 gst-launch-1.0 -v $SRC ! $ENC ! fpsdisplaysink video-sink=fakesink text-overlay=false sync=false > /tmp/enc.log 2>&1 &
  sleep 6
  top -bn1 | grep -E "gst-launch" | head -2
  wait
  grep -o "rendered: [0-9]*, dropped: [0-9]*, current: [0-9.]*, average: [0-9.]*" /tmp/enc.log | tail -1
done
echo "== services"
systemctl is-active k11c-kvm lightdm
