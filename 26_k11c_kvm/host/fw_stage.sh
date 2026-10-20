#!/bin/sh
# 出固件第 1 步：把"板上验证过的东西"拼成一棵 rootfs 覆盖树，推到编译 VM。
#
# 为什么是这个方向：SDK 的 ubuntu/mk-rootfs-noble.sh 每次构建都会
#   rm -rf binary → 从 ubuntu-rootfs.img 整份拷出来 → 再 sudo cp -rpf overlay/* binary/
# 所以**只有放进 ubuntu/overlay/ 的东西才活得下来**，直接改 binary/ 会被下一次构建冲掉。
#
# 用法：sh host/fw_stage.sh [--appliance]
#   默认 = 桌面形态（保留 lightdm，电视靠 autostart 的 tv.sh）
#   --appliance = 产品形态（multi-user，没有桌面；电视由 k11c-fakevo.service 直出）
# 只读板上、只往 VM 的 /tmp 写，不动 binary、不动镜像、不编译。
set -e
BOARD=${BOARD:-kickpi@192.168.31.89}
VM=${VM:-rk-vm}
APPLIANCE=0
[ "$1" = "--appliance" ] && APPLIANCE=1

SUDO=${K11C_SUDO:-kickpi}
REPO=$(cd "$(dirname "$0")/.." && pwd)      # 26_k11c_kvm
OUT=$REPO/build/rootfs
rm -rf "$REPO/build"
mkdir -p "$OUT"/opt/k11c-kvm/www "$OUT"/opt/k11c-kvm/vo \
         "$OUT"/usr/local/sbin "$OUT"/etc/systemd/system/multi-user.target.wants \
         "$OUT"/etc/netplan "$OUT"/home/kickpi/.config/autostart "$OUT"/home/kickpi/.ssh

echo "=== 1. 从板子上拉（只有板上有的） ==="
b() { printf '%s\n' "$SUDO" | ssh -T "$BOARD" "sudo -S sh -c '$1'"; }
ssh "$BOARD" 'cp -a /opt/k11c-kvm/vo/fakevo /tmp/fakevo.bin 2>/dev/null' || true
scp -q "$BOARD":/tmp/fakevo.bin "$OUT/opt/k11c-kvm/vo/fakevo"
# 底图和字形表：fakevo 开机就要读，缺一个它就起不来
scp -q "$BOARD":/opt/k11c-kvm/vo/bars_nv12.yuv "$BOARD":/opt/k11c-kvm/vo/glyphs.gray "$OUT/opt/k11c-kvm/vo/"
b 'cat /etc/netplan/90-NM-*.yaml'            > "$OUT/etc/netplan/90-NM-k11c.yaml"
b 'cat /etc/systemd/system/serial-getty@ttyGS0.service.d/autologin.conf' \
                                             > "$OUT/etc/systemd/system/serial-getty-autologin.conf.tmp"
ssh "$BOARD" 'cat ~/.ssh/authorized_keys'    > "$OUT/home/kickpi/.ssh/authorized_keys"
for f in onboard.desktop onboard-autostart.desktop xfce4-screensaver.desktop; do
  ssh "$BOARD" "cat ~/.config/autostart/$f" > "$OUT/home/kickpi/.config/autostart/$f"
done

echo "=== 2. 从 repo 拷（源码为准，板上同名文件只做核对） ==="
cp -a "$REPO"/board/kvm_server.py "$REPO"/board/fakesrc.sh "$REPO"/board/run.sh "$REPO"/board/tv.sh "$OUT/opt/k11c-kvm/"
cp -a "$REPO"/board/www/index.html "$REPO"/board/www/webrtc.html "$REPO"/board/www/probe.html "$OUT/opt/k11c-kvm/www/"
cp -a "$REPO"/board/vo/fakevo.c "$REPO"/board/vo/mkassets.sh "$OUT/opt/k11c-kvm/vo/"
cp -a "$REPO"/board/k11c-kvm.service "$REPO"/board/k11c-fakevo.service "$REPO"/board/k11c-gw.service \
    "$REPO"/systemd/k11c-gadget.service "$OUT/etc/systemd/system/"
