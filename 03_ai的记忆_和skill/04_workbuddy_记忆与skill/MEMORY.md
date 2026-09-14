# WorkBuddy 项目记忆（SNM970）

> 长期记忆 · 2026-09-12 深夜更新：状态快照以 `00_START_新会话入口.md` 为准，此处收**永久有效的事实与陷阱**。所有 AI 共用本目录。

## 一、永久事实（随时读取）

### 1. 核心技术结论 ✅
| 项目 | 事实 | 证据 |
|------|------|------|
| 音频采集 | **09-07 通路仍对**；重刷后两份 XML 会丢。09-12 再 push 后 A2DP CONNECTED。现役采集是 **AudioPlaybackCapture**，不是 REMOTE_SUBMIX | 板上 0.1.12；动态档放 SSD 歌已震 |
| FF 震动 | 09-12 刷机后 xone + `/dev/input/eventN` + root `ff_bridge` 读 `HapticXOut` 实震。停震必须强度 0 + `EV_FF=1` | 用户确认震；hv-haptics 也有 FF_RUMBLE 别发错 |
| **xone.ko 进包确认** | **09-11 14:30 验包**：inc 模式编译（删 Image 后重跑）→ `device/qcom/kalama-kernel/vendor_dlkm/` 落 ko、`dist/vendor_dlkm.modules.load` 列表 xone 三件套、`build.log` 全程 END → **xone 成功进刷机包** | 见下 "14:20 自省"；稀疏镜像 super.img 12:30 生成，vendor_dlkm.img 11:54 已收录 xone ko |
| 驱动方案 | **09-10 完成 xone 移植**：`kernel_platform/{common,msm-kernel}/drivers/input/joystick/xone/` 7 个 .c；**待用户全量编译刷机验证** | VM 编译验证，Kalama GKI config 已写 CRYPTO_ECDSA 等 |
| OTG 供电 | VBUS=0（ADSP/UCSI 残缺），**强制 host via USB hub 供电**：`echo host > /sys/bus/platform/devices/a600000.ssusb/mode` | 09-02 调试现场 `2026-09-05_音频调试现场/` 归档 |
| OTG 供电实测 | 09-10 复核：`ucsi-source-psy...ucsi1/online=0 / voltage_now=0 / current_now=0`（板子确实零输出）；同时 `/sys/class/power_supply/usb/voltage_now=11869000`（11.87V）→ **反向由 hub 给板子供电**。带供电 hub 方案成立 | 实战 dumpsys/sysfs 读取 |
| USB 设备模式切换 | ⚠️ 值必须是 **`peripheral`**，写 `device` 无效（读回 `none`）：`echo peripheral > /sys/bus/platform/devices/a600000.ssusb/mode`。成功判据：mode 返回 `peripheral` + `/sys/class/udc/a600000.dwc3/state` = `configured` + adb 出现 `12344321` | 09-11 实测；接手柄前记得 `echo host` 切回 |
| 传大文件通道选择 | **USB 33.5 MB/s ≫ WiFi 2.4G 3.2 MB/s（约 10 倍）**。6.4GB 文件：USB 3m17s vs WiFi 35min。大文件一律走 USB | 09-11 战神2 实测 |

