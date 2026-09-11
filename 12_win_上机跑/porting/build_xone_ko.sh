#!/bin/bash
# 单独编 xone 模块 .ko（独立 O 目录，不碰主编译 out/）
# 前置：crypto.c 的 err 未初始化补丁已打在 msm-kernel 树
set -e

KP=/home/laide/Desktop/10_code/LA.VENDOR.15.4.3/kernel_platform
OUT=/tmp/xone_test_build

rm -rf "$OUT"
mkdir -p "$OUT"

# 复用主编译 GKI common 的 .config（已答完所有 NEW 符号，非交互）
cp "$KP/out/msm-kernel-kalama-consolidate/gki_kernel/common/.config" "$OUT/.config"

# 追加 xone 模块 + crypto 依赖（全 =m，独立于主编译）
cat >> "$OUT/.config" << 'CFGEOF'
CONFIG_JOYSTICK_XONE_WIRED=m
CONFIG_JOYSTICK_XONE_WIRED_INPUT=m
CONFIG_INPUT_FF_MEMLESS=m
CONFIG_CRYPTO=y
CONFIG_CRYPTO_ECC=y
CONFIG_CRYPTO_ECDSA=y
CONFIG_CRYPTO_ECDH=y
CONFIG_CRYPTO_SHA256=y
CFGEOF

cd "$KP/msm-kernel"
export PATH="$KP/prebuilts/clang/host/linux-x86/clang-r450784e/bin:$KP/prebuilts/build-tools/linux-x86/bin:$PATH"

make O="$OUT" ARCH=arm64 LLVM=1 olddefconfig > /tmp/xone_prep.log 2>&1

echo "=== build xone .ko ==="
make O="$OUT" ARCH=arm64 LLVM=1 -j6 M=drivers/input/joystick/xone modules 2>&1 | tee /tmp/xone_cc.log | tail -25

echo "--- RESULT ---"
if ls "$OUT"/drivers/input/joystick/xone/*.ko 2>/dev/null; then
    echo "KO_BUILD_SUCCESS"
    for f in "$OUT"/drivers/input/joystick/xone/*.ko; do
        echo "== $f =="
        modinfo "$f" 2>/dev/null | grep -E '^(filename|name|vermagic|depends)' || true
    done
else
    echo "KO_BUILD_FAILED"
    grep -iE 'error:|Error [0-9]' /tmp/xone_cc.log | head -20
fi
