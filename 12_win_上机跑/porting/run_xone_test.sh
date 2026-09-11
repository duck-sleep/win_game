#!/system/bin/sh
# 板子侧执行：降级 panic 策略 + 对照组二分定位，全程落盘抗 adb/USB 抖动
# 结果写 /data/local/tmp/xone/result.txt，即使板子重启也在 data 分区保留

DIR=/data/local/tmp/xone
LOG=$DIR/result.txt
: > "$LOG"
say() { echo "$1" >> "$LOG"; }

say "=== START $(date) ==="
say "uname : $(uname -r)"
say "uptime: $(uptime)"

# [0] 降级 panic 策略：让 oops/WARN 只杀进程，不触发整机重启
echo 0 > /proc/sys/kernel/panic_on_oops 2>>"$LOG" && say "panic_on_oops -> 0 OK" || say "panic_on_oops 不可写"
echo 0 > /proc/sys/kernel/panic_on_rcu_stall 2>>"$LOG" && say "panic_on_rcu_stall -> 0 OK" || say "rcu_stall 不可写"
echo 0 > /proc/sys/kernel/panic_on_taint 2>>"$LOG" && say "panic_on_taint -> 0 OK" || say "taint 不可写"

# [1] SELinux 放行
setenforce 0 2>>"$LOG"
say "selinux: $(getenforce)"

dmesg -c > /dev/null 2>&1

# [2] 对照组：hello.ko（纯 printk，不碰任何子系统）
say ""
say "########## STEP A: hello.ko (对照组) ##########"
insmod $DIR/hello.ko 2>>"$LOG"; say "hello rc=$?"
sync
dmesg 2>/dev/null | grep -iE "XONE_TEST|hello|disagrees|signature|CFI|Unknown symbol" | tail -10 | sed 's/^/  A> /' >> "$LOG"
sync
rmmod hello 2>/dev/null; sync

# [3] 被测：xone-gip.ko（基础模块，不注册 USB 驱动，最安全）
say ""
say "########## STEP B: xone-gip.ko ##########"
insmod $DIR/xone-gip.ko 2>>"$LOG"; say "gip rc=$?"
sync
dmesg 2>/dev/null | tail -15 | sed 's/^/  B> /' >> "$LOG"
sync

# [4] gamepad
say ""
say "########## STEP C: xone-gip-gamepad.ko ##########"
insmod $DIR/xone-gip-gamepad.ko 2>>"$LOG"; say "gamepad rc=$?"
sync
dmesg 2>/dev/null | tail -10 | sed 's/^/  C> /' >> "$LOG"
sync

# [5] wired（真正注册 USB 驱动，最可能触发问题）
say ""
say "########## STEP D: xone-wired.ko ##########"
insmod $DIR/xone-wired.ko 2>>"$LOG"; say "wired rc=$?"
sync
dmesg 2>/dev/null | tail -15 | sed 's/^/  D> /' >> "$LOG"
sync

# [6] 最终状态
say ""
say "########## FINAL STATE ##########"
say "-- lsmod --"
lsmod 2>/dev/null | grep -iE "xone|hello" >> "$LOG"
say "-- usb driver dirs --"
ls /sys/bus/usb/drivers/ 2>/dev/null | grep -iE "xone|xpad" >> "$LOG"
say "-- gip bus --"
ls /sys/bus/gip/ 2>/dev/null >> "$LOG" || say "(no gip bus)"
say "-- dmesg 全量含 xone/gip --"
dmesg 2>/dev/null | grep -iE "xone|gip" | tail -25 | sed 's/^/  /' >> "$LOG"
say ""
say "=== END $(date) uptime=$(uptime) ==="
sync
