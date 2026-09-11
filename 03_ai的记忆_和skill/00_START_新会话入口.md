# 00_START — 新会话 1 分钟读完入口（2026-09-11 更新）

> 冲突时以本文件【当前状态】为准。更多细节见 02_知识库_整理版.md 、04_workbuddy_记忆与skill\MEMORY.md。记忆+skill 在 03_ai的记忆_和skill，技术文档在 12_win_上机跑（01~12）。

## 项目一句话
SNM970/OK700 掌机（QCS8550 kalama Android 15 BSP）定制；主战场是「安卓雷云 / HapticX」：系统音频→FFT贝司分析→手柄震动。

## 当前状态快照（2026-09-11 11:00）
| 线路 | 状态 | 说明 |
|------|------|------|
| HapticX Windows 参数调优 | ✅ | M0~M4 + profiles tabs + 模式增益 config.json 已落地；amp_comp 未补；每个 band 音频范围拖拽已对齐雷云 UX |
| HapticX Android 采集链路 | ✅ | **🎉 09-07 大胜利**：官方音频播放 API 复活（MediaSession+fftest），auto_test PASS；Bluetooth_qti/apc_btq 已生成并落地 VENDOR；`persist.bluetooth.a2dp_offload.disabled=true` 为启动前提 |
| 采集-FF 驱动 | ⏳ | xone `=m` 已产 ko（09-11 dist 验证 EXIT=0）；但被 prepare_vendor 的 COPY_NEEDED 门控挡在 vendor_dlkm.img 外——**改过内核驱动必须 `rm -f device/qcom/kalama-kernel/Image` 才会重搬 ko**（09-11 实测根因）；待重跑 target 阶段 + debugfs 验包再刷 |
| Haptics 输出 | ⚠️ | appops MediaProjection 已破，音频采集跑通；强制 host + 带电 Hub 需实测供电 |
| OTG / 充电栈 | ⏳ | 内核补丁已验证，ADSP UCSI/VBUS 还需带电 Hub 复测 |
| SSD 枚举/挂载 | ✅ | PR 已合 master |
| BSP 编译 | ⚠️ | 仅全量 `./SNM970_A15_build.sh userdebug kalama 01`，构建超 6h，**用户自己跑** |

## 今天待办
- 重跑含 xone 的 vendor_dlkm：`rm -f device/qcom/kalama-kernel/Image` → 重跑 target 阶段（prepare_vendor 重搬 ko）→ `debugfs -R "ls /lib/modules" vendor_dlkm.img | grep xone` **验到才刷**
- 刷机后验证：`ls /vendor/lib/modules/xone*.ko` / reboot 后 `lsmod` / 上手柄测 FF+LED
- ⚠️ 教训固化：skill `snm970-fake-build-success-check` + `12_win_上机跑\04_快速编译指令.md`「假成功根因」6 条

## 环境速查
VM: ssh laide@192.168.64.130 (6vCPU/43G/1.3T)  
代码: /home/laide/Desktop/10_code/{LA.VENDOR.15.4.3, LA.QSSI.15.0}  
产物: vendor/vendorcode/build/SNM970_userdebug_01.zip  
Git: Gitea http://106.52.24.80:3005 (981637988)  
ADB: `C:\platform-tools\adb.exe` (不在 PATH)  
WiFi adb: `adb tcpip 5555; adb connect <板子IP>:5555`（连板子，不是 VM）

## 工作约定（用户明确）
- 中文沟通；VM 配置 / 6h 编译 / 刷机验证 **用户自己动手**
- 构建期间 AI 只回答问题，不动代码
- 绝不 `git add -A`；内核改动后先 `rm -f device/qcom/kalama-kernel/Image`
- 提交格式：`[SNM970_A15][TaskID]编号 [Description]... [Solution]... [Owner]...`

## 新会话阅读路线（按需）
- 只看状态 → 本文件足够
- 要干 HapticX Android → 先读 12_win_上机跑\11_安卓雷云技术.md 顶部【新阅读指南】→ 读 **🎊09-07 大胜利 + 🛠️09-10 xone 端到端移植** 两章节（后为历史归档）
- Windows 侧 HapticX → 12_win_上机跑\10_动态触觉反馈技术.md
- 编译/BSP 坑 → 02_知识库_整理版.md；快速指令 04_快速编译指令.md
- 外部交接 → 11 的「📌 试用期终结归档」自成体系
- **勿读**：03_ai\01_记忆原档（冷档备份），12_win_上机跑\_archive（现场调试残留）

## 高频命令
```bash
# 三大回路
adb shell media command --get version
adb shell dumpsys media.audio_flinger | grep -A 200 "Active playback threads"
adb shell "run-as com.snm970.audioinput.teste... dumpsys ..."
# FF 验证
adb shell getevent -l
adb shell dmesg | grep xpad
# 验包（刷机前必做）
debugfs -R "ls /lib/modules" vendor_dlkm.img | grep xone
```

## 永久有效坑 Top 10
1. **改过内核驱动/DT/.ko，先 `rm -f device/qcom/kalama-kernel/Image`**（否则 prepare_vendor 的 COPY_NEEDED=0 跳过搬运，"编了没进包"——09-11 实锤根因）；2. WiFi adb 先 tcpip；3. PROJECT_MEDIA、ignorelist；4. appops MediaProjection；5. toybox 290344 改机；6. `TARGET_COPY_OUT_VENDOR` 权限；7. 11135 损坏图片；8. media 命令缺失（service initsnm 替补）；9. `git add -A` 禁止；10. **打包完成别信 DONE，刷机前用 debugfs 验包**
