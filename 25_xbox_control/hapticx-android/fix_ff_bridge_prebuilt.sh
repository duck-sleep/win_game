#!/bin/bash
set -e
VEN=/home/laide/Desktop/10_code/LA.VENDOR.15.4.3
FF=$VEN/device/qcom/kalama/hapticx_ff
MK=$VEN/device/qcom/kalama/kalama.mk

# 1) 二进制改走 cc_prebuilt_binary
cat > "$FF/Android.bp" <<'EOF'
// Android 15 禁止 PRODUCT_COPY_FILES 拷 ELF，必须走 prebuilt。
cc_prebuilt_binary {
    name: "ff_bridge",
    srcs: ["ff_bridge"],
    vendor: true,
    compile_multilib: "64",
    check_elf_files: false,
    strip: {
        none: true,
    },
}
EOF

# 2) kalama.mk：COPY 只留 rc/sh，二进制改 PRODUCT_PACKAGES
python3 - <<'PY'
from pathlib import Path
p = Path("/home/laide/Desktop/10_code/LA.VENDOR.15.4.3/device/qcom/kalama/kalama.mk")
t = p.read_text()
old = """# SNM970: HapticX ff_bridge 开机自启
PRODUCT_COPY_FILES += \\
    $(LOCAL_PATH)/hapticx_ff/hapticx_ff.rc:$(TARGET_COPY_OUT_VENDOR)/etc/init/hapticx_ff.rc \\
    $(LOCAL_PATH)/hapticx_ff/run_ff_bridge.sh:$(TARGET_COPY_OUT_VENDOR)/bin/run_ff_bridge.sh \\
    $(LOCAL_PATH)/hapticx_ff/ff_bridge:$(TARGET_COPY_OUT_VENDOR)/bin/ff_bridge
"""
new = """# SNM970: HapticX ff_bridge 开机自启
# ELF 不能走 PRODUCT_COPY_FILES（Android 15 check-non-elf 会失败）
PRODUCT_PACKAGES += ff_bridge
PRODUCT_COPY_FILES += \\
    $(LOCAL_PATH)/hapticx_ff/hapticx_ff.rc:$(TARGET_COPY_OUT_VENDOR)/etc/init/hapticx_ff.rc \\
    $(LOCAL_PATH)/hapticx_ff/run_ff_bridge.sh:$(TARGET_COPY_OUT_VENDOR)/bin/run_ff_bridge.sh
"""
if old not in t:
    raise SystemExit("BLOCK_NOT_FOUND")
p.write_text(t.replace(old, new, 1))
print("kalama.mk patched")
PY

echo "===== Android.bp ====="
cat "$FF/Android.bp"
echo "===== kalama.mk tail ====="
sed -n '568,585p' "$MK"
echo FIX_OK
