---
name: snm970-fake-build-success-check
description: SNM970 项目"以为编译了、结果没编译进包"的验包排查。当改了内核配置/driver/DT/.ko 或任何刷机包内容后，在刷机前确认改动是否真的进了 super/vendor_dlkm/boot 等镜像；触发词：编译了没进包、刷机没生效、ko 没加载、vendor_dlkm、假成功、验包。
agent_created: true
---

# SNM970 假成功验包

> 核心原则：**build 脚本打出 DONE ≠ 改动进了刷机包。** 只有直接翻产物才可信。
> 完整背景见 `12_win_上机跑\04_快速编译指令.md`「假成功根因」6 条。本 skill 是可执行 checklist。

## 何时用
- 改过内核配置、vendor 驱动、DT、`.ko`，或任何"应该进刷机包"的文件后，跑 SNM970_A15_build.sh 之前/之后
- 刷机后发现改动不生效、怀疑编了没进包
- 想快速验证一个 kernel 模块能否进 vendor_dlkm.img（无需跑 8h 整包）

## 快速验证单模块（约 50min，不跑 Android）
```bash
cd /home/laide/Desktop/10_code/LA.VENDOR.15.4.3/kernel_platform
BUILD_CONFIG=./msm-kernel/build.config.msm.kalama VARIANT=consolidate \
  ./build/build.sh 2>&1 | tee /tmp/kernel_only.log
# 验产物：
ls out/msm-kernel-kalama-consolidate/dist/<name>*.ko
grep <name> out/msm-kernel-kalama-consolidate/dist/vendor_dlkm.modules.load
```
EXIT=0 + dist 有 ko + modules.load 有它 → 单模块层 OK。

## 整包后必做 3 道验包（缺一道都可能"编了没进"）
**1. COPY_NEEDED 有没有触发搬运**
```bash
# 搬运整段仅 COPY_NEEDED=1 才跑；这行日志是判据
grep -c "Preparing prebuilt folder" \
  vendor/vendorcode/build/build_log/make_userdebug_target.txt
# 0 = 搬运被跳过（Image 未删 + build.config 没变）→ ko 不会进包
```
**2. 产物层直接翻镜像验**
```bash
debugfs -R "ls /lib/modules" out/target/product/kalama/vendor_dlkm.img | grep <name>
debugfs -R "stat /lib/modules/<name>.ko" out/target/product/kalama/vendor_dlkm.img | head
```
**3. 比对 device 目录 ko 是不是新的**
```bash
ls -la --time-style=+%m-%d device/qcom/kalama-kernel/vendor_dlkm/*.ko | head
# 若 device 目录比 kernel_platform/out/.../dist/ 的 ko 时间戳旧 → 搬运没发生
```

## 修复动作（三选一）
- 只改了驱动/config，没改 build.config：
  ```bash
  rm -f device/qcom/kalama-kernel/Image
  # 然后重跑 target + dynamic 阶段：从 build_log 看 make_userdebug_target 是否已重触发
  ```
- 想彻底重来：`./SNM970_A15_build.sh userdebug kalama 01 full`（仍建议加删 Image 保险）
- 快速救包（不重跑）：手工把 `kernel_platform/out/.../dist/<name>.ko` 拷进
  `device/qcom/kalama-kernel/vendor_dlkm/`，重跑 `prepare_vendor.sh` 再跑 target 打包。

## 根因速记（源码级）
- `prepare_vendor.sh` 行 201-207：COPY_NEEDED 只在 device/Image 缺失 或 build.config diff 时 =1。
  **完全不看 .config / 驱动源码变化。**
- `copy_kernel`：`rsync -a` 无 `--delete` → 旧 ko 残留。
- `run_build`：`2>&1 > log` 写反，stderr 进终端被吞；必须 `tee build.log`。
- GKI：vendor 驱动必须 `=m`，`=y` 不产 ko → 进不了 vendor_dlkm。

## 刷机后自检（最后一道）
```bash
adb shell ls -l /vendor/lib/modules/<name>*.ko
adb shell grep <name> /vendor/lib/modules/modules.load
adb shell "dmesg | grep -iE '<name>'"
```
