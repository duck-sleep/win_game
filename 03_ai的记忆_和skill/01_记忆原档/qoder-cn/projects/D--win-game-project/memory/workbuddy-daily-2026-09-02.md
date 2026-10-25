---
name: 2026-09-02 工作日志
description: Review project progress
metadata:
  type: project
---

# 2026-09-02 工作日志

- 读取 `03_ai的记忆_和skill/`（README、02_知识库_整理版、03_skill清单、原档 project_memory/topics），完整恢复 SNM970 项目上下文，长期要点已沉淀到 `.workbuddy/memory/MEMORY.md`。本会话仅上下文加载，未改动项目文件。
- 重新扫描更新后的记忆目录：SSD 阶段已收官（PR 合入 master），当前主战场为 HapticX 动态触觉反馈（25_xbox_control\hapticx\）；掌机 OTG 供电受阻。按用户要求建立 `03_ai的记忆_和skill\04_workbuddy_记忆与skill\`（README + MEMORY.md + skills\），作为 WorkBuddy 记忆与 skill 的主存放地；`.workbuddy/memory/MEMORY.md` 改为入口指针；并更新了 `03_ai的记忆_和skill\README.md` 的目录结构说明。

## OTG 手柄不枚举：根因定位 + 补丁（深夜会话）
- WiFi adb 连上设备（192.168.31.180:5555）做全面诊断：dwc3 已 host 模式、ucsi_glink/altmode 已绑定、UCSI 能力查询通，但插手柄 0 事件、插 PC 时 `pmic_glink_rx_callback: No client present for 32778`。
- **根因（VM 源码实锤）**：`qti_battery_charger.c` probe 开头有 czw（Meig ODM，随 lijie 2025-10-28 提交 deea42bbd3e 混入）的 Micro-USB ID 引脚检测代码，`id-gpios` 缺失时 `return -EINVAL`；本机（KalamaP HDK，纯 Type-C）DT 全目录无 `id-gpios` → 充电驱动 probe 必败 → battery/usb psy 不存在 → eUSB2 PHY "Could not get usb psy" → 充电栈+VBUS 全断。32778=MSG_OWNER_BC，丢的正是 BC 消息（此前误判为 UCSI）。
- **已打补丁（VM 内核仓库 ssd-m2-nvme 分支工作区，+5/-3）**：① 无 id_gpiod 时不再 return -EINVAL（Type-C 板跳过 ID 检测，角色切换交给 UCSI）；② `usb_conn_queue_work` 加 `!conn || !conn->id_gpiod` 守卫，防 czw 机制在 Type-C 板上与 UCSI 抢角色（NONE 角色会杀 host 模式）。
- **快速验证路线**（已确认可行）：内核单模块增量编译（kernel_platform/build.build.sh，与 SNM 脚本 build_kernel 同命令）→ `out/msm-kernel-kalama-consolidate/dist/qti_battery_charger.ko` → adb push 热替换（设备已 root；CONFIG_MODULE_SIG_FORCE 未开且厂商改的 MODULE_SIG_PROTECT 把 sig_enforce 硬编码 false，未签名模块可 insmod）→ rmmod/insmod → 验证 psy/插手柄。编译由用户跑（曾误启动一次已 kill）。
- 待验证后走正式流程：完整 SNM 脚本出包刷机 + gitea PR。

## 补丁热替换 + host 模式绕过实验（晚间会话，WiFi adb @ 192.168.31.241:5555）
- WiFi「今天鸭鸭还好困」(00000000) 连接成功；中文 SSID 无坑，之前失败是距离（-83dBm assoc_no_ack_received）。
- 设备重启过 → 补丁模块被还原 → 重新热替换（卸载链 camera→leds_qti_flash→hv_haptics→swr_haptics→qti_battery_charger，insmod /data/local/tmp/qbc_new.ko，再全部恢复）→ probe 成功，battery/usb/wireless psy 全现。
- 补丁效果实锤：BC 消息被正常消费（No client present 消失）、eUSB2 PHY 拿到 psy（Avail curr from USB）、电池温度 -40 垃圾值→10°C、插充电器能测到 VBUS 4.97V。
- 但 ADSP 固件层仍断：UCSI 连接事件从不上报（typec partner 永不出现）、强制 source 被忽略、VBUS 不输出、充电不使能（online=0/Discharging）。
- 突破：`echo host > /sys/bus/platform/devices/a600000.ssusb/mode` 绕过 CC/UCSI 强制 host，xHCI 枚举成功；orientation 可 A/B 强制。手柄（自带电池开机亮灯）仍不枚举 → 无 VBUS，总线供电设备 USB 芯片不上电。用户无带电 Hub，待后续验证。
- 今日刷机包不含新 .ko（打包未拾取 kernel dist 单模块产物），正式出包需排查。
- 实验日志：25_xbox_control/{gamepad_test3,host_mode_gamepad,host_awake_gamepad,host_phy_rebind_gamepad}_20260902.log。重启可恢复全部运行时改动（host 模式/模块热替换均非持久）。

## HapticX UI 重构（对标官方雷云 Synapse）
- 依据用户 3 张官方截图，重写 `25_xbox_control/hapticx/` 纯 UI 层，管线（analyzer/config_store）未动
- 改动文件：`ui/theme.py`（深色主题+雷蛇绿 #44D62C）、`ui/widgets.py`（胶囊页签/药丸开关/圆钮滑条）、`ui/band_gain_canvas.py`（谱图背景+频段块+拖拽把手）、`app.py`（顶部模块栏+居中页签版式）
- 冒烟测试通过（WALK_OK/SMOKE_OK）；用系统 Python 跑（托管版无 tkinter）；BMP 截图需纯 Python zlib 转 PNG
- 截图预览：`ui_preview_dynamic.png`（1116×819）；截屏工具 `capture_window.py`
- 注：会话内图片上传通道故障（错误码 11135），无法回读图片给 AI 看，效果由用户自行确认
