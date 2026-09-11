#!/bin/bash
# 启用 xone 驱动 + crypto 依赖（Razer Wolverine V3 Pro FF 支持）

KDIR="$1"  # kernel 根目录路径
DCONF="$(find "$KDIR" -name 'defconfig' | xargs grep -l 'joydev' 2>/dev/null | head -1)"

if [ -z "$DCONF" ]; then
    echo "ERROR: 未找到 defconfig"
    exit 1
fi

echo "编辑 $DCONF"

# 1. 注释/禁用 xpad（可选，若想保持 xpad 兼容性可不改）
sed -i 's/^CONFIG_JOYSTICK_XPAD=y/# CONFIG_JOYSTICK_XPAD is not set/' "$DCONF"

# 2. 启用 xone
sed -i 's/^# CONFIG_JOYSTICK_XONE_WIRED is not set/CONFIG_JOYSTICK_XONE_WIRED=y/' "$DCONF"
sed -i 's/^# CONFIG_JOYSTICK_XONE_WIRED_INPUT is not set/CONFIG_JOYSTICK_XONE_WIRED_INPUT=y/' "$DCONF"

# 3. 启用 crypto 依赖（ECDSA/ECDH/SHA256）
for opt in CRYPTO_ECDSA CRYPTO_ECDH CRYPTO_SHA256 CRYPTO_SHA512; do
    sed -i "s/^# $opt is not set/CONFIG_$opt=y/" "$DCONF"
done
sed -i 's/^CONFIG_CRC16=y/# CONFIG_CRC16 is not set/' "$DCONF"  # 避免冲突

echo "DONE: xone 启用成功"
grep -E 'XONE|XPAD|ECDSA|ECDH|SHA256' "$DCONF"