#!/bin/sh
# 最小可用 gadget：只有 键盘 + 绝对坐标鼠标（+ 可选 ACM），不带 adb、不带相对鼠标/唤醒。
# 目的：验两件事 —— (1) 端点够不够（少挂 function 后 mkdir 不再 ENODEV）
#              (2) Windows 能不能把它当复合设备拆开、认出键盘和鼠标
# 用法: sh k11c_min.sh [withacm]
set -e

GROOT=/sys/kernel/config/usb_gadget
G=$GROOT/k11cmin
ACM="${1:-}"

[ -d "$G" ] && { echo "先清掉上一次的 $G"; echo "" >"$G/UDC" 2>/dev/null || true; }

wb() {
	_o=""
	for _b in $2; do
		_d=$((0x$_b))
		_o="$_o\\$((_d / 64))$(((_d / 8) % 8))$((_d % 8))"
	done
	printf "$_o" >"$1"
}

KB='05 01 09 06 a1 01 05 07 19 e0 29 e7 15 00 25 01 75 01 95 08 81 02 95 01 75 08 81 03 95 05 75 01 05 08 19 01 29 05 91 02 95 01 75 03 91 03 95 06 75 08 15 00 25 ff 05 07 19 00 29 ff 81 00 c0'
ABS='05 01 09 02 a1 01 85 01 09 01 a1 00 05 09 19 01 29 05 15 00 25 01 75 01 95 05 81 02 95 01 75 03 81 03 05 01 09 30 09 31 16 00 00 26 ff 7f 36 00 00 46 ff 7f 75 10 95 02 81 02 c0 85 02 09 38 15 81 25 7f 35 00 45 00 75 08 95 01 81 06 05 0c 0a 38 02 15 81 25 7f 75 08 95 01 81 06 c0'

# 键盘要 OUT 端点（收 LED 指令），鼠标不要 → 省一个端点
mk_hid() { # n proto subclass len noout desc
	d="$G/functions/hid.usb$1"
	mkdir -p "$d"
	echo "$2" >"$d/protocol"
	echo "$3" >"$d/subclass"
	echo "$4" >"$d/report_length"
	echo "$5" >"$d/no_out_endpoint"
	wb "$d/report_desc" "$6"
	ln -s "$d" "$G/configs/b.1/hid.usb$1"
	echo "  建好 hid.usb$1"
}

mkdir -p "$G"
echo 0x1d6b >"$G/idVendor" # Linux Foundation，Windows 不会拿厂商驱动整台认领
echo 0x0104 >"$G/idProduct"
echo 0x0601 >"$G/bcdDevice"
echo 0x0200 >"$G/bcdUSB"
echo 0xEF >"$G/bDeviceClass" # misc
echo 0x02 >"$G/bDeviceSubClass"
echo 0x01 >"$G/bDeviceProtocol"

mkdir -p "$G/strings/0x409"
echo "KICKPI" >"$G/strings/0x409/manufacturer"
echo "K11C KVM HID" >"$G/strings/0x409/product"
echo "00000001" >"$G/strings/0x409/serialnumber"

mkdir -p "$G/configs/b.1/strings/0x409"
echo "k11c kvm" >"$G/configs/b.1/strings/0x409/configuration"
echo 500 >"$G/configs/b.1/MaxPower"

echo "建 function："
mk_hid 0 1 1 8 0 "$KB"
mk_hid 1 2 0 6 1 "$ABS"

if [ "$ACM" = "withacm" ]; then
	mkdir -p "$G/functions/acm.usb0"
	ln -s "$G/functions/acm.usb0" "$G/configs/b.1/acm.usb0"
	echo "  建好 acm.usb0"
fi

UDC=$(ls /sys/class/udc | head -1)
echo "$UDC" >"$G/UDC"
sleep 2
echo "UDC=$(cat "$G/UDC") state=$(cat /sys/class/udc/$UDC/state)"
echo "节点: $(ls /dev/hidg* /dev/ttyGS0 2>&1 | tr '\n' ' ')"