### 2. 编译渊坑（踩过的，别踩）
1. **`<script> 任何模式（inc|full）增量前必删 Image**：`rm -f device/qcom/kalama-kernel/Image`，否则增量不动（★源码级根因 09-11 查明：prepare_vendor 的 COPY_NEEDED 门控**只看 Image 存在与 build.config diff，完全不看 .config/驱动/DT 变化**）。

   **INC/FULL 差异**：两种模式跑的步骤完全相同，仅 `full` 额外跑 `make update-api` + `generate_ota_package`——**并不删 device/Image**。增量改内核/DT/ko，必须手动删 Image → wait prepare_vendor COPY_NEEDED=1 → 搬 dtbo/.ko 正式到刷机包。

   **正确流程**：
   ```bash
   cd LA.VENDOR.15.4.3
   rm -f device/qcom/kalama-kernel/Image   # 触发搬运，inc/full 都吃亏
   ./SNM970_A15_build.sh userdebug kalama 01 inc 2>&1 | tee build.log
   ```

2. **toybox 坏**：`ls -la kernel_platform/prebuilts/build-tools/linux-x86/bin/toybox` 必须 290344 字节；
3. **git add -A**：编译副产物 30+ 个删光，PR 只拉变更文件；
4. **11135 图片**：PNG `chunk()` 误用 `<I` 打包（小端），规范要求大端 `>I`——坏图直接报废整个会话；
5. **TARGET_COPY_OUT_VENDOR**：变量展开空字符串会导致文件未进 vendor 分区；
6. **增量编译 dtbo 过期**：`prepare_vendor.sh` 只看 Image 变化，DT 改动也删 Image；
7. **run_build stderr 被吞**：脚本用 `bash -c "..." 2>&1 > log` 把错误导向终端、日志只记 stdout → 必须 `tee build.log`，否则真错误看不着；
8. **`=y` 不产 `.ko`**：GKI 架构下 msm-kernel 只 `MAKE_GOALS="modules dtbs"`，vendor 驱动 `=y` → 不产 ko → `find *.ko` 找不到 → 不进 vendor_dlkm.img → 刷机包无此驱动。**必须写 `=m`**。
9. **rsync 不清旧产物**：`copy_kernel` 用 `rsync -a`（无 `--delete`），旧 ko 残留 `out/` → 改配置后要全量重跑或删 `out/`；
10. **软链树确认**：`LA.VENDOR.15.4.3 → LA.VENDOR.15.4.3-irix` 是软链（inode 相同），改一边即生效；但历史上若有两份独立目录，易改错地方。

### 3. 日常紧急指令
```bash
adb tcpip 5555                   # 切 host 前打开 WiFi adb
adb root && adb remount          # push 到 /system 必备
adb appops set com.meig.hapticx PROJECT_MEDIA allow
cmd wifi connect-network <SSID> wpa2 <pwd>  # 中文 SSID
settings put global device_provisioned 1   # Settings 进不去
echo host > /sys/bus/platform/devices/a600000.ssusb/mode        # 接手柄/hub（host）
echo peripheral > /sys/bus/platform/devices/a600000.ssusb/mode  # 连电脑传文件（device，★不是 device！）
```

## 二、每日进度速览（最新在前）
| 日期 | 关键成果 |
|------|----------|
| 09-12 深夜 | 板上 **0.1.17**：悬浮马达条 + DSP 改回 Windows analyzer.py。QSSI 预装已换成 0.1.17；kalama.mk A2DP + hapticx_ff 开机 + appops。用户自己 `inc` 刷完即有 App。第一次仍要点「开始捕获」。Git 仓 App 源码仍 0.1.0 |
| 09-12 晚 | 0.1.12 真采+四档，动态档现场过。AetherSX2 丢失后已重装 v1.5-3668，BIOS 从 SSD 补回 |
| 09-11 | 推《战神2》6.4GB 到掌机 SSD；USB `peripheral` 33.5MB/s；GitHub `duck-sleep/win_game` 首推成功 |
| 09-10 | xone 移植完成，VM 编译中；await 全量 build & flash 验证 |
| 09-09 | FF 方案定位：xpad GIP 子集不足，xone 完整握手唯一活路 |
| 09-07 深夜 | 🎉 **蓝牙独立通道打通**：官方 API 复活，auto_test PASS，capture 镜像链路通 |
| 09-05 | AudioPolicyManager 端到端 bug 定位：SPEAKER HAL write 永久阻塞 → 影子轨无数据 |
| 08-30 | SSD M.2 GPIO46 供电驱动完成，PR 合入 master |
| 08-26 | OTG Host Mode 切换 `echo host` + toybox/11135 问题排查 |

## 三、归档 / 历史快照
- 09-05 卡点全景（SPEAKER 线程挂、primary/secondary 输出失效）→ 见 `01_记忆原档\旧项目\...\20260905\topics.md`
- 旧项目 VM 环境经验 → `01_记忆原档\旧项目_VM环境\project_memory.md`

## 四、常见约定
- VM: `tmux attach -t build`；`./SNM970_A15_build.sh userdebug kalama 01`
- adb: `C:\platform-tools\adb.exe`（不在 PATH）
- Gitea: http://106.52.24.80:3005 / 981637988 / LTWLTW200057
- 提交不走 origin (群晖不可达)，`git push gitea <branch>`
- **GitHub: `git@github.com:duck-sleep/win_game.git`**（账号 duck-sleep / `ltw18505222732@gmail.com`）——工作区 `D:\win_game_project` 已初始化并推送 `main`。只跟踪 `03_ai的记忆_和skill` / `12_win_上机跑` / `25_xbox_control`，其余靠根目录 `.gitignore` 挡住。22 端口被 FlClash 拦，`~/.ssh/config` 已把 github.com 固定到 `ssh.github.com:443`
- 弱网推 GitHub 必看 skill `github-push-behind-proxy`（瘦包 + SSH 保活，9.43MB 两次失败 → 4.12MB 一次成功）
- 重刷后 A2DP 丢：从 `.workbuddy/tmp_apmcheck` 或已改进 VM 的 XML push；`setprop persist.bluetooth.a2dp_offload.disabled true`；`killall audioserver`；开关蓝牙
- HapticX 震动桥：`adb shell "( /system/bin/sh /data/local/tmp/run_ff_bridge.sh >/data/local/tmp/ff_bridge.log 2>&1 & ) ; echo FORKED"`。禁止 `pkill -f ff_bridge`；勿对活着的桥 `logcat -c`
- 平台签名：VM `signapk.jar` + `platform.pk8`。大包预装：`LA.QSSI.15.0/vendor/meig/HapticX/HapticX.apk`（现 **0.1.17**），`device/qcom/qssi/qssi.mk:310` inherit `vendor/meig/hapticx.mk`
- 固件一次 inc 应带：HapticX 0.1.17 + `a2dp_offload.disabled=true` + apc/ha 两份策略（md5 `7be27531…` / `4e472f90…`）+ `/vendor/bin/ff_bridge` 开机 + `PROJECT_MEDIA`/`SYSTEM_ALERT_WINDOW` appops。刷完仍要用户点一次屏幕捕获
- 0.1.15/16 用整段 PCM 顶马达会跑满，已在 0.1.17 撤掉；只留 `CAPTURE_SCALE=2.5` 放大 30–130Hz
- 薄低音歌先切 **动态** 档；均衡门限更高可能完全不震
- AetherSX2 包名 `xyz.aethersx2.android`。OnionKnight 主页看不到 sideload 图标，用 `am start -n xyz.aethersx2.android/.MainActivity`
- 用户 09-12：记忆写 `03_ai的记忆_和skill`，技术写 `12_win_上机跑`