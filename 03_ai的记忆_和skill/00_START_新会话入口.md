# 00_START — 新会话 1 分钟读完入口（2026-09-12 深夜更新）

> 冲突时以本文件【当前状态】为准。更多细节见 02_知识库_整理版.md 、04_workbuddy_记忆与skill\MEMORY.md。
>
> **记忆存放（用户 09-12 明确，所有 AI 共用）**：会话记忆、长期事实、每日日志、skill **一律写到** `D:\win_game_project\03_ai的记忆_和skill`。技术文档写到 `D:\win_game_project\12_win_上机跑`。

## 项目一句话
SNM970/OK700 掌机（QCS8550 kalama Android 15 BSP）定制；主战场是「安卓雷云 / HapticX」：系统音频→FFT贝司分析→手柄震动。

## 当前状态快照（2026-09-12 深夜）
| 线路 | 状态 | 说明 |
|------|------|------|
| HapticX Windows 参数调优 | ✅ | M0~M4 + profiles + 模式增益；amp_comp 未补 |
| HapticX Android 现役 | ✅ **0.1.17** | 板上真采 + 四档 + 悬浮马达条。DSP 已改回 Windows `analyzer.py`（只看 30–130Hz）。用户确认「好像还行」 |
| 采集-FF 驱动 | ✅ | xone + `eventN` + `ff_bridge` 实震。**板载 hv-haptics 也有 FF_RUMBLE，别发错** |
| 预装进大包 | ✅ 源已换 **0.1.17** | QSSI `vendor/meig/HapticX/HapticX.apk` = 0.1.17（`.0.1.12.bak` / `.0.1.0.bak`）。`qssi.mk` 已 inherit |
| P2 A2DP/ff 开机 | ✅ 源已齐 | `kalama.mk` offload=true + 两份策略 XML + `hapticx_ff/`（开机桥 + appops）。**尚未 inc 出包** |
| Git 仓 | ⚠️ | 工作区 App 源码仍是 **0.1.0**；0.1.17 只在板子 / VM 预装 APK / 本地工程，**没 commit** |
| OTG / 充电栈 | ⏳ | 带电 Hub 复测未关 |
| SSD | ✅ | `7FEE-F970`：GAMES + PS2/bios |
| AetherSX2 | ✅ 已重装 | 09-12 晚发现丢了，已装回 v1.5-3668 并打开向导 |

## 对 Windows 雷云的差距
| 环节 | 状态 | 说明 |
|------|------|------|
| DSP 菜谱 | ✅ | 0.1.17 与 analyzer.py 对齐；0.1.15/16 用 PCM 顶满是弯路，已撤 |
| 出声（蓝牙） | 🟡 | 板上已 push；源已进 VM，等 inc 进包后重刷不再丢 |
| 马达能震 / 静音能停 | ✅ 0.1.17 | 动态档现场过；悬浮条可在游戏上看到强弱 |
| 偷听系统/游戏声 | ✅ | AudioPlaybackCapture。REMOTE_SUBMIX 本板 peak 常 0，勿当成功 |
| 四档 UI | ✅ | 受控/均衡/动态/自订 + 三柱增益 |
| LRA / 扳机 | ❌ | 两端都没有 |
| SPEAKER / 3.5mm | ❌ | HAL 仍死，出声认 A2DP |

## 今天待办
- 用户自己编大包（不必删 Image）：`./SNM970_A15_build.sh userdebug kalama 01 inc`
- 刷完验：`versionName=0.1.17` 在 `/system/priv-app/HapticX`；`getprop persist.bluetooth.a2dp_offload.disabled` = true；`pidof ff_bridge`
- 刷完仍要点一次「开始捕获」（MediaProjection 系统弹窗没法预装掉）
- 验收清单：`12_win_上机跑\11_安卓雷云技术.md` 第 5 节（`14` 已改成指向 11）
- ⚠️ 发震动前重拿节点：`grep -E 'Microsoft Xbox' -A6 /proc/bus/input/devices`

## 环境速查
VM: ssh laide@192.168.64.130  
代码: `/home/laide/Desktop/10_code/{LA.VENDOR.15.4.3, LA.QSSI.15.0}`  
产物: `vendor/vendorcode/build/SNM970_userdebug_01.zip`  
ADB: `C:\platform-tools\adb.exe`  
WiFi adb: 上次 `192.168.31.228:5555`（重启会变）  
App: 板上 **0.1.17**（priv-app stub 仍 0.1.0，数据区覆盖）。下次 inc 预装就是 0.1.17。签名必须 VM `platform.pk8`  
音箱: SRS-XB10 `B8:D5:0B:3E:EB:CC`  
手柄: Razer 1532:0a3f，近期 event5  
SSD: `/mnt/media_rw/7FEE-F970`（文件管理器里叫「安卓」盘）

## 工作约定
- 中文；VM / 6h 编译 / 刷机 **用户自己动手**
- 绝不 `git add -A`；改内核先 `rm -f device/qcom/kalama-kernel/Image`
- 记忆写 `03_ai的记忆_和skill`，技术写 `12_win_上机跑`

## 新会话阅读
- 状态 → 本文件
- 安卓雷云 → `12_win_上机跑\11_安卓雷云技术.md`（第 1–2 节：Linux 对照 + 安卓术语；第 5 节验收；历史在文末附录）
- Windows 雷云 → `10_动态触觉反馈技术.md`
- PS2 / 传 ROM → 本文件「掌机资源」+ skill `push-to-snm970-storage`

## 掌机资源（09-12 复核）
| 资源 | 路径 |
|------|------|
| PS2 模拟器 | AetherSX2 `xyz.aethersx2.android` v1.5-3668。APK：`E:\@【已整理】经典游戏rom\roms\ps2\AetherSX2-v1.5-3668.apk` |
| PS2 BIOS | 内部 `/sdcard/PS2/bios/`（09-12 从 SSD 补回）；SSD 备份 `/mnt/media_rw/7FEE-F970/PS2/bios/`。推荐 scph39001.bin |
| 游戏 | SSD `GAMES\`：战神2 `.chd`、寄生前夜 `.iso`、game.iso、jade-garden-serenade.mp3 |
| PSP 模拟器 | 系统预装 PPSSPP |
| 前端 | OnionKnight（`app.gamenative`）。**新 sideload 的应用不会出现在这页**，要用 `am start` 或系统桌面 |

## 永久有效坑（Top）
1. 改内核/DT/.ko 先删 `device/qcom/kalama-kernel/Image`
2. WiFi adb 先 `tcpip` 再 connect 板子 IP
3. `appops set com.meig.hapticx PROJECT_MEDIA allow`
4. 自播自采禁止主线程 AudioTrack 写 SPEAKER
5. `pkill -f ff_bridge` 会杀到自己；勿在桥活着时 `logcat -c`
6. USB 传文件写 `peripheral` 不是 `device`；完事切回 `host`
7. 禁止 `git add -A`；刷机前 debugfs 验包
8. 重刷丢 A2DP 策略：push apc_btq/ha_btq + `a2dp_offload.disabled=true` + 杀 audioserver + 开关蓝牙
9. 均衡档对薄低音可能不震，先切 **动态**
10. 桌面是 OnionKnight 时，新装 App 图标看不见 ≠ 没装上
11. 安卓采集瘦时**不要**用整段 PCM 顶马达（0.1.15/16 条会跑满）。只放大 30–130Hz（`CAPTURE_SCALE`），映射跟 Windows 走
12. `hapticx_ff.rc` 用了 `seclabel u:r:su:s0`，只适合 **userdebug**，user 包桥起不来
