#!/bin/sh
# T14 部署 + 板内自测：起网关、起静态服务、curl 一次 /offer 看 SDP 里有没有 H265。
VO=/opt/k11c-kvm
printf '%s\n' "$K11C_SUDO" | sudo -S true

python3 -m py_compile $VO/webrtc_gw.py && echo COMPILE_OK

echo "=== 起网关 :8001 ==="
sudo systemctl stop k11c-gw 2>/dev/null
sudo systemd-run --unit=k11c-gw --collect $VO/webrtc_gw.py --port 8001 --rtp-port 5004
sleep 2
systemctl is-active k11c-gw

echo "=== 起静态服务 :8002 ==="
sudo systemctl stop k11c-probe 2>/dev/null
sudo systemd-run --unit=k11c-probe --collect -p WorkingDirectory=$VO/www \
  /usr/bin/python3 -m http.server 8002
sleep 2
systemctl is-active k11c-probe

echo "=== fakevo --enc 在跑吗（RTP 来源） ==="
systemctl is-active k11c-fakevo

echo "=== curl /offer ==="
curl -s --max-time 15 http://127.0.0.1:8001/offer > /tmp/offer.sdp
echo "offer 字节数: $(wc -c < /tmp/offer.sdp)"
grep -c "H265\|h265" /tmp/offer.sdp | sed 's/^/H265 出现次数: /'
grep -m3 "^m=\|^a=rtpmap" /tmp/offer.sdp
echo "=== 网关日志 ==="
sudo journalctl -u k11c-gw --no-pager -o cat | tail -5
