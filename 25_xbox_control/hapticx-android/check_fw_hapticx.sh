#!/bin/bash
set -u
QSSI=/home/laide/Desktop/10_code/LA.QSSI.15.0
VEN=/home/laide/Desktop/10_code/LA.VENDOR.15.4.3

echo "===== SYMLINK ====="
readlink -f "$QSSI"
readlink -f "$VEN"

echo "===== inherit hapticx ====="
grep -n -i hapticx "$QSSI/qssi.mk" || echo NO_IN_qssi.mk
grep -n inherit-product "$QSSI/qssi.mk" | head -30
echo "----- vendor/meig -----"
ls "$QSSI/vendor/meig/"
echo "----- hapticx.mk -----"
cat "$QSSI/vendor/meig/hapticx.mk"
echo "----- Android.mk -----"
cat "$QSSI/vendor/meig/HapticX/Android.mk"

echo "===== APK badging ====="
AAPT=""
for c in \
  "$QSSI/prebuilts/sdk/tools/linux/bin/aapt" \
  /home/laide/Desktop/10_code/LA.QSSI.15.0-irix/prebuilts/sdk/tools/linux/bin/aapt
do
  if [ -x "$c" ]; then AAPT=$c; break; fi
done
echo AAPT=$AAPT
if [ -n "$AAPT" ]; then
  "$AAPT" dump badging "$QSSI/vendor/meig/HapticX/HapticX.apk" | head -8
fi
ls -l "$QSSI/vendor/meig/HapticX/HapticX.apk"
md5sum "$QSSI/vendor/meig/HapticX/HapticX.apk"

echo "===== privapp / default-perm ====="
cat "$QSSI/vendor/meig/HapticX/privapp-permissions_hapticx.xml"
echo "-----"
cat "$QSSI/vendor/meig/HapticX/default-permissions-com.meig.hapticx.xml"

echo "===== kalama.mk ====="
KMK="$VEN/device/qcom/kalama/kalama.mk"
ls -l "$KMK"
grep -n hapticx "$KMK" || echo NO_hapticx_IN_kalama.mk
grep -n a2dp_offload "$KMK" || echo NO_a2dp_IN_kalama.mk
echo "----- tail haptic-related context -----"
grep -n -A6 -B2 hapticx "$KMK" || true
grep -n -A3 -B2 a2dp_offload "$KMK" || true

echo "===== hapticx_ff dirs ====="
ls -la "$VEN/device/qcom/kalama/hapticx_ff" 2>/dev/null || echo NO_device_qcom_kalama_hapticx_ff
ls -la "$VEN/vendor/meig/hapticx_ff" 2>/dev/null || echo NO_vendor_meig_hapticx_ff
ls -la /home/laide/Desktop/10_code/LA.VENDOR.15.4.3-irix/device/qcom/kalama/hapticx_ff 2>/dev/null || true

echo "===== policy xml ====="
for p in \
  "$VEN/hardware/qcom/audio/configs/kalama/audio_policy_configuration.xml" \
  "$VEN/device/qcom/kalama/audio_policy_configuration.xml" \
  "$VEN/vendor/qcom/opensource/audio-hal/primary-hal/configs/kalama/audio_policy_configuration.xml"
do
  if [ -f "$p" ]; then
    echo "FILE $p"
    md5sum "$p"
  fi
done

echo "===== build script mention ====="
grep -n hapticx "$VEN/SNM970_A15_build.sh" 2>/dev/null | head || echo no_in_build_sh
echo DONE
