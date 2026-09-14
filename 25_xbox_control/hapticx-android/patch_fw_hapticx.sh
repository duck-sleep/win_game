#!/bin/bash
set -e
QSSI=/home/laide/Desktop/10_code/LA.QSSI.15.0
VEN=/home/laide/Desktop/10_code/LA.VENDOR.15.4.3
HX="$QSSI/vendor/meig/HapticX"
FF="$VEN/device/qcom/kalama/hapticx_ff"

# 预装 APK 换成 0.1.17（Make 会再用 platform 签一次）
if [ ! -f /tmp/hapticx-0117-signed.apk ]; then
  echo MISSING_0117
  exit 1
fi
if [ ! -f "$HX/HapticX.apk.0.1.12.bak" ]; then
  cp -a "$HX/HapticX.apk" "$HX/HapticX.apk.0.1.12.bak"
fi
cp /tmp/hapticx-0117-signed.apk "$HX/HapticX.apk"
AAPT="$QSSI/prebuilts/sdk/tools/linux/bin/aapt"
"$AAPT" dump badging "$HX/HapticX.apk" | grep -E "package:|versionName"
ls -l "$HX/HapticX.apk" "$HX/HapticX.apk.0.1.12.bak"
md5sum "$HX/HapticX.apk"

# 开机顺带放行采集和悬浮窗（appop，不是 runtime permission）
cat > "$FF/hapticx_ff.rc" <<'EOF'
# 开机拉起 ff_bridge。userdebug 下 vendor init 可跑 vendor/bin。
service hapticx_ff /vendor/bin/run_ff_bridge.sh
    class late_start
    user root
    group root system log input
    disabled
    seclabel u:r:su:s0

on property:sys.boot_completed=1
    exec u:r:su:s0 -- /system/bin/appops set com.meig.hapticx PROJECT_MEDIA allow
    exec u:r:su:s0 -- /system/bin/appops set com.meig.hapticx SYSTEM_ALERT_WINDOW allow
    start hapticx_ff
EOF
echo "----- rc now -----"
cat "$FF/hapticx_ff.rc"
echo PATCH_OK
