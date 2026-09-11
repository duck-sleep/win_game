#!/bin/bash
# 复用已完成的 msm-kernel 构建环境，把 xone 编成 .ko（不重编整包）
set -e

KROOT=/home/laide/Desktop/10_code/LA.VENDOR.15.4.3/kernel_platform
KSRC=$KROOT/msm-kernel
ODIR=$KROOT/out/msm-kernel-kalama-consolidate/msm-kernel
CLANG=$KROOT/prebuilts/clang/host/linux-x86/clang-r450784e/bin
BUILDTOOLS=$KROOT/prebuilts/build-tools/linux-x86/bin
export PATH="$CLANG:$BUILDTOOLS:$PATH"

echo "=== [0] 环境自检 ==="
ls -la "$ODIR/.config" "$ODIR/include/generated/asm-offsets.h" "$ODIR/include/generated/autoconf.h" 2>&1
ls -d "$KSRC/drivers/input/joystick/xone"
ls -la "$ODIR/Module.symvers" 2>&1 | head -2

cp -a "$ODIR/.config" /tmp/xone_out_config.bak
echo "备份原 .config -> /tmp/xone_out_config.bak"

echo
echo "=== [1] 把 XONE 从 built-in 改成 module ==="
sed -i 's/^CONFIG_JOYSTICK_XONE_WIRED=y$/CONFIG_JOYSTICK_XONE_WIRED=m/' "$ODIR/.config"
sed -i 's/^CONFIG_JOYSTICK_XONE_WIRED_INPUT=y$/CONFIG_JOYSTICK_XONE_WIRED_INPUT=m/' "$ODIR/.config"
grep -nE 'JOYSTICK_XONE|INPUT_FF_MEMLESS|CRYPTO_ECDSA|CRYPTO_ECDH|LEDS_CLASS=' "$ODIR/.config"

echo
echo "=== [2] olddefconfig 同步 ==="
make -C "$KSRC" O="$ODIR" ARCH=arm64 LLVM=1 olddefconfig > /tmp/xone_cfg.log 2>&1 || { echo CFG_FAIL; tail -20 /tmp/xone_cfg.log; exit 1; }
grep -nE 'JOYSTICK_XONE' "$ODIR/.config"

echo
echo "=== [3] 编 xone 模块 ==="
make -C "$KSRC" O="$ODIR" ARCH=arm64 LLVM=1 -j6 M=drivers/input/joystick/xone modules 2>&1 | tail -35

echo
echo "=== [4] 产物 ==="
find "$ODIR/drivers/input/joystick/xone" -name '*.ko' -exec ls -la {} \;
for f in $(find "$ODIR/drivers/input/joystick/xone" -name '*.ko' 2>/dev/null); do
  echo "--- $(basename $f) ---"
  modinfo "$f" 2>/dev/null | grep -E '^(name|vermagic|depends)' || true
done
echo "DONE"
