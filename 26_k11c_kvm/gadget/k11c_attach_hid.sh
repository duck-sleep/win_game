#!/bin/sh
# 把 HID(键盘/绝对鼠标/相对鼠标/厂商唤醒) + ACM 追加进 K11C 官方 rootfs 已有的 gadget
# —— 不抢 UDC、保留 ffs.adb，所以 USB shell 这条命脉一直在。
# 全部改的是 configfs（内存），重启即恢复原样，可反复试。
# 报文与属性照 jetkvm/kvm internal/usbgadget（见 ../port/PORTING.md）
#
# ⚠️ 顺序很重要：gadget 绑在 UDC 上时，configfs 会拒绝把 function 链进 config（EBUSY）。
#    所以必须 解绑 → 建 function + 链进 config → 再绑。
set -e

G=/sys/kernel/config/usb_gadget/rockchip
[ -d "$G" ] || { echo "找不到官方 gadget $G"; exit 1; }

wb() { # $1=文件 $2=空格分隔的 hex
	_o=""
	for _b in $2; do
		_d=$((0x$_b))
		_o="$_o\\$((_d / 64))$(((_d / 8) % 8))$((_d % 8))"
	done
	printf "$_o" >"$1"
}

KB='05 01 09 06 a1 01 05 07 19 e0 29 e7 15 00 25 01 75 01 95 08 81 02 95 01 75 08 81 03 95 05 75 01 05 08 19 01 29 05 91 02 95 01 75 03 91 03 95 06 75 08 15 00 25 ff 05 07 19 00 29 ff 81 00 c0'
ABS='05 01 09 02 a1 01 85 01 09 01 a1 00 05 09 19 01 29 05 15 00 25 01 75 01 95 05 81 02 95 01 75 03 81 03 05 01 09 30 09 31 16 00 00 26 ff 7f 36 00 00 46 ff 7f 75 10 95 02 81 02 c0 85 02 09 38 15 81 25 7f 35 00 45 00 75 08 95 01 81 06 05 0c 0a 38 02 15 81 25 7f 75 08 95 01 81 06 c0'
REL='05 01 09 02 a1 01 09 01 a1 00 05 09 19 01 29 08 15 00 25 01 95 08 75 01 81 02 05 01 09 30 09 31 09 38 15 81 25 7f 75 08 95 03 81 06 05 0c 0a 38 02 15 81 25 7f 75 08 95 01 81 06 c0 c0'
WAKE='06 00 ff 09 01 a1 01 15 00 26 ff 00 75 08 95 01 09 01 81 02 c0'

add_hid() { # n protocol subclass len no_out desc
	d="$G/functions/hid.usb$1"
	mkdir -p "$d"
	echo "$2" >"$d/protocol"
	echo "$3" >"$d/subclass"
	echo "$4" >"$d/report_length"
	echo "$5" >"$d/no_out_endpoint"
	# wakeup_on_write 是 JetKVM 那颗 5.10 的厂改属性，SDK 的 6.1 没有 → 跳过（远程唤醒暂不做）
	wb "$d/report_desc" "$6"
}

UDC=$(cat "$G/UDC")
[ -n "$UDC" ] || UDC=$(ls /sys/class/udc | head -1)

echo "1) 解绑 UDC（adb 会掉线几秒，属正常）"
echo "" >"$G/UDC"

echo "2) 建 function"
add_hid 0 1 1 8 0 "$KB"
add_hid 1 2 0 6 1 "$ABS"
add_hid 2 2 1 5 1 "$REL"
add_hid 3 0 0 1 1 "$WAKE"
mkdir -p "$G/functions/acm.usb0"

echo "3) 链进 config（这一步之前失败过：绑着 UDC 时 configfs 返 EBUSY）"
for f in hid.usb0 hid.usb1 hid.usb2 hid.usb3 acm.usb0; do
	[ -e "$G/configs/b.1/$f" ] || ln -s "$G/functions/$f" "$G/configs/b.1/$f"
done

echo "4) 重新绑定 $UDC"
echo "$UDC" >"$G/UDC"
sleep 2

echo "config 里的 function: $(ls "$G/configs/b.1" | grep -v '^\(bmAttributes\|MaxPower\|strings\)$' | tr '\n' ' ')"
echo "state=$(cat /sys/class/udc/$UDC/state)"
echo "节点: $(ls /dev/hidg* /dev/ttyGS0 2>&1 | tr '\n' ' ')"
