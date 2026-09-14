#!/bin/bash
set -u
LOG=/home/laide/Desktop/10_code/LA.VENDOR.15.4.3/vendor/vendorcode/build/build_log/make_userdebug_target.ERROR.txt
echo "===== size ====="
ls -l "$LOG"
echo "===== error/fail lines ====="
grep -n -E 'error:|FAILED|ninja: error|fatal error|No such file|hapticx|HapticX|LOCAL_PATH|QIIFA|FAILED:' "$LOG" | tail -80
echo "===== tail 60 ====="
tail -n 60 "$LOG"
echo "===== make_qssi hapticx ====="
grep -n -E 'HapticX|hapticx|error:' /home/laide/Desktop/10_code/LA.VENDOR.15.4.3/vendor/vendorcode/build/build_log/make_qssi.txt | tail -30
