#!/bin/bash
set -u
VEN=/home/laide/Desktop/10_code/LA.VENDOR.15.4.3
cd "$VEN"

echo "===== tmux pane tail ====="
tmux capture-pane -t build -p -S -200 2>/dev/null | tail -n 120

echo "===== run_build log location ====="
grep -n -A20 'run_build\|LOG=\|make_userdebug' SNM970_A15_build.sh | head -80

echo "===== other COPY_FILES style in kalama.mk ====="
grep -n 'PRODUCT_COPY_FILES' -A3 device/qcom/kalama/kalama.mk | head -40

echo "===== LOCAL_PATH in kalama.mk ====="
grep -n LOCAL_PATH device/qcom/kalama/kalama.mk | head

echo "===== find ninja/soong fail ====="
# typical android dump
for p in \
  out/target/product/kalama/.soong/build.ninja \
  out/error.log \
  out/verbose.log.txt \
  out/build_error \
  vendor/vendorcode/build/build_log
do
  [ -e "$p" ] && echo "HAVE $p"
done
ls -lt out/error* 2>/dev/null | head
ls -lt vendor/vendorcode/build/build_log 2>/dev/null | head

echo "===== grep hapticx / COPY error in out ====="
grep -R -l 'hapticx_ff\|PRODUCT_COPY_FILES.*haptic' out/verbose.log.txt out/error.log 2>/dev/null | head
if [ -f out/error.log ]; then
  echo "----- out/error.log tail -----"
  tail -n 80 out/error.log
fi
