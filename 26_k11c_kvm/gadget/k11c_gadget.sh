#!/bin/sh
# K11C USB 设备端（gadget）装配脚本：键盘 + 绝对坐标鼠标 + 相对鼠标 + 唤醒 + ACM 控制台
# report descriptor 与属性值照抄 jetkvm/kvm 的 internal/usbgadget/*（见方案文档 §2-Q18-A）
# 用法: k11c_gadget.sh start | stop | status
# 需要 root（configfs 挂在 /sys/kernel/config）

set -e

GROOT=/sys/kernel/config/usb_gadget
NAME=k11c
DIR=$GROOT/$NAME

# JetKVM 在 RV1106 上读 /sys/devices/platform/usbdrd —— RK3566 的节点名不一样，
# 这里直接取 /sys/class/udc 下第一个（RK3566 上应为 fcc00000.usb，即 DRD 那一路）。
pick_udc() {
	for u in /sys/class/udc/*; do
		[ -e "$u" ] || { echo ""; return; }
		case "$(basename "$u")" in
		*fcc00000*) basename "$u"; return ;;
		esac
	done
	for u in /sys/class/udc/*; do [ -e "$u" ] && { basename "$u"; return; }; done
	echo ""
}

# 空格分隔的十六进制 → 原始字节。
# 只用 printf 格式串里的 \ooo 八进制转义（POSIX 保证），因为板子上是 busybox ash，
# \xHH 这类扩展不能指望。
wbytes() { # $1=文件 $2=hex
	_out=""
	for _b in $2; do
		_d=$((0x$_b))
		_out="$_out\\$((_d / 64))$(((_d / 8) % 8))$((_d % 8))"
	done
	printf "$_out" >"$1"
}

KB_DESC='05 01 09 06 a1 01 05 07 19 e0 29 e7 15 00 25 01 75 01 95 08 81 02 95 01 75 08 81 03 95 05 75 01 05 08 19 01 29 05 91 02 95 01 75 03 91 03 95 06 75 08 15 00 25 ff 05 07 19 00 29 ff 81 00 c0'
ABS_DESC='05 01 09 02 a1 01 85 01 09 01 a1 00 05 09 19 01 29 05 15 00 25 01 75 01 95 05 81 02 95 01 75 03 81 03 05 01 09 30 09 31 16 00 00 26 ff 7f 36 00 00 46 ff 7f 75 10 95 02 81 02 c0 85 02 09 38 15 81 25 7f 35 00 45 00 75 08 95 01 81 06 05 0c 0a 38 02 15 81 25 7f 75 08 95 01 81 06 c0'
REL_DESC='05 01 09 02 a1 01 09 01 a1 00 05 09 19 01 29 08 15 00 25 01 95 08 75 01 81 02 05 01 09 30 09 31 09 38 15 81 25 7f 75 08 95 03 81 06 05 0c 0a 38 02 15 81 25 7f 75 08 95 01 81 06 c0 c0'
WAKE_DESC='06 00 ff 09 01 a1 01 15 00 26 ff 00 75 08 95 01 09 01 81 02 c0'

mk_hid() { # $1=hid.usbN $2=protocol $3=subclass $4=report_length $5=no_out $6=wakeup $7=desc
	d=$DIR/functions/$1
	mkdir -p "$d"
	echo "$2" >"$d/protocol"
	echo "$3" >"$d/subclass"
	echo "$4" >"$d/report_length"
	echo "$5" >"$d/no_out_endpoint"
	echo "$6" >"$d/wakeup_on_write"
	wbytes "$d/report_desc" "$7"
	ln -s "$d" "$DIR/configs/b.1/$1" 2>/dev/null || true
}

do_start() {
	mkdir -p "$DIR"

	echo 0x1d6b >"$DIR/idVendor" # Linux Foundation 的通用 VID，将来可换成自己的
	echo 0x0104 >"$DIR/idProduct"
	echo 0x0601 >"$DIR/bcdDevice"
	echo 0x0200 >"$DIR/bcdUSB"
	echo 0xEF >"$DIR/bDeviceClass"
	echo 0x02 >"$DIR/bDeviceSubClass"
	echo 0x01 >"$DIR/bDeviceProtocol"

	mkdir -p "$DIR/strings/0x409"
	echo "KICKPI K11C" >"$DIR/strings/0x409/manufacturer"
	echo "K11C HID + CDC-ACM" >"$DIR/strings/0x409/product"
	echo "000001" >"$DIR/strings/0x409/serialnumber"

	mkdir -p "$DIR/configs/b.1/strings/0x409"
	echo "HID keyboard+mouse, ACM console" >"$DIR/configs/b.1/strings/0x409/configuration"
	echo 500 >"$DIR/configs/b.1/MaxPower"

	# 顺序照 JetKVM：0 键盘 → 1 绝对鼠标 → 2 相对鼠标 → 3 唤醒
	mk_hid hid.usb0 1 1 8 0 0 "$KB_DESC"
	mk_hid hid.usb1 2 0 6 1 0 "$ABS_DESC"
	mk_hid hid.usb2 2 1 5 1 0 "$REL_DESC"
	mk_hid hid.usb3 0 0 1 1 1 "$WAKE_DESC"

	mkdir -p "$DIR/functions/acm.usb0"
	ln -s "$DIR/functions/acm.usb0" "$DIR/configs/b.1/acm.usb0" 2>/dev/null || true

	UDC=$(pick_udc)
	[ -n "$UDC" ] || { echo "找不到 UDC：/sys/class/udc 是空的（dr_mode 没进 device？见 §2-Q2）" >&2; exit 1; }
	echo "$UDC" >"$DIR/UDC"
	echo "started: UDC=$UDC  设备节点: $(ls /dev/hidg* 2>/dev/null | tr '\n' ' ')"
	echo "ACM 控制台: $(ls -l /dev/ttyGS0 2>/dev/null || echo '还没出现')"
}

do_stop() {
	[ -d "$DIR" ] || { echo "没在跑"; exit 0; }
	[ -e "$DIR/UDC" ] && echo >"$DIR/UDC" || true
	for l in "$DIR"/configs/b.1/*; do [ -L "$l" ] && rm -f "$l"; done
	for f in "$DIR"/functions/*; do [ -e "$f" ] && rmdir "$f" 2>/dev/null || true; done
	rmdir "$DIR"/configs/b.1/strings/0x409 "$DIR"/configs/b.1 "$DIR"/strings/0x409 "$DIR"/configs "$DIR" 2>/dev/null || true
	echo "stopped"
}

do_status() {
	echo "--- /sys/class/udc ---"
	for u in /sys/class/udc/*; do
		[ -e "$u" ] || { echo "(空)"; break; }
		echo "$(basename "$u") state=$(cat "$u/state") speed=$(cat "$u/current_speed" 2>/dev/null)"
	done
	echo "--- gadget ---"
	[ -d "$DIR" ] && { echo "UDC=$(cat "$DIR/UDC" 2>/dev/null)"; ls -l /dev/hidg* /dev/ttyGS0 2>/dev/null; } || echo "未装配"
}

case "${1:-}" in
start) do_start ;;
stop) do_stop ;;
restart)
	do_stop
	do_start
	;;
status) do_status ;;
*) echo "用法: $0 start|stop|restart|status" >&2; exit 2 ;;
esac
