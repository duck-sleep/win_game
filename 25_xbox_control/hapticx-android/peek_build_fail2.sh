#!/bin/bash
set -u
VEN=/home/laide/Desktop/10_code/LA.VENDOR.15.4.3
cd "$VEN"

echo "===== build_log dir ====="
ls -lt build_log 2>/dev/null | head -25

echo "===== make_userdebug_target log ====="
for f in build_log/make_userdebug_target.txt build_log/make_userdebug_target.ERROR.txt \
         build_log/make_target.txt vendor/vendorcode/build/build_log/make_userdebug_target.txt
do
  if [ -f "$f" ]; then
    echo "FILE $f $(wc -l < "$f") lines"
    echo "----- grep error -----"
    grep -n -E 'error:|FAILED|ninja:|fatal|No such file|HapticX|hapticx_ff|LOCAL_PATH' "$f" | tail -50
    echo "----- tail 40 -----"
    tail -n 40 "$f"
  fi
done

echo "===== kalama.mk hapticx / COPY ====="
sed -n '560,590p' device/qcom/kalama/kalama.mk
echo "===== ls hapticx_ff ====="
ls -la device/qcom/kalama/hapticx_ff

echo "===== QSSI HapticX in log ====="
grep -n -E 'HapticX|hapticx|privapp-permissions_hapticx' build.log | tail -30

echo "===== around ERROR ====="
sed -n '1400,1475p' build.log
