#!/system/bin/sh
# Razer Wolverine V3 Pro (0x1532:0x0a3f) 手柄绑定脚本
# 依据 D:\win_game_project\12_win_上机跑\01_工程说明.md 编写
# 目标：xone.ko 完整接管，支持 FF 震动反馈

set -e

VID="0x1532"     # Razer VID
PID="0x0a3f"     # Wolverine V3 Pro (你们说的 "3f")
# PID_4C="0x1532:0x004c"  # 另一型号，若不需要可忽略

echo "[xone-bind] 开始绑定 Razer Wolverine V3 Pro ($VID:$PID)..."

# 1. insmod xone.ko （若是作为 .zip 包，路径自行改成 /vendor/ 或 /system/vendor/）
MOD_PATH="/vendor/lib/modules/xone.ko"
if [ ! -f "$MOD_PATH" ]; then
    # 也可能是 xone.ko 在 /system/lib/modules/ 或类似位置
    MOD_PATH=$(find /vendor /system -name "xone.ko" 2>/dev/null | head -1)
fi

if [ -f "$MOD_PATH" ]; then
    insmod "$MOD_PATH"
    echo "[xone-bind] xone.ko 加载成功"
else
    echo "[xone-bind] ERROR: 找不到 xone.ko，请确认刷机包已包含 xone 模块"
    exit 1
fi

# 2. 检查 xpad/c gamepad/hid 驱动是否抢占了我们 USB 手柄
# 如果看到 0x1532:0x0a3f 被 xpad/hid 等驱动绑定，就需要 unbind
echo "[xone-bind] 检查是否还被 xpad 抢占..."
FOR_DRIVER=$(grep -r "$PID" /sys/bus/hid/drivers/*/report_descriptor 2>/dev/null | head -1 | cut -d/ -f6)
if [ -n "$FOR_DRIVER" ]; then
    echo "[xone-bind] 检测到 $FOR_DRIVER 仍持有 $PID，进行 unbind..."
    DEV_PATH=$(grep -r "$PID" /sys/bus/hid/drivers/*/report_descriptor 2>/dev/null | head -1 | cut -d: -f1 | sed 's|/sys_bus/hid/drivers/[^/]*/[0-9a-f]*|/sys/bus/hid/drivers/'${FOR_DRIVER}'/unbind|')
    # 更稳妥的方式：遍历所有可能的驱动
    for driver in /sys/bus/hid/drivers/*; do
        DNAME=$(basename "$driver")
        if [ -d "$driver" ]; then
            for dev in "$driver"/*; do
                [ -e "$dev" ] || continue
                DEV_NAME=$(basename "$dev")
                if [[ "$DEV_NAME" == *"$PID"* ]] || grep -q "$PID" "$dev/../report_descriptor" 2>/dev/null; then
                    echo "[xone-bind] Unbinding $DEV_NAME from $DNAME ..."
                    echo "$DNAME $DEV_NAME" > "$driver/unbind" 2>/dev/null || true
                fi
            done
        fi
    done
else
    echo "[xone-bind] 未检测到 xpad 抢占，当前设备状态干净"
fi

# 3. 通过 /sys/bus/hid/drivers/xone/bind 让 xone 抢占手柄
# 或者通过 USB hidraw 方式发现 xone 接管
XONE_BIND="/sys/bus/hid/drivers/xone/bind"
if [ -d "$(dirname "$XONE_BIND")" ]; then
    # xone driver bind 格式是 "VID:PID"
    BIND_NAME="0000:0000:00$(printf '%x' $((0x${PID#0x})))"
    # 简单写法：直接写 "VID:PID"（具体格式看内核实际期望）
    echo "$VID:$PID" > "$XONE_BIND" 2>/dev/null && echo "[xone-bind] xone bind 成功" || echo "[xone-bind] bind 文件不存在或写入权限问题"
else
    echo "[xone-bind] xone driver 未加载，跳过 bind 步骤"
fi

# 4. 验证 FF 功能
echo
echo "[xone-bind] == 验证结果 =="
echo "[xone-bind] 检查 FF 设备:"
ls -la /dev/input/event* 2>/dev/null | head -8
echo ""
echo "[xone-bind] 检查 xpad/xone 输入设备:"
ls -la /sys/devices/platform/soc/*.ff 2>/dev/null || ls -la /sys/class/input/ | grep -i "ff\|joystick" | head -5
echo ""
echo "[xone-bind] 检查 hidraw 手柄:"
hidraw=$(ls /dev/hidraw* 2>/dev/null | head -1)
if [ -n "$hidraw" ]; then
    echo "发现 hidraw: $hidraw"
    echo "尝试读取设备描述:"
    printf "  " && cat "$hidraw../device/uevent" 2>/dev/null | grep NAME= || echo "  (无法读取描述)"
fi

echo
echo "[xone-bind] === 测试振动 ===
  测试方法参考 D:\win_game_project\12_win_上机跑\01_工程说明.md 中的 'xone test app' 部分
  推荐使用 evtest 或 adevtest 测试 FF 功能:
    evtest /dev/input/eventX   # 找到对应事件号后测试
  或从 Windows 侧运行 xone_test_app.exe 连设备测试"
echo
echo "DONE"