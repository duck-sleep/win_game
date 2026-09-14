#!/system/bin/sh
# 等手柄节点出现，再把 HapticXOut 转成 FF_RUMBLE。
# 不要 logcat -c：init 重启服务时会清空 logd，把正在读的 logcat 掐死，
# 服务跟着退、再拉、再 -c，死循环，手柄就不震。
# -T 1 已经只跟新日志，不回放 ring buffer。
# 不要 `exec logcat | ...`：exec 会让 init 把 logcat 当成主进程，谁清一次日志服务就挂。

BR=/vendor/bin/ff_bridge
[ -x "$BR" ] || BR=/data/local/tmp/ff_bridge
i=0
EV=""
while [ $i -lt 60 ]; do
    EV=$(grep -E 'Microsoft Xbox' -A6 /proc/bus/input/devices | grep -o 'event[0-9]*' | head -1)
    [ -n "$EV" ] && break
    i=$((i+1))
    sleep 2
done
[ -z "$EV" ] && EV=event5
chmod 666 /dev/input/$EV 2>/dev/null

logcat -T 1 -s HapticXOut:I | $BR /dev/input/$EV
