---
name: 2026-09-12 振动调试日志
description: Review project progress
metadata:
  type: project
---

# 2026-09-12 振动调试日志

## 震动测试情况
- 手柄型号：Razer Wolverine V3 Pro for Xbox (VID:1532 PID:0a3f)
- 连接方式：USB OTG
- 驱动：xone_gip_gamepad/xone_gip/xone_wired (已正确加载)
-事件节点：/dev/input/event5 (FF=0x107030000 标示支持强/弱马达)

## 诊断发现
1. **ff_rumble.c 被误编辑**：2026-09-12 之前的 Edit 操作将源码置为无限循环 shellcode，导致程序无限循环返回 0，根本没执行 EVIOCSFF/IoU 逻辑。
2. **dmesg 无 FF 日志**：即使新版代码跑通，内核日志里仍没有 `xone: ff_rumble`、`gip_ff_play`、`submit_urb` 等任何日志，说明卡在驱动协议层。
3. **触发器不匹配**：板子上的 xone-gip-gamepad.ko 是为蓝牙 GIP/Xbox Series X|S 手柄设计的，Razer V3 Pro USB 模式（HID 类 GIP 包装在 USB 中）可能不在兼容列表。

## 问题根因
- 按位拆解 FF=0x107030000：支持 FF_RUMBLE，但 GIP 蓝牙协议层的 `gip_send_rumble` 需要经过水晶头发 Packet 给手柄。USB 模式下，这个 path 没有触发。
- 结论：**卡在 kalama BSP 的 xone-gip-gamepad.ko 驱动内，未正确下发 rumble 命令给 USB HID 封装的 Razer 手柄**。

## 推进建议
1. 换手柄：确认是 Razer V3 Pro 在 OTG USB 模式是否能被 Android 原生 xone 驱动识别。
2. 蓝牙调测：把手柄切成蓝牙模式，用手机/BT 连接，测试是否振动。
3. 补丁：如果是厂商没加 USB FF 支持，需在 kernel 的 `drivers/hid/hid-xone.c` 或 `drivers/input/joystick/xone/` 里补 1532:0a3f 的 compatible ID。
4. 替代方案：参考 xpad 驱动，或自行打补丁让 `ff_rumble` 直接调用 `usb_kill_urb` + `usb_control_msg` 发 rumble 特征报告。

## 时间线
- 00:30-00:35：确认 adb 设备在位，扫描 USB 端口，VID:1532 PID:0a3f 确认是 Razer V3 Pro
- 00:35-00:40：尝试加载/重载 xone 模块，发现加载顺序问题，修正后成功加载
- 00:40-00:45：ff_rumble 测试返回 success，但 dmesg 无 xone 相关日志
- 00:45-00:48：分析 ff_rumble 源码被误修改，定位到驱动协议层不匹配

## 当前状态
- 🟡 振动功能**未验证通过**
- 🔴 根因：Xbox GIP协议驱动对USB-Razer兼容性不完整
- ⏳ 需要：查 kalama BSP 源，补 rigth compatible table，或换 BT 模式调测

---

## ⚠️ 上面旧结论已被证伪（09-12 上午 WorkBuddy 实测更正）
**驱动层 FF 链路是通的，振动能出来**：
- 09-11 用户实测 ff_rumble 65535:65535 → "振动了"（见 09-11 记录）
- 09-12 上午 WorkBuddy 直接跑 `/data/local/tmp/ff_rumble /dev/input/event5 65535 65535 500` → 用户确认持续振动（进程卡在循环里持续触发，kill 10291 后停止）
- 旧结论"根因=GIP驱动不兼容USB-Razer"是错的，别再引用

## 09-12 上午实测（WorkBuddy）——"自播自采有声音但手柄不振"排查
1. 板子重启过，IP 217→32；xone 模块自动加载，手柄仍在 event5（FF=107030000）
2. ff_bridge（logcat -s HapticXOut 管道 → EVIOCSFF）已在 event5 重启，正常 streaming
3. **app 根本没启动引擎**：logcat 无任何 HapticX/HapticXOut；"自播"按钮(R.id.tone)只 playTone 放音，采集引擎必须点"开始捕获"走投屏授权
4. 板上 priv-app /system/priv-app/HapticX/HapticX.apk 是**旧版**（6 个 dex 全无 auto_test 字符串）；本地 app-debug.apk(09-06 15:44) 有 auto_test 但安装被拒：INSTALL_FAILED_UPDATE_INCOMPATIBLE（priv-app 平台签名 vs 本地 debug 签名）。旧 APK 有 HapticXOut/TonePlayer，功能可用
5. **屏幕睡眠是最大干扰源**：mWakefulness=Asleep 时投屏授权弹窗起不来、auto_test 全程静默；且板子**未插电时 svc power stayon true 无效**，灭屏深睡后 WiFi 直接连 adb 都 ping 不通（掉网）
   - 已设 `settings put system screen_off_timeout 600000`
   - 板子插着电跑的话 stayon 才有效
6. UI 自动化路径已验证可行：开始捕获(540,857) → appops PROJECT_MEDIA=allow 下授权静默通过 → 状态"引擎运行中"→ 自播(540,1025) → AudioTrack USAGE_MEDIA 48kHz state:started 确认在播
7. **采集管线本身通**：HapticXOut L=0.000 R=0.000 持续输出（峰值 0 是因为当时还没放音）
8. **audioserver 中途死过一次**："AudioPolicyService server died!" → capture 重建失败 status -22 → MediaProjection 采集会话作废，必须重启引擎。camera provider 每 5s SIGABRT 崩溃循环（CamX HwEnvironment init fail）刷爆 crash buffer，板子已知问题
9. ff_rumble 持续振动的 bug：参数 500ms 但进程卡 nanosleep 循环反复触发效果 —— ff_rumble 源码的时长/循环逻辑要复查

## 下一步（板子被唤醒后）
1. 亮屏 + dismiss-keyguard → UI 点击：停(如引擎在跑)→开始捕获→自播
2. 看 HapticXOut 是否出现非零 L/R → ff_bridge 振动
3. 若 HapticXOut 全 0 而音频在播 → 查 MediaProjection 采集是否又遇 audioserver 会话作废，重启引擎再试
4. 尽量插电跑（stayon 才有效），或插根 USB 线保持 WiFi adb 不掉

## 第二轮补充（12:23-13:05，详见 04_workbuddy_记忆与skill/日志/2026-09-12.md）
- logcat 缓冲 256KB 被 camera 崩溃刷爆 → 必须 `logcat -f` 流式落盘（full.log 在设备 /data/local/tmp/）
- 引擎静默死机制 = app 进程反复重启 + START_STICKY 空 intent 自停（pid 7275→23813→24054→26824）
- 旧 APK 自播按钮点一下采集必死（两次复现），疑自带 stop 逻辑
- 外部音源：am start VIEW 铃声 → com.android.music/.AudioPreview 自动播放 ✅
- 板子不插电周期性深睡掉网；下次加 `echo hapticx > /sys/power/wake_lock` 防 suspend
- 核心未解：还没有一个"放音期间采集存活"的数据点，无法判定 MediaProjection 播放采集是否真正工作
