---
name: 2026-09-03 工作日志（指针）
description: Review project progress
metadata:
  type: project
---

# 2026-09-03 工作日志（指针）

> 正文在 `D:\win_game_project\03_ai的记忆_和skill\04_workbuddy_记忆与skill\日志\2026-09-03.md`，本文件仅作入口。

- 会话重启：通读 03_ai 记忆区与 04_ai和运行资料，完成上下文重建（未改项目代码）
- 记忆体系落地：WorkBuddy 记忆主存放地确定，新增 `日志\` 分层；新建 skill `snm970-context-recover`
- **11135 坏图根因修复**：`hapticx\ui_preview_profiles.png`/`ui_preview_dynamic.png` 是 `profiles_shot.py` 小端写 PNG 头产出的坏图，导致会话一读雷云复刻项目就挂。已修脚本（`<I`→`>I`）、从 BMP 重生成两张好图、全工作区 PNG 复验 OK；踩坑入 MEMORY.md，诊断流程固化为 skill `hapticx-png-guard`
- **HapticX 频段增益布局修复**：profiles 页超高无滚动+画布写死尺寸导致编辑器被裁出窗外（动态模式下看不见）。`band_gain_canvas.py` 加 resize 自适应；`app.py` 加 `_make_scroll_page` 滚动容器、画布 fill+expand、默认窗口 1100x860；滚轮 bind_all+指针归属判断。截图实测通过
- **频段边界（音频输入范围）可调**：对标雷云，内边界（70/100Hz）画布可拖+数值框可改，按模式存 `mode_band_edges`，analyzer 实时重建 eq_table；外边界 30/200Hz 固定。顺手修 `find_window` 抓错窗口问题。链路 analyzer→pipeline→canvas→app 全打通
- 等待用户确认"重新开始"的任务方向（HapticX / OTG / BSP 出包）
- **新建 `12_win_上机跑\10_安卓雷云技术.md`**：HapticX 搬上安卓掌机方案。结论：priv-app（引擎 system 化+UI 独立雷云界面+Settings 简版开关）；用户已拍板输出目标/界面/定位；音频捕获三路待实测；阶段0=OTG 收官。详见 03 区日志。
- **安卓雷云方案 v2**：VM 核实 xpad 已编入内核但 FF 宏没开（kalama 两 defconfig 加一行即可）；工程两端分离=app 独立 Gitea 仓+VENDOR 树 glue；`10_安卓雷云技术.md` 已更新待 review。教训：找源码位置先看 02_知识库。
- **安卓雷云 app 出 APK**:发现挂掉的雷云会话已在 `25_xbox_control/hapticx-android/` 留下半成品 Gradle 工程+Windows 工具链（D:/android_build/），清理我误建的平行结构后修 5 处 Kotlin 编译错，BUILD SUCCESSFUL 出 `app-debug.apk`（7.3MB），等掌机接 adb 验证音频捕获。手柄线按用户指示挂起（FF defconfig+fftest 已就位）。
- **DSP 对拍 PASS**:抓出 Kotlin 版 FFT 忘乘汉宁窗的移植 bug,修复后 60 块对拍马达偏差 ~5e-13。对拍工具链固化（crosscheck_gen.py + CompareMain.kt,命令在 README）;APK 重出。
- **磁盘盘点**（22:24）:D:\android_build 1.5G（必备 868M+可删残留 618M 等确认）;C 盘仅 ~/.gradle/caches 805M 依赖缓存。详见 03 区日志。
- **OTG 突破**（22:45）:强制 host + 带供电 Hub 全链路打通——Hub(自供电 bMaxPower=0mA)+读卡器均枚举成功,sdi1 挂载 64MB 读 9.4MB/s 零错。铁律:动 USB 模式前先开 WiFi adb(板子现 192.168.31.93:5555,旧 .180 作废)。详见 03 区日志。
- **手柄枚举成功,阶段0收官**（23:10）:雷云 2.4G 收发器(1532:0a3f)枚举+xpad 绑定+event5,全 XInput 能力。坑:手柄关机时收发器不握手(像坏了)。`10_安卓雷云技术.md` 已重写:阶段1也完成(对拍PASS+APK),下一步=APK 装机测音频捕获 opt-out(头号风险)+攒一次刷机(FF宏+自动host+预装)。按键事件流待下次验证。

- **音频捕获实测（23:30）**:APK 装机,授权链路修通(AppOps PROJECT_MEDIA=ignore 是静音元凶,appops set 修复);但最终断点=BSP secondary outputs 影子轨不激活(io 149 上 15 条影子轨全 idle,HAL Frames written=0),采集纯静音。对照 VM 内 AOSP15 源码确认规则正确→判定 QCOM BSP AudioFlinger/APM 缺陷,APK 层无解。下一步:app 自播自采测试→不行就 BSP 修(与 FF 宏攒一次编译)。详见 03 区日志+10_安卓雷云技术.md 增补段。
