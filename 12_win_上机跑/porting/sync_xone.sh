#!/bin/bash
# Complete xone porting sync script for LA.VENDOR.15.4.3
# Runs on the VM. Idempotent where possible.
set -e

KP=/home/laide/Desktop/10_code/LA.VENDOR.15.4.3/kernel_platform
C=$KP/common
M=$KP/msm-kernel

echo "=== [1] Sync xone source: common -> msm-kernel ==="
rm -rf "$M/drivers/input/joystick/xone"
cp -r "$C/drivers/input/joystick/xone" "$M/drivers/input/joystick/"
ls "$M/drivers/input/joystick/xone/"

echo
echo "=== [2] Add source line to msm-kernel joystick Kconfig ==="
if ! grep -q 'xone/Kconfig' "$M/drivers/input/joystick/Kconfig"; then
    printf 'source "drivers/input/joystick/xone/Kconfig"\n' >> "$M/drivers/input/joystick/Kconfig"
    echo "added"
else
    echo "already present"
fi

echo
echo "=== [3] Add obj line to msm-kernel joystick Makefile ==="
if ! grep -q 'JOYSTICK_XONE_WIRED' "$M/drivers/input/joystick/Makefile"; then
    printf 'obj-$(CONFIG_JOYSTICK_XONE_WIRED) += xone/\n' >> "$M/drivers/input/joystick/Makefile"
    echo "added"
else
    echo "already present"
fi

echo
echo "=== [4] Patch msm-kernel xpad.c to yield to xone ==="
python3 /tmp/patch_xpad.py "$M/drivers/input/joystick/xpad.c"

echo
echo "=== [5] Append xone+crypto config to kalama_GKI.config (msm-kernel) ==="
MC="$M/arch/arm64/configs/vendor/kalama_GKI.config"
if ! grep -q 'CONFIG_JOYSTICK_XONE_WIRED=y' "$MC"; then
cat >> "$MC" << 'EOF'

# Xbox One GIP driver (Razer Wolverine V3 Pro FF) - 2026-09-10
CONFIG_JOYSTICK_XONE_WIRED=y
CONFIG_JOYSTICK_XONE_WIRED_INPUT=y
CONFIG_INPUT_FF_MEMLESS=y
CONFIG_CRYPTO=y
CONFIG_CRYPTO_ECC=y
CONFIG_CRYPTO_ECDSA=y
CONFIG_CRYPTO_ECDH=y
CONFIG_CRYPTO_SHA256=y
CONFIG_CRYPTO_HASH=y
CONFIG_CRYPTO_MANAGER=y
EOF
echo "appended"
else
echo "already present"
fi

echo
echo "=== [6] Same append to common gki_defconfig if it's the real base ==="
# (common gki_defconfig is GKI base; vendor fragment overrides. We only need vendor. skip.)
echo "skipped (vendor fragment is authoritative)"

echo
echo "=== VERIFY ==="
echo "--- msm-kernel xpad yield ---"
grep -n 'xone_claim_needed' "$M/drivers/input/joystick/xpad.c" | head -3
echo "--- msm-kernel config xone ---"
grep -E 'XONE|CRYPTO_ECDSA|CRYPTO_ECDH' "$MC"
echo "--- common config xone ---"
grep -E 'XONE' "$M/arch/arm64/configs/vendor/kalama_GKI.config" | head -3

echo
echo "ALL_DONE"
