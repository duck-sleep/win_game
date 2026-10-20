#!/bin/sh
# 出固件第 2 步（在编译 VM 上跑）：把 /tmp/k11c-rootfs 装进 SDK 的 ubuntu/overlay/。
#
#   --dry   只列出会写成什么样、落在哪，不动任何文件（默认）
#   --go    真的写进 overlay（root 属主按目标路径改好），仍然不编译、不动 binary
#
# 为什么是 overlay 而不是直接改 binary/：mk-rootfs-noble.sh 每次构建先
# rm -rf binary、从 ubuntu-rootfs.img 整份拷出来，再 sudo cp -rpf overlay/* binary/。
# 只有 overlay 里的东西能活过下一次构建。
set -e
SDK=$HOME/k11c/rk-linux6.1-2026091606
SRC=/tmp/k11c-rootfs
OV=$SDK/ubuntu/overlay
MODE=${1:---dry}

export SUDO_ASKPASS=/tmp/.rk_ap.sh
printf '#!/bin/sh\necho %s\n' "${RK_SUDO:?用 RK_SUDO=... 传 VM 的 sudo 口令}" > "$SUDO_ASKPASS"
chmod 700 "$SUDO_ASKPASS"
PATH=/tmp/.rk_sudo_bin:$PATH
mkdir -p /tmp/.rk_sudo_bin
printf '#!/bin/sh\nexec /usr/bin/sudo -A "$@"\n' > /tmp/.rk_sudo_bin/sudo
chmod 700 /tmp/.rk_sudo_bin /tmp/.rk_sudo_bin/sudo

echo "=== overlay 现状（会被覆盖的同名文件） ==="
sudo -A find "$OV" \( -name 'k11c*' -o -name '90-NM*' -o -path '*ttyGS0*' -o -path '*autostart*' \) \
     -printf '%M %u:%g %p\n' 2>/dev/null | sort | head -20

echo
echo "=== 将要落进 overlay 的文件（属主按目标改：etc/opt/usr 归 root，home/kickpi 归 1000） ==="
cd "$SRC"
find . \( -type f -o -type l \) -printf '%y %M %p\n' | sort | sed 's#^\(.\) \(.\{9\}\) ./#  \2  #'

echo
echo "=== 开机自启（VM 侧建软链） ==="
[ -f "$SRC/enable.txt" ] && sed 's/^/  enable: /; $!s/$/.service/' "$SRC/enable.txt"
[ -f "$SRC/default.txt" ] && echo "  default.target -> $(cat "$SRC/default.txt")"

[ "$MODE" = "--dry" ] && { echo; echo "（--dry：没动任何文件。要真写：RK_SUDO=xxx sh fw_install.sh --go）"; rm -rf "$SUDO_ASKPASS" /tmp/.rk_sudo_bin; exit 0; }

echo
echo "=== 写入 overlay ==="
sudo -A mkdir -p "$OV/opt/k11c-kvm" "$OV/home/kickpi" "$OV/etc/systemd/system/multi-user.target.wants"
# 软链在这里建（本机 Git Bash 建出来的 ln -s 是普通文件，不能带过来）
while read -r u; do
  [ -n "$u" ] || continue
  sudo -A ln -sfn "../$u.service" "$SRC/etc/systemd/system/multi-user.target.wants/$u.service"
  echo "  enable: $u.service"
done < "$SRC/enable.txt"
if [ -f "$SRC/default.txt" ]; then
  D=$(cat "$SRC/default.txt")
  sudo -A mkdir -p "$SRC/etc/systemd/system"
  sudo -A ln -sfn "/lib/systemd/system/$D" "$SRC/etc/systemd/system/default.target"
  echo "  default.target -> $D"
fi
# 官方 usb-gadget.service 会在 Type-C 上挂 adb(2207:0006)，Windows 会把整台按硬件 ID 认领成安卓设备，
# HID 接口就此消失 —— 必须 mask。现在这条只活在 ubuntu-rootfs.img 里，写进 overlay 才能只靠 SDK 树复现。
sudo -A mkdir -p "$SRC/etc/systemd/system"
sudo -A ln -sfn /dev/null "$SRC/etc/systemd/system/usb-gadget.service"
echo "  mask: usb-gadget.service -> /dev/null"
# 清单文件本身不进镜像
sudo -A rm -f "$SRC/enable.txt" "$SRC/default.txt"
# 属主：整棵树先归 root，home 下那份归 kickpi(1000)
sudo -A chown -R 0:0 "$SRC"
sudo -A chown -R 1000:1000 "$SRC/home/kickpi"
sudo -A chmod 600 "$SRC/etc/netplan/90-NM-k11c.yaml" "$SRC/home/kickpi/.ssh/authorized_keys"
sudo -A cp -rpf "$SRC/." "$OV/"
# cp -rpf 不跨目录改已存在文件的属主，这里再兜一次
sudo -A chown -R 0:0 "$OV/opt/k11c-kvm" "$OV/usr/local/sbin/k11c-gadget.sh" "$OV/etc/systemd/system" "$OV/etc/netplan"
sudo -A chown -R 1000:1000 "$OV/home/kickpi"

echo "=== 写完后 overlay 里的 k11c 相关条目 ==="
sudo -A find "$OV" \( -iname '*k11c*' -o -name '90-NM*' -o -path '*ttyGS0*' -o -name 'default.target' \) \
     -printf '%y %M %u:%g %10s %p\n' | sort

rm -rf "$SUDO_ASKPASS" /tmp/.rk_sudo_bin
echo "=== 完成（overlay 已更新；编译与打包还没跑） ==="
