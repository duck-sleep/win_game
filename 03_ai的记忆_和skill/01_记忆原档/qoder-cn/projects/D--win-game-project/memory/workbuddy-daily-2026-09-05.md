---
name: win_game_project 工作日志 2026-09-05
description: Review project progress
metadata:
  type: project
---

(若文件已存在请追加) 

## 00:28 播放采集排查重大进展（音频静音根因链条更新）
**已确认事实链（板上实测 + QSSI 源码核对）：**
- APM 补丁生效：音乐走 AudioOut_D（MIXER 线程），没被逼到 offload/DIRECT（日志 "keep stream 3 on mixer path"）
- Mix 注册健康：MIX_TYPE_PLAYERS + RENDER|LOOP_BACK + REMOTE_SUBMIX(747858387:ap:0mixp:0) + output 85，criteria 含 USAGE_UNKNOWN/MEDIA/GAME
- areMixCriteriaMatched 逻辑核对：3 条全是 usage 正向规则，MEDIA 必命中（AudioPolicyMix.cpp:72-101）
- AF::createTrack 自己调 AudioSystem::getOutputForAttr 拿 secondaryOutputs，非空才调 updateSecondaryOutputsForTrack_l 建 TeePatch（AF.cpp:996-1135, 3879-3968）
- **TeePatch 其实建了**：AudioOut_55（output 85, r_submix 输出线程）上有 2 条 PatchTrack（audioserver, 48k+44.1k）
- **但数据零流动**：2 条 PatchTrack 全 idle(S=I)/FrmRdy=0/server=0，output 85 Standby=yes、Frames written=0 → HapticX peak 恒 0
- PatchPanel 面板不显示 TeePatch（挂在 Track 对象上），不能拿面板当证据
- AF 无 "secondary output"/"patchRecord/patchTrack init failed" 报错 → 创建成功，卡在喂数据

**数据流机制（源码已核对）：**
- 混音循环对活跃轨调 track->updateTeePatches_l()（Threads.cpp:4255-4259）→ 移入 pending tee patches 并 start patchTracks（Tracks.cpp:1637-1648）；Track::start() 也会 start patchTracks（Tracks.cpp:1292）
- 待查断点：主轨混音数据写进 patchRecord 的路径（Tracks.cpp ~1085-1100 getTeePatches 使用者 + PatchTrack/PatchRecord 在 Threads.cpp 的数据流），被打断没读完
- 疑点：PatchTrack 有 frameCountToBeReady 门控（=2*sink+source 帧数就绪才启动），若主线程从未往 patchRecord 写则永远 idle

**测试环境备注：**
- 测试音：本地生成的 440Hz WAV（音量 2 秒起伏），推到 /sdcard/Music/test_tone.wav，用系统音乐 app（com.android.music, pid 8376, usage MEDIA flags 0x0）播放
- HapticX 捕获用 MediaProjection Entire screen 授权；HapticXCapture 线程每秒 50 块稳定读，peak=0
- CamX 摄像头 HAL 每 5 秒循环崩溃（UID 1047），与音频无关勿误判
- 屏幕息屏很快：svc power stayon true 常亮；横屏 1920x1080
- 下一步：读完 Tracks.cpp:1075-1100 和 PatchTrack 数据流，查主轨→patchRecord 喂数据断在哪；或对比 AOSP 原生看高通有没有砍 tee 逻辑

## 01:10 接力验证补充（详细版见 04_workbuddy 日志 2026-09-05.md）

- 影轨 IDLE 是**系统性**的：binder updateSecondaryOutputs 更新的 5 条存量系统轨 + 测试音影轨(110)全部 State=I/FrmRdy=0/Underruns=0，r_submix 线程从未醒（Timestamp n=1）→ 影轨 Track::start 从未执行
- 音量干扰排除：STREAM_MUSIC speaker 默认 0（G db=-inf），`cmd audio set-volume 3 15` 修好后复测仍 peak=0
- isExternalTrack 拒绝假设排除（PatchTrack 明确 false）；板上 audioserver 二进制含全套 tee 机制字符串 = 运行代码与 VM 源码一致

## 13:00-13:20 snm970_jt 编译成功 + 虚拟耳机插孔打通（3.5mm 出口验证✅）

**snm970_jt 静态编译（VM AOSP clang，无需 NDK）：**
- write() 方式 setup uinput 在 5.15 内核走 legacy 路径（要求 struct uinput_user_dev 1492B），发新结构体(92B)报 EINVAL → 必须用 **UI_DEV_SETUP ioctl**
- 编译配方见 skill 文档：`04_workbuddy_记忆与skill/skills/snm970-aarch64-static-bin.md`

**虚拟插孔测试结果（板上实测，全链路通）：**
- `./snm970_jt jack` → uinput 建虚拟设备 SNM970_JACK_SIM → EventHub 识别 SWITCH 类 → **WiredAccessoryManager: headset h2w connected** → AudioFlinger 真的 openOutput WIRED_HEADPHONE ✅
- 播放验证：SnapdragonMusic 播 test_tone.wav → 新开 DIRECT 线程 AudioOut_B5（44.1kHz）→ **PAL_DEVICE_OUT_WIRED_HEADPHONE open/close 干净** → 轨道 server 帧数推进、10 秒播完正常移除 → **无 HAL 卡死，音频出口链路全通** ✅
- 结论：之前"HAL write 卡死"是 speaker 后端独有问题；3.5mm 耳机后端 drain 正常。等用户戴耳机主观确认声音

