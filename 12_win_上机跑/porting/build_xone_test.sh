#!/bin/bash
# 提前验 xone 模块编译（独立 O 目录，不碰主编译的 out/）
set -e

KROOT=/home/laide/Desktop/10_code/LA.VENDOR.15.4.3/kernel_platform
MSM=$KROOT/msm-kernel
OUT=/tmp/xone_test_build

CLANG=$KROOT/prebuilts/clang/host/linux-x86/clang-r450784e/bin
BUILDTOOLS=$KROOT/prebuilts/build-tools/linux-x86/bin
export PATH="$CLANG:$BUILDTOOLS:$PATH"

cd "$MSM"

echo "=== [1] make prepare (生成 include/config 与 autoconf) ==="
make O="$OUT" ARCH=arm64 LLVM=1 prepare -j4 > /tmp/xone_prepare.log 2>&1 && echo "PREPARE_OK" || { echo "PREPARE_FAIL"; tail -25 /tmp/xone_prepare.log; exit 1; }

echo
echo "=== [2] 确认 .config 里 XONE/CRYPTO 状态 ==="
grep -E 'JOYSTICK_XONE|CRYPTO_ECDSA|CRYPTO_ECDH|CRYPTO_ECC|FF_MEMLESS|LEDS_CLASS' "$OUT/.config"

echo
echo "=== [3] 编译 xone 7 个 .o (抓 5.15 API 兼容性) ==="
make O="$OUT" ARCH=arm64 LLVM=1 -j4 \
  drivers/input/joystick/xone/transport/wired.o \
  drivers/input/joystick/xone/bus/bus.o \
  drivers/input/joystick/xone/bus/protocol.o \
  drivers/input/joystick/xone/auth/auth.o \
  drivers/input/joystick/xone/auth/crypto.o \
  drivers/input/joystick/xone/driver/common.o \
  drivers/input/joystick/xone/driver/gamepad.o 2>&1 | tee /tmp/xone_cc.log | tail -30

echo
echo "=== [4] 结果 ==="
ls -la "$OUT/drivers/input/joystick/xone/"*.o 2>/dev/null && echo "ALL_OBJ_OK" || { echo "SOME_OBJ_MISSING"; grep -iE 'error|warning' /tmp/xone_cc.log | head -20; }