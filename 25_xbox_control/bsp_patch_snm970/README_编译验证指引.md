# SNM970 播放采集 BSP 补丁 — 修改说明与编译验证指引

## 根因（已实验验证）

播放采集（HapticX 播放捕获）静音的完整因果链：

1. **根因 A（主因）**：高通 BSP 在 `AudioPolicyManager.cpp getOutputForDevices()` 里，
   `vendor.audio.offload.track.enable`（默认 true）强制把 `STREAM_MUSIC + USAGE_MEDIA/GAME`
   的 PCM 流设成 `AUDIO_OUTPUT_FLAG_DIRECT`（PCM offload 直通）→ 绕过 MIXER →
   AudioFlinger 的 secondary outputs（tee 影子轨）机制无从触发。
   （已验证：root setprop false + 重启 audioserver 后，测试音从 DIRECT 线程回到 MIXER 线程）

2. **根因 B（次因）**：关掉 offload 后，`audio.deep_buffer.media`（默认 true）把 MEDIA 流
   路由到 DEEP_BUFFER 输出线程（AudioOut_25），但该线程在本板是坏的
   （`Blocked in write`、`Frames written: 0`、时间戳 `rate=nan`）→ threadLoop 卡死 →
   `updateTeePatches_l()` 不执行 → 影子轨永远 IDLE → 采集静音。

## 补丁内容（单文件：managerdefault/AudioPolicyManager.cpp）

在 `getOutputForDevices()` 的 offload/deep_buffer 决策前，检测是否已注册
loopback render policy mix（即播放采集授权中）：

- `playbackCaptureActive == true` 时：
  1. 不强制 DIRECT（豁免 PCM offload 直通）
  2. 不强制 DEEP_BUFFER（避开坏线程）
  → MEDIA/GAME 流走正常 primary MIXER（AudioOut_D，已验证正常工作），
    影子轨机制可正常触发
- `playbackCaptureActive == false` 时：行为与原版完全一致（省电优化保留）

改动范围：2 处、净增约 19 行。原文件备份为 `AudioPolicyManager.cpp.snm970.orig`。

## 快速验证（增量编译，不用跑 6h 全量）

在 VM 的 QSSI 树里（与 SNM970_A15_build.sh 相同的 lunch 环境）：

```bash
cd ~/Desktop/10_code/LA.QSSI.15.0
source build/envsetup.sh
lunch <你的QSSI lunch目标>
mmm frameworks/av/services/audiopolicy/managerdefault
# 产物: out/target/product/<device>/system/lib64/libaudiopolicymanagerdefault.so
```

推到板子验证（userdebug，需 root）：

```bash
adb root && adb remount
adb push out/target/product/<device>/system/lib64/libaudiopolicymanagerdefault.so /system/lib64/
adb shell killall audioserver
```

## 验证要点（改完后按这个顺序看）

1. `logcat | grep "keep stream"` — 出现 `playback capture active, keep stream 3 on mixer path`
   即补丁生效（stream 3 = MUSIC）
2. 启动 HapticX 采集 → 自动测试音 → `dumpsys media.audio_flinger` 里：
   测试音主轨应落在 **AudioOut_D（primary MIXER）**，不再是 AudioOut_5D(DIRECT)/AudioOut_25(DEEP_BUFFER)
3. REMOTE_SUBMIX 输出（AudioOut_5x）里的影子轨（P 开头）应为 active，`Frames written` 持续增长
4. `logcat | grep 输入电平` — peak > 0 即全链路打通
5. 若 primary MIXER 上 FAST 轨的影子轨仍不激活（低概率，Pixel 有 FastMixer 也能采集），
   再回来查 `updateTeePatches_l` 对 fast track 的调用路径

## 回退

```bash
cd frameworks/av/services/audiopolicy/managerdefault
cp AudioPolicyManager.cpp.snm970.orig AudioPolicyManager.cpp
```

## 注意

- 本补丁只动 QSSI 树（system 分区），不涉及 VENDOR 树
- 正式出包走 SNM970_A15_build.sh 全量（补丁会进 system 镜像）
- DEEP_BUFFER 线程在 HAL 层卡死是另一个独立 bug（不阻塞本修复，但值得后续报给 BSP 侧）
