#!/bin/sh
# T13 验收：fakevo --enc 跑 70 秒，第 20 秒起在板子上收 6 秒 RTP，落地成 h265 再数帧。
# 不用 set -e：systemctl is-active / timeout 这些"正常返回非 0"的会把脚本提前打断。
VO=/opt/k11c-kvm/vo

printf '%s\n' "$K11C_SUDO" | sudo -S true

echo "=== 停掉 T12 常驻单元，腾出 DRM ==="
sudo systemctl stop k11c-fakevo || true
sleep 2
echo "card0 占用者: [$(sudo fuser -v /dev/dri/card0 2>&1 | tr -s ' ')]"
echo "lightdm: $(systemctl is-active lightdm)"

echo "=== 起 fakevo --enc 70 秒 ==="
sudo systemd-run --unit=k11c-fakevo --collect -p WorkingDirectory=$VO $VO/fakevo --enc --seconds 70

echo "=== 等 20 秒后收 6 秒码流 ==="
sleep 20
timeout -s INT 6 gst-launch-1.0 -e udpsrc port=5004 \
  caps="application/x-rtp,media=video,encoding-name=H265,clock-rate=90000,payload=96" \
  ! rtph265depay ! h265parse ! "video/x-h265,stream-format=byte-stream" \
  ! filesink location=/tmp/t13.h265 2>&1 | tail -3 || true

ls -l /tmp/t13.h265
echo "=== ffprobe 数帧 ==="
ffprobe -v error -count_frames -select_streams v:0 \
  -show_entries stream=codec_name,width,height,nb_read_frames -of csv /tmp/t13.h265
echo "=== 抽第 100 帧成图 ==="
ffmpeg -nostdin -loglevel error -i /tmp/t13.h265 -vf "select=eq(n\,100)" -frames:v 1 -y /tmp/t13.jpg
ls -l /tmp/t13.jpg
echo "=== fakevo CPU ==="
top -bn1 | grep -E "fakevo" | head -3
echo "=== fakevo 日志 ==="
sleep 26
sudo journalctl -u k11c-fakevo --no-pager -o cat | tail -60
