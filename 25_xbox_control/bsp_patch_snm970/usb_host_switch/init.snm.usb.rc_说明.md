# init.snm.usb.rc（VM: device/qcom/kalama/init.snm.usb.rc，2026-09-04 最终版）

## 决策
默认 peripheral（保 adb），连手柄后手动 `setprop persist.vendor.snm.usb_host 1` 切 host。

```
on boot
    setprop persist.vendor.snm.usb_host 0
    write /sys/bus/platform/devices/a600000.ssusb/mode peripheral

on property:persist.vendor.snm.usb_host=1
    write /sys/bus/platform/devices/a600000.ssusb/mode host

on property:persist.vendor.snm.usb_host=0
    write /sys/bus/platform/devices/a600000.ssusb/mode peripheral
```

## 挂载方式（关键坑）
- 原方案 AndroidBoard.mk BUILD_PREBUILT：增量编译不拾取新增模块 → rc 文件不进镜像。
- 最终方案：kalama.mk 末尾（~528 行）加：
  `PRODUCT_COPY_FILES += $(LOCAL_PATH)/init.snm.usb.rc:$(TARGET_COPY_OUT_VENDOR)/etc/init/hw/init.snm.usb.rc`
  ⚠️ 注意：**没有 `TARGET_COPY_OUT_VENDOR_ETC` 这个变量**（未定义会静默展开为空，文件拷到根暂存区）。正确写法是 `$(TARGET_COPY_OUT_VENDOR)/etc/...`，与本树 charger_fw_fstab.qti 的拷贝先例一致。此坑踩了两次（第一次 heredoc 双引号、第二次变量名记错），2026-09-04 17:05 那次编译因此没进镜像。
  同时删除 AndroidBoard.mk 里 init.snm.usb.rc 的 BUILD_PREBUILT 段（避免重复）。
- init.target.rc 末尾已加 `import /vendor/etc/init/hw/init.snm.usb.rc`。

## 警告教训
在 Windows bash 里对 VM 用**双引号 heredoc** 时 `$(LOCAL_PATH)`、`$(TARGET_COPY_OUT_VENDOR_ETC)` 会被本地 shell 展开成空，还会把 `\n` 变成字面字符。必须用**单引号 heredoc**（`<<'PYEOF'` / `<<'EOF'`）。

## 验证方法
1. 重编 target 后：`find out -path '*vendor/etc/init/hw/init.snm.usb.rc'` 或解包 vendor.img 确认文件存在。
2. 刷机后 `adb shell getprop persist.vendor.snm.usb_host` 应为 0；`setprop persist.vendor.snm.usb_host 1` 后 `cat /sys/bus/platform/devices/a600000.ssusb/mode` 应为 host。