**板上系统坑（都踩过）：**
- SnapdragonMusic 崩溃根因：缺 READ_PHONE_STATE → `pm grant com.android.music android.permission.READ_PHONE_STATE` 修好
- device_provisioned 重启后丢失 → Settings/解锁全废，需重打 `settings put global device_provisioned 1` + `secure user_setup_complete 1`（建议做成 boot 修复）
- app.gamenative（IRIX 桌面）是 HOME 且每次恢复都弹"扫描 ROM"对话框抢前台，force-stop 会自动复活 → **本轮已 `pm disable-user --user 0 app.gamenative`**（恢复：`pm enable app.gamenative`），禁用后露出 launcher3
- 播放无 UI 方法：monkey 启 Music → 点艺人(700,360)→专辑(700,540)→歌(700,1404) → `cmd media_session dispatch previous/play`（歌播完停在 position=10000 时需先 previous）
- 息屏快：`svc power stayon true` + screen_off_timeout 调大；锁屏"仅紧急呼叫"= provision 丢了

## 13:30-14:00 HapticX 采集链路全打通，最后卡点=路由（重大结论）

**已验证通的环节（板上实测）：**
- HapticX 开始捕获 → r_submix 输出/输入线程创建 ✅（REMOTE_SUBMIX 出现在 AF dump）
- 采集注册后每条 MEDIA 轨 tee 挂载成功：`SNM970Tee: updateSecondaryOutputsForTrack_l track=N nSecondary=1` ✅
- HapticX AudioRecord 48kHz 实时读（server 帧 3 秒推进 ~15 万帧）✅，UI"引擎运行中"✅
- BSP 补丁位置：`QSSI-irix/frameworks/av/services/audiopolicy/managerdefault/AudioPolicyManager.cpp:1849`（playbackCaptureActive 时禁 DIRECT/深缓冲强制 mixer path）+ `audioflinger/AudioFlinger.cpp:3880`（tee 日志）

**最终卡点（peak=0 的根因）：**
- mixer 线程（AudioOut_D）绑定 **speaker 后端**（0x2 patch 永不切换），speaker 后端 HAL 永不 drain（板无喇叭）→ 主轨 Server=0 混音循环不跑 → TeePatch 无数据 → HapticX 读到全 0
- 重插虚拟耳机不会重路由 mixer 线程（APM patch 一直打 speaker）；采集未激活时音乐走 DIRECT headphone（能 drain）但那时没采集
- **audioserver 崩溃也是它**：speaker 线程卡死持主锁 → releaseAudioSessionId→purgeStaleEffects_l 死锁 → watchdog 杀 audioserver+audio HAL（12:21:48 实测崩溃堆栈在手）

**下一步方向（二选一，需改码重编）：**
1. APM 补丁扩展：capture 激活时把 primary/mixer output 的 createAudioPatch 跟随 MEDIA 策略设备（headphone）
2. 更彻底：audio_policy_configuration.xml 摘掉 speaker（板子本来就没喇叭），全局默认 headphone

**板上状态备注：** app.gamenative 已 disable-user（恢复 pm enable）；SnapdragonMusic 已 grant READ_PHONE_STATE；provision 标志重启会丢需重打；audioserver 崩溃重启后 Framework 侧耳机路由状态保持
- 静态分析见底 → **必须插桩**：updateTeePatches_l（log has_value/mState/start 返回）+ Track::start tee 段 + PatchTrack::start；mmm frameworks/av/services/audioflinger 增量 → push /system/bin/audioserver → killall audioserver
- 新坑：①重复 start 捕获前必须 force-stop 清投影（旧投影 stop 回调与新会话录制端撞车 → createRecord -22）②这板没 `media` 命令，用 `cmd audio set-volume 3 15` ③判包版本看特征字符串，ro.build.date 停在 8-23 不刷新
- 板上包快照：APM 补丁 ✅ / priv-app 预装 ✅ / init.snm.usb.rc ✅（三项已在板验证）；XPAD_FF ❌（正在编译的新包交付）

## 11:30 继续同步（读 03_ai的记忆 后接力）+ 采集静音真根因（重大反转）
- 先同步了昨晚其他 AI 的交接（影子轨 START 已修、FF fragment 修复、build6 已出包 10:39 待刷）
- 严谨复测推翻"单轨优化路径无 releaseBuffer"结论（查错文件，真身在 AudioMixerBase.cpp:1321/1503，所有混音路径都会释放）
- 板上实证真根因：AudioOut_D **HAL write 永久阻塞**（Total writes 卡 4、Blocked in write: yes）→ FastMixer 冻结 → 音轨 Server=0 从未被消费 → intercept 永不执行 → 采集静音
- 内核驱动零错误、声卡注册正常；板上无喇叭 + ADSP 固件前科 → speaker 后端无法 drain
- 方向三选待用户定：USB DAC 验证（最便宜）/ 深挖 DSP write 卡死 / 降级自环验证
- 详细版见 03_ai的记忆_和skill/04_workbuddy_记忆与skill/日志/2026-09-05.md

## 12:06 Settings 修复收官（用户验证好评）
- 根因：ROM 未走完成机向导 → Settings 检测 "Device is not provisioned" 秒退
- 修复：settings put global device_provisioned 1 + settings put secure user_setup_complete 1（重启可能丢，复发就重写）
- 桌面 app.gamenative（IRIX 前端）自绘顶栏盖住 SystemUI → 下拉无效是正常；Scan for ROMs 弹窗是桌面自身行为
- tap 坐标坑再次确认：screencap 图是缩放+旋转的，不能按图比例直接换算 input tap
- 用户现在可自行在 Settings 连蓝牙音箱/WiFi；下一步等蓝牙连上后复测音频采集（验证 A2DP 出口能否解 HAL write 卡死）
