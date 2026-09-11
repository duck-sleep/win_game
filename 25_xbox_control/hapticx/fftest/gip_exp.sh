#!/system/bin/sh
# gip_exp.sh — 强制重枚举(归零 GIP 状态机) → unbind xpad → 自动 ack → 发包 → rebind
# 用法: gip_exp.sh [-a] <hex1> [hex2 ...]
ARGS=""
AUTO=""
for a in "$@"; do
    if [ "$a" = "-a" ]; then AUTO="-a"; else ARGS="$ARGS $a"; fi
done

echo 1-1.1:1.0 > /sys/bus/usb/drivers/xpad/unbind 2>/dev/null
echo 0 > /sys/bus/usb/devices/1-1.1/authorized
sleep 0.5
echo 1 > /sys/bus/usb/devices/1-1.1/authorized
sleep 1.5
echo 1-1.1:1.0 > /sys/bus/usb/drivers/xpad/unbind 2>/dev/null
sleep 0.5
D=""
i=0
while [ $i -lt 12 ]; do
    N=$(cat /sys/bus/usb/devices/1-1.1/devnum 2>/dev/null)
    for pad in "" "0" "00"; do
        C=/dev/bus/usb/001/$pad$N
        if [ -n "$N" ] && [ -e "$C" ]; then D=$C; break 2; fi
    done
    sleep 0.3
    i=$((i+1))
done
if [ -z "$D" ]; then echo "NODEV"; echo 1-1.1:1.0 > /sys/bus/usb/drivers/xpad/bind; exit 1; fi
echo DEV=$D
/data/local/tmp/sendgip $AUTO $D $ARGS
echo 1-1.1:1.0 > /sys/bus/usb/drivers/xpad/bind
