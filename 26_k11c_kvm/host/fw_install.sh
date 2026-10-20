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
sudo -A cp -rpf "$SRC/." "$OV/"
sudo -A rm -f "$OV/enable.txt" "$OV/default.txt"

# 属主/模**只在 overlay 那边定**，不碰暂存树：上一版在这里 chown -R 0:0 $SRC，
# 结果下次 fw_stage.sh 的 rm -rf /tmp/k11c-rootfs 直接 Permission denied，
# 暂存树变成半旧的根属主残留 —— 症状是清单文件"莫名丢失"、.ssh 目录没推上去。
sudo -A chown -R 0:0 "$OV/opt/k11c-kvm" "$OV/usr/local/sbin/k11c-gadget.sh" \
                   "$OV/etc/systemd/system" "$OV/etc/netplan"
sudo -A chown -R 1000:1000 "$OV/home/kickpi"
sudo -A chmod 700 "$OV/home/kickpi/.ssh"
sudo -A chmod 600 "$OV/etc/netplan/90-NM-k11c.yaml" "$OV/home/kickpi/.ssh/authorized_keys"
# 两个二进制必须可执行：它们在 Windows 侧是 scp 拉回来的普通文件（644），本机 chmod 没保住。
# mkfs.ext4 -d 会把模原样带进镜像，644 的话开机服务直接 status=203/EXEC。
sudo -A chmod 755 "$OV/opt/k11c-kvm/k11c-gw" "$OV/opt/k11c-kvm/vo/fakevo" "$OV/opt/k11c-kvm/vo"

# 软链直接建在 overlay 里（Git Bash 的 ln -s 建出来是普通文件，不能带过来）
while read -r u; do
  [ -n "$u" ] || continue
  sudo -A ln -sfn "../$u.service" "$OV/etc/systemd/system/multi-user.target.wants/$u.service"
  echo "  enable: $u.service"
done < "$SRC/enable.txt"
if [ -s "$SRC/default.txt" ]; then
  sudo -A ln -sfn "/lib/systemd/system/$(cat "$SRC/default.txt")" "$OV/etc/systemd/system/default.target"
  echo "  default.target -> $(cat "$SRC/default.txt")"
fi
# 官方 usb-gadget.service 会在 Type-C 上挂 adb(2207:0006)，Windows 按硬件 ID 把整台认领成安卓设备，
# HID 接口就此消失 —— 必须 mask。这条以前只活在 ubuntu-rootfs.img 里，写进 overlay 才能只靠 SDK 树复现。
sudo -A ln -sfn /dev/null "$OV/etc/systemd/system/usb-gadget.service"
echo "  mask: usb-gadget.service -> /dev/null"

echo "=== 写完后核对（这两个二进制的 x 位是重点） ==="
sudo -A ls -l "$OV/opt/k11c-kvm/k11c-gw" "$OV/opt/k11c-kvm/vo/fakevo" \
     "$OV/opt/k11c-kvm/vo/bars_nv12.yuv" "$OV/opt/k11c-kvm/vo/glyphs.gray" \
     "$OV/usr/local/sbin/k11c-gadget.sh" "$OV/etc/netplan/90-NM-k11c.yaml" \
     "$OV/home/kickpi/.ssh/authorized_keys"
sudo -A find "$OV/etc/systemd/system" \( -iname 'k11c*' -o -name 'default.target' \
     -o -name 'usb-gadget.service' -o -path '*ttyGS0*' \) -printf '%y %M %u:%g %p\n' | sort

rm -rf "$SUDO_ASKPASS" /tmp/.rk_sudo_bin
echo "=== 完成（overlay 已更新；编译与打包还没跑） ==="
