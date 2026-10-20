#!/bin/sh
# 出固件前的只读盘点：板上有哪些东西是"跑出来的"、重烧会丢。
# 不装、不改、不重启。sudo 口令走环境变量 K11C_SUDO。
S="${K11C_SUDO:-kickpi}"
su_() { printf '%s\n' "$S" | sudo -S "$@"; }

echo "=== 1. 内核 / 镜像出处 ==="
uname -a
cat /etc/hostname

echo
echo "=== 2. /opt/k11c-kvm 全量（大小 + md5） ==="
su_ find /opt/k11c-kvm -type f -printf '%s\t%p\n' 2>/dev/null | sort -k2

echo
echo "=== 3. systemd：我们加/改的单元 ==="
for u in k11c-gadget k11c-kvm k11c-fakevo k11c-webrtc k11c-gw k11c-probe; do
  f=/etc/systemd/system/$u.service
  [ -f "$f" ] && { echo "--- $f"; cat "$f"; }
done
echo "--- 瞬态单元（重烧/重启即没）"
su_ systemctl list-units --no-pager --all | grep -E 'k11c|kvm|gw|fakevo|probe' || true
echo "--- enabled 状态"
for u in k11c-gadget k11c-kvm lightdm; do
  printf '%s: ' "$u"; su_ systemctl is-enabled "$u" 2>&1 | head -1
done
echo "--- getty drop-in"
su_ find /etc/systemd/system -name '*.d' -path '*getty*' -o -name 'override.conf' 2>/dev/null | head
echo "--- masked 了谁"
ls -l /etc/systemd/system/ 2>/dev/null | grep -i '1\|mask' | head -20

echo
echo "=== 4. gadget 脚本：板上版本 vs repo ==="
su_ md5sum /usr/local/sbin/k11c-gadget.sh 2>/dev/null

echo
echo "=== 5. 桌面自启覆盖 ==="
su_ ls -l /home/kickpi/.config/autostart/ 2>/dev/null
for f in /home/kickpi/.config/autostart/*.desktop; do
  [ -f "$f" ] && { echo "--- $f"; cat "$f"; }
done

echo
echo "=== 6. apt：首启之后装了什么（history.log） ==="
su_ sh -c 'grep -h "^[A-Z][A-Z]*  20" /var/log/apt/history.log 2>/dev/null | tail -40'
echo "--- 装了但镜像可能没有的关键二进制"
for b in ffmpeg ffplay ffprobe iw mjpg_streamer gst-launch-1.0 v4l2-ctl xrandr onboard; do
  printf '%-16s %s\n' "$b" "$(command -v "$b" || echo -)"
done

echo
echo "=== 7. WiFi 配置落在哪 ==="
su_ ls -l /etc/NetworkManager/system-connections/ 2>/dev/null
nmcli -t -f NAME,TYPE,DEVICE con show 2>/dev/null | head

echo
echo "=== 8. rootfs 分区用了多少 ==="
df -h / /opt 2>/dev/null | head -5
su_ du -sh /opt /var/log 2>/dev/null | head -5

echo
echo "=== 9. 用户改过的系统文件（找 diff 线索） ==="
su_ ls -l /etc/systemd/system/ | head -30

echo
echo "=== 10. 板子上跑着的进程（谁该进固件、谁只是调试残留） ==="
ps -eo pid,user,etime,args --sort=start_time | grep -viE '\[|grep|ps -eo' | tail -25