cp -a "$REPO"/gadget/k11c-gadget.sh "$OUT/usr/local/sbin/"
cp -a "$REPO"/host/k11c-gw "$OUT/opt/k11c-kvm/k11c-gw"
[ "$APPLIANCE" = 1 ] || cp -a "$REPO"/board/k11c-tv.desktop "$OUT/home/kickpi/.config/autostart/"

echo "=== 3. 开机自启清单（软链由 VM 那边建：Git Bash 的 ln -s 建出来是普通文件，不能用） ==="
if [ "$APPLIANCE" = 1 ]; then
  printf '%s\n' k11c-gadget k11c-fakevo k11c-gw k11c-kvm > "$OUT/enable.txt"
  echo multi-user.target > "$OUT/default.txt"
else
  printf '%s\n' k11c-gadget k11c-kvm > "$OUT/enable.txt"
fi

echo "=== 4. 权限（overlay 是 cp -rpf，这里定的属主/模就是镜像里的） ==="
chmod 755 "$OUT/opt/k11c-kvm" "$OUT/opt/k11c-kvm/vo" "$OUT/opt/k11c-kvm/www" "$OUT/usr/local/sbin"
chmod 644 "$OUT"/etc/systemd/system/*.service "$OUT"/opt/k11c-kvm/*.sh "$OUT"/opt/k11c-kvm/kvm_server.py
chmod 755 "$OUT"/opt/k11c-kvm/k11c-gw "$OUT"/opt/k11c-kvm/vo/fakevo "$OUT"/usr/local/sbin/k11c-gadget.sh
chmod 644 "$OUT"/opt/k11c-kvm/vo/*.yuv "$OUT"/opt/k11c-kvm/vo/*.gray "$OUT"/opt/k11c-kvm/www/*.html
chmod 600 "$OUT"/etc/netplan/90-NM-k11c.yaml "$OUT"/home/kickpi/.ssh/authorized_keys
# ttyGS0 自动登录：VM 那边按目录名再落位
mkdir -p "$OUT/etc/systemd/system/serial-getty@ttyGS0.service.d"
mv "$OUT/etc/systemd/system/serial-getty-autologin.conf.tmp" \
   "$OUT/etc/systemd/system/serial-getty@ttyGS0.service.d/autologin.conf"

echo "=== 5. 核对：repo 版 vs 板上跑的版本 ==="
for f in kvm_server.py www/index.html; do
  a=$(md5sum < "$OUT/opt/k11c-kvm/$f" | cut -d" " -f1)
  bb=$(ssh "$BOARD" "md5sum /opt/k11c-kvm/$f" | cut -d" " -f1)
  [ "$a" = "$bb" ] && echo "  同  $f" || echo "  ≠  $f  repo=$a 板上=$bb（以 repo 为准）"
done

echo "=== 6. 推到 VM 的 /tmp/k11c-rootfs（还没进 overlay） ==="
ssh "$VM" 'rm -rf /tmp/k11c-rootfs'
ssh "$VM" 'mkdir -p /tmp/k11c-rootfs'
tar -cf - -C "$OUT" . | ssh "$VM" 'tar -xf - -C /tmp/k11c-rootfs'
scp -q "$REPO/host/fw_install.sh" "$VM":/tmp/fw_install.sh
echo
echo "下一步（在 VM 上看清单，不动文件）："
echo "  ssh $VM 'RK_SUDO=<VM 的 sudo 口令> sh /tmp/fw_install.sh --dry'"
echo "确认无误后："
echo "  ssh $VM 'RK_SUDO=<VM 的 sudo 口令> sh /tmp/fw_install.sh --go'"
