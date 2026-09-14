#!/bin/bash
set -u
QSSI=/home/laide/Desktop/10_code/LA.QSSI.15.0
VEN=/home/laide/Desktop/10_code/LA.VENDOR.15.4.3

echo "===== find qssi.mk ====="
ls -l "$QSSI/qssi.mk" "$QSSI/device/qcom/qssi/qssi.mk" 2>&1 | head
echo "===== inherit meig (no out) ====="
for d in "$QSSI" "$QSSI/device" "$QSSI/vendor/meig" "$QSSI/vendor/qcom"; do
  [ -d "$d" ] || continue
  grep -n --include='*.mk' -d skip -r 'hapticx\|onion_knight\|ppsspp.mk\|cit.mk\|inherit-product.*meig' "$d" 2>/dev/null | grep -v '/out/' | head -40
done
echo "===== top mk ====="
ls "$QSSI"/*.mk 2>/dev/null
grep -n hapticx "$QSSI"/device/qcom/qssi/*.mk 2>/dev/null
grep -n inherit-product "$QSSI"/device/qcom/qssi/*.mk 2>/dev/null | grep -i meig

echo "===== hapticx_ff.rc / sh ====="
echo "----- rc -----"
cat "$VEN/device/qcom/kalama/hapticx_ff/hapticx_ff.rc"
echo "----- sh -----"
cat "$VEN/device/qcom/kalama/hapticx_ff/run_ff_bridge.sh"
echo "----- file ff_bridge -----"
file "$VEN/device/qcom/kalama/hapticx_ff/ff_bridge"
ls -l "$VEN/device/qcom/kalama/hapticx_ff/ff_bridge"

echo "===== second policy xml ====="
md5sum \
  "$VEN/vendor/qcom/opensource/audio-hal/primary-hal/configs/kalama/"*policy* \
  "$VEN/vendor/qcom/opensource/audio-hal/primary-hal/configs/kalama/"*btq* \
  2>/dev/null | head -40
ls "$VEN/vendor/qcom/opensource/audio-hal/primary-hal/configs/kalama/" | grep -iE 'policy|btq|a2dp' | head

echo "===== ha_btq / apc_btq ====="
ls "$VEN/vendor/qcom/opensource/audio-hal/primary-hal/configs/kalama/" | head -50
grep -l a2dp_offload "$VEN/device/qcom/kalama/"*.mk 2>/dev/null

echo DONE
