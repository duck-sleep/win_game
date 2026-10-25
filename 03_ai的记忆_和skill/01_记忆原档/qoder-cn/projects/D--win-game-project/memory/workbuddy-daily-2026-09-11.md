---
name: win_game_project 工作日志 2026-09-11
description: Review project progress
metadata:
  type: project
---

## 复查补漏（二）——dtbo 增量过期 = 坑 4b（12:00 用户追问后补）
- 用户提示：之前参考设备树那次，以为编译进去了结果没有、来回查找——04 文档漏了这起独立 incident
- 读 08_ssd部署分析.md §3.5-3.6 核对细节：改 overlay DTS，增量编译跑成功但 dtbo.img 仍旧值（boot-option 未变、GPIO46 hog 未生效）
- 根因与 ko 同一个 COPY_NEEDED 门控：prepare_vendor 只看 Image + build.config，不看 dtbo 时间戳；首次全编铺旧 kp-dtbs 后，后续增量交接拷贝全被跳过
- 修复（与 ko 相同）：改 DTS 后增量前先删 device/qcom/kalama-kernel/Image（dist/Image 还在不会重编内核，prepare_vendor 秒级重铺 kp-dtbs+.ko+Image）
- 已写进 04 文档：新增「坑 4b：dtbo 增量过期」小节（证据标注 08-26 现场 + 源码行 201-280）+ 流水线图加坑4b分支 + 自检清单加 extract_dtbo.py 验 dtbo 项

## GitHub 建仓 + 首推成功（15:00~15:40）
- 仓库 `git@github.com:duck-sleep/win_game.git`，工作区 `D:\win_game_project` 已 init + push main（提交 `103ad5b`）
- 只跟踪 `03_ai的记忆_和skill` / `12_win_上机跑` / `25_xbox_control`，根 `.gitignore` 挡掉烧录包/游戏镜像/工具
- 前两次 push 失败（`unexpected disconnect while reading sideband packet`，19s / 6m14s 断）→ 根因 FlClash TUN 走境外节点，到 GitHub 实测仅 82~236 KB/s
- 解法：瘦包（踢掉 `*.bmp` / `*.wav` / 编译好的测试二进制）26.03MB→7.17MB、git 包 9.43MB→4.12MB，再加 SSH 保活（`ServerAliveInterval=15` + `pack.threads=1`）→ 1m51s 成功
- 详细流程与错误速查见 `03_ai的记忆_和skill\04_workbuddy_记忆与skill\skills\github-push-behind-proxy\SKILL.md`

## 17:55 WiFi adb 打通 + xone 上板确认
- 按 01_工程说明.md 第5/7节指令：cmd wifi connect-network Duck wpa2 00000000 → 连上 2.4G Duck（192.168.31.208，RSSI -40）→ adb tcpip 5555 → adb connect 成功
- ★环境发现：WorkBuddy 沙箱每条 Bash 命令结束后杀掉 adbd 后台进程，connect 状态活不过单条命令。对策=把 connect 和后续 shell 命令拼进同一行执行
- ★里程碑：lsmod 确认 xone_wired / xone_gip / xone_gip_gamepad 三模块已在板上加载（refcount: gip 被 wired+gamepad 引用=2）——09-10 移植 → 09-11 进包 → 09-11 加载，全链路闭环
- ssusb mode=peripheral（USB 正常连电脑）；下一步：接 hub+雷蛇收发器前 echo host 切角色，验证手柄枚举绑 xone

## 09-12 00:30 教训：adb 用 IP 前必先 devices 扫描
- 我反复对着旧 IP 192.168.31.208 敲 connect，失败后误报"WiFi adb 断了"——实际设备 DHCP 换址为 192.168.31.172，用户自己 adb devices 一眼看到。
- ★纪律：每次用 WiFi adb 前先 `adb devices` 取活地址，绝不硬记上一轮 IP；DHCP 会变、旧的 :5555 条目会变僵尸。
- 另：WorkBuddy 沙箱命令间会清 adb server，connect 与后续命令要拼同一条。

## 09-12 00:35 ★里程碑：xone 全链路闭环验证

设备：Razer Wolverine V3 Pro for Xbox (VID 1532 : PID 0a3f) 经 VL817 (2109:2817) hub 接入 OTG 口

一、模块加载（dmesg 均为 (E)=loaded）：
  xone_wired(E)    → 固件通信层 → input5
  xone_gip(E)      → HID 解析层 → input6
  xone_gip_gamepad(E) → 手柄映射层 → 内嵌于 xone_gip

二、驱动绑定（kernel 官方路径）：
  Bus=0006 Vendor=1532 Product=0a3f → Microsoft Xbox Controller → gip0.0/input/input6
  Sysfs 路径：platform/soc/a600000.ssusb/.../gip0/gip0.0/input/input6

三、FF 震动能力位（B: FF=107030000 0）→ 已启用；09-06 固件已就位 CONFIG_JOYSTICK_XPAD_FF=y

四、电源节点（/sys/class/power_supply/gip0.0，状态 Not charging）→ 板供电监测正常

结论：09-10 移植 → 09-11 进包（inc 模式，删 Image 后）→ 09-12 刷机 → **09-12 00:35 确认加载成功**。xone FF 全栈跑通。
