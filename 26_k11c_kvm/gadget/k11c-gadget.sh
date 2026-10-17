#!/bin/sh
# K11C IP-KVM 的 USB gadget 装配脚本（开机由 k11c-gadget.service 调用）
#
# 结论都来自 2026-10-17 的上板实测：
#   · 沿用官方 VID:PID(2207:0006) 时，Windows 上装过的 Android 驱动会按硬件 ID 把
#     复合设备的父节点整台认领，其它接口根本不拆开枚举 → 必须用自己的 VID:PID
#   · bDeviceClass 要写 EF/02/01（misc），Windows 才会建 "USB Composite Device" 并分子接口
#   · gadget 已绑在 UDC 上时 configfs 拒绝把 function 链进 config(EBUSY) → 顺序：解绑→建→绑
#   · 这个内核(6.1)的 hid function 没有 wakeup_on_write 属性（那是 JetKVM 5.10 的厂改）
#   · 只挂 键盘 + 绝对鼠标 + ACM：够用，且给以后留端点余量
set -e

GROOT=/sys/kernel/config/usb_gadget
G=$GROOT/k11c
NAME=k11c

# 等 UDC 出现（DWC3 是内建的，一般开机很早就有）
i=0
while [ ! -d /sys/class/udc ] || [ -z "$(ls /sys/class/udc 2>/dev/null)" ]; do
	i=$((i + 1)); [ $i -gt 50 ] && { echo "no udc"; exit 1; }
	sleep 0.2
done
UDC=$(ls /sys/class/udc | grep fcc00000 | head -1)
[ -n "$UDC" ] || UDC=$(ls /sys/class/udc | head -1)

# 抢 UDC：把任何已绑定的 gadget 先解绑（官方的也解，它的 adb 我们不用）
for g in "$GROOT"/*; do
	[ -d "$g" ] || continue
	[ -n "$(cat "$g/UDC" 2>/dev/null)" ] && echo "" >"$g/UDC" || true
done
[ -d "$G" ] && rm -rf "$G" 2>/dev/null || true
sleep 1

# 十六进制串 → 原始字节（只用 printf 的八进制转义，dash/busybox 都吃）
wb() {
	_o=""
	for _b in $2; do
		_d=$((0x$_b))
		_o="$_o\\$((_d / 64))$(((_d / 8) % 8))$((_d % 8))"
	done
	printf "$_o" >"$1"
}

# report descriptor 照 jetkvm/kvm internal/usbgadget（GPL-2.0，自用不分发；见 port/PORTING.md）
KB='05 01 09 06 a1 01 05 07 19 e0 29 e7 15 00 25 01 75 01 95 08 81 02 95 01 75 08 81 03 95 05 75 01 05 08 19 01 29 05 91 02 95 01 75 03 91 03 95 06 75 08 15 00 25 ff 05 07 19 00 29 ff 81 00 c0'
ABS='05 01 09 02 a1 01 85 01 09 01 a1 00 05 09 19 01 29 05 15 00 25 01 75 01 95 05 81 02 95 01 75 03 81 03 05 01 09 30 09 31 16 00 00 26 ff 7f 36 00 00 46 ff 7f 75 10 95 02 81 02 c0 85 02 09 38 15 81 25 7f 35 00 45 00 75 08 95 01 81 06 05 0c 0a 38 02 15 81 25 7f 75 08 95 01 81 06 c0'

mk_hid() { # n proto subclass len noout desc
	d="$G/functions/hid.usb$1"
	mkdir -p "$d"
	echo "$2" >"$d/protocol"
	echo "$3" >"$d/subclass"
	echo "$4" >"$d/report_length"
	echo "$5" >"$d/no_out_endpoint"
	wb "$d/report_desc" "$6"
	ln -s "$d" "$G/configs/b.1/hid.usb$1"
}

mkdir -p "$G/strings/0x409" "$G/configs/b.1/strings/0x409"
echo 0x1d6b >"$G/idVendor" # Linux Foundation 通用 VID，避免撞任何厂商驱动
echo 0x0104 >"$G/idProduct"
echo 0x0601 >"$G/bcdDevice"
echo 0x0200 >"$G/bcdUSB"
echo 0xEF >"$G/bDeviceClass"
echo 0x02 >"$G/bDeviceSubClass"
echo 0x01 >"$G/bDeviceProtocol"
echo "KICKPI" >"$G/strings/0x409/manufacturer"
echo "K11C KVM" >"$G/strings/0x409/product"
# serialnumber 必须非空：iSerialNumber 指向一个空字符串会让主机读串描述符时失败，
# 枚举停在 SET_ADDRESS 之后（2026-10-17 上板实测就是这个）。
# 注意不能用 `cat ... | tr ... >file || echo 兜底` —— 管道返回的是 tr 的 0，兜底永不触发，
# 而这颗 RK3566 的 dwc3 根本没有 /sys/class/udc/*/mac_address，结果写进去的就是空串。
SER=$(cat /sys/class/udc/"$UDC"/mac_address 2>/dev/null | tr -d ':\n-')
[ -n "$SER" ] || SER=$(cat /sys/class/net/end1/address /sys/class/net/eth0/address 2>/dev/null | head -1 | tr -d ':\n-')
[ -n "$SER" ] || SER=00000001
echo "$SER" >"$G/strings/0x409/serialnumber"
echo "k11c kvm hid+acm" >"$G/configs/b.1/strings/0x409/configuration"
echo 500 >"$G/configs/b.1/MaxPower"

mk_hid 0 1 1 8 0 "$KB"      # 键盘：boot protocol，8 字节，带 OUT 端点收 LED
mk_hid 1 2 0 6 1 "$ABS"     # 绝对坐标鼠标：Report ID 1 = Pointer/Absolute，0-32767

mkdir -p "$G/functions/acm.usb0"
ln -s "$G/functions/acm.usb0" "$G/configs/b.1/acm.usb0"   # /dev/ttyGS0 = 不依赖网络的自救通道

echo "$UDC" >"$G/UDC"
echo "k11c gadget up: udc=$UDC state=$(cat /sys/class/udc/$UDC/state) hid=$(ls /dev/hidg* 2>/dev/null | tr '\n' ' ')"
