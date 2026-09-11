#!/system/bin/sh
# 板子侧执行：加载 xone 三件套，全部结果落盘，避免 adb 抖动丢输出
# 用法: adb shell sh /data/local/tmp/xone/insmod_xone_test.sh

LOG=/data/local/tmp/xone/result.txt
MODDIR=/data/local/tmp/xone

: > "$LOG"
echo "=== START $(date) ===" >> "$LOG"
echo "uname : $(uname -r)"       >> "$LOG"
echo "uptime: $(uptime)"         >> "$LOG"

setenforce 0 2>>"$LOG"
echo "selinux: $(getenforce)"    >> "$LOG"

dmesg -c > /dev/null 2>&1

for m in xone-gip.ko xone-gip-gamepad.ko xone-wired.ko; do
    echo "" >> "$LOG"
    echo "--- insmod $m ---" >> "$LOG"
    if [ ! -f "$MODDIR/$m" ]; then
        echo "MISSING FILE" >> "$LOG"
        continue
    fi
    insmod "$MODDIR/$m" 2>>"$LOG"
    echo "rc=$?" >> "$LOG"
    echo "  [dmesg tail]" >> "$LOG"
    dmesg 2>/dev/null | tail -25 | sed 's/^/  /' >> "$LOG"
done

echo "" >> "$LOG"
echo "--- lsmod ---" >> "$LOG"
lsmod 2>/dev/null | grep -iE "xone|xpad" >> "$LOG" 2>&1 || echo "(no xone/xpad)" >> "$LOG"

echo "" >> "$LOG"
echo "--- usb drivers ---" >> "$LOG"
ls /sys/bus/usb/drivers/ 2>/dev/null | grep -iE "xone|xpad" >> "$LOG" 2>&1 || echo "(no usb driver dir)" >> "$LOG"

echo "" >> "$LOG"
echo "--- uptime after ---" >> "$LOG"
uptime >> "$LOG"
echo "=== END ===" >> "$LOG"

cat "$LOG"
