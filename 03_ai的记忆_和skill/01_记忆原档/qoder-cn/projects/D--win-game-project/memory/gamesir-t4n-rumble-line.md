---
name: gamesir-t4n-rumble-line
description: 盖世小鸡 GameSir T4n 振动/唱小星星线：Windows 枚举身份已实测、"老枚举"根因、马达能力上限、待定的路线分叉
metadata:
  type: project
---

# 盖世小鸡 GameSir T4n 线（工程 `D:\win_game_project\27_small_chicken_controller\`）

**事实（2026-11-06 00:07 本机实测，只读探针 `tools\probe_usb.py`）**：T4n 插上 USB 后在 Windows 里是
**Xbox 360 兼容手柄**：`045E:028E`，HID 集合 `HID\VID_045E&PID_028E&IG_00`（usage_page 1 / usage 4 Gamepad），
设备序列号 `3286963A`，产品串 `Controller (Xbox 360 for Windows Controller)`，驱动 = 微软官方 `xusb22.inf` /
`XnaComposite`（厂商串显示 "Microsoft" 是驱动给的，不是设备写的）。三个节点状态全 `OK / CM_PROB_NONE`。
`hidapi` **能打开**这个集合（`open_path` 成功 ⇒ 裸 HID 可读可试写）。

**Why**：用户买它是想复刻 `24_machine_teacher_control` 那套"音频转振动唱歌"。
**How to apply**：这只手柄和机械师/雷蛇**不是一类设备**，别照搬 NS `0x10` 协议就以为有频率；先确认型号档位再定范围。

## 🔴 能力上限（资料已核实，别自欺）

- **机身标贴（用户 2026-11-06 提供）**：FCC ID `2AF9S-T4N`、CMIIT ID `2024DP6412`。
  ⇒ 只证明两件事：**它有无线电发射器**（有线-only 设备不会去核 FCC/CMIIT，所以是 2.4G/蓝牙款）+
  **2024 年送核**（按工信部编码规则前四位是年份）。**核准代码里查不出马达类型**，FCC 文档接口本机拿不到（403）。
- **型号判定（2026-11-06，资料推断，用户还没确认背面有没有"NS"）**：FCC `2AF9S-T4N` + 用户说"没有接收器"
  ⇒ 大概率是**盖世小鸡 启明星（T4 Nova）本尊**，官方参数 **震动马达 = XBOX 同级非对称摆锤马达**（摆锤=转子 ERM）、
  连接=蓝牙/有线、**2.4G 接收器需另外购买**、轮询率 **有线 500Hz / 无线 125Hz**、600mAh。
  官方那句"**更是一个会'唱歌'的马达**"只用在 **启明星 NS 版**（PS5 同类型**音圈**线性马达）和 **九尾狐 T3Pro**（音圈，
  支持 Switch HD + PC 适配）上 ⇒ **背面型号带 NS 的话这条线完全变天，先问清楚再动手。**
  ⚠️ 来源互相打脸：smzdm 一篇 Switch 横评把"超新星"标成"HD 震动"，sohu/zol 标成"Xbox 同级非对称转子马达"
  ⇒ 资料不可靠，**以本机喂频率字节后的手感实测为准**。
- T4n 这一族的公开规格（2018 款评测 + 2024 家族页）：**非对称双转子马达（一大一小 ERM）**、
  **震感 5 档 = 手柄上 `TURBO + 上/下方向键` 调**（不是主机侧调）、蓝牙/2.4G/有线三模、无机械电源开关、
  30 秒未连接或 180 秒无操作自动休眠。超新星/启明星 NS 版才是"Xbox 同级转子 / 音圈"的分水岭。
- 官方 FAQ + 社区拆解：**这一族只有 2 只转子马达（ERM）**，官方参数只写"双振动、档位调节"。
- 360 兼容身份下主机侧只有 `wLeftMotorSpeed / wRightMotorSpeed` 两根 0–65535 的强度线，**没有频率这一维**；
  SDL2 的 XInput 后端源码就是直映射这两个值，语义只有 constant；xpadneo 要额外 quirk 才能震动，反证它只有左右马达脉冲位。
- ⇒ **唱不出音高**。能做到的是"节奏 + 强弱 + 两只马达的音色差"；ERM 的转速会随驱动力变（音高跟着漂），
  属于可利用但不精确的量，要做成"能听出起伏"而不是"唱准"。
- 唯一的例外线索：**启明星 NS 版**（同族不同型号）用音圈/线性马达、支持 Switch HD 震动
  （贴吧/拆机实测：高频弱、启停拖尾、断电后余震、PC 模式比 Switch 模式还弱）。
  **如果用户手里这只是 NS 版，切到红色 NS Pro 模式后可能枚举成 `057E:2009` ⇒ 能直接复用 24 的协议栈。**

## "一插就好像老枚举"的根因（已证 / 未证分清）

**已证（本机日志）**
- 2026-11-06 00:07:28 这次插入**一次到位**：4 条 Kernel-PnP 400/410 都在同一秒，之后无重连 ⇒ 设备本身没在抖。
- 注册表 `USB\VID_045E&PID_028E` 有 **6 个实例：2 个按序列号（`1DD5F3D`、`3286963A`）+ 4 个按物理端口**
  （`5&299d89e&0&2 / 0&3 / 0&10`、`6&2deab1fc&0&3`）⇒ **换口 = 新设备 = 重装驱动**，这是"每次都像新设备"的机制。
- 2026-11-05 22:18:19→22:18:45 `DeviceSetupManager` 对同一设备连续"提供服务"6+2 次（多次写 0 个属性，
  最长单次 2518 ms），每条后面都跟 `无法建立与 Windows 更新服务的连接` ⇒ 新身份 + 离线 ⇒ Windows 反复重试驱动安装。
- `VMUSBArbService` Running 且有 `vmware-vmx` 进程 ⇒ **当时有虚拟机在跑**，VMware USB 仲裁给每个插入设备建一份
  `Vid_0E0F&Pid_0001` "VMware USB Device" 节点（历史 24 个）。
- `USBPcap`（Wireshark）Running，是装在**所有** USB 设备上的 UpperFilter；另有 ViGEmBus、Razer Synapse（RazerAppEngine×8）、
  网易 GameViewer（虚拟键鼠注入）在场。
- 历史失败节点：`ROOT\USB\0000` = `USB Device(VID_1f3a_PID_efe8)` `CM_PROB_FAILED_START`（代码 10）；
  1F3A=Maxio，常见于国产 2.4G 接收器主控。当前未在线，属遗留。

**未证**
- 是不是曾经**长按误进蓝牙配对模式**导致反复连/断（社区/官方售后给的头号原因，本机蓝牙当前开着）。
- **手柄与接收器固件版本不匹配**（社区说 4200/6300 不兼容，6300 只能在真机升、虚拟机里升不了）。
- 前置面板/Hub 供电、USB 选择性暂停、纯充电线这几条还没在本机复现过。

## 待拍板（用户给信息才能走）

1. **确切型号**：启明星 / 启明星 NS / 超新星(T4n Pro) / T4n Lite —— 决定转子还是音圈，也就是能不能唱。
2. **有没有 D-input 档**（背后拨轮或组合键），因为 360 身份已经把设备交给微软驱动，裸 HID 写报文不一定被听。
3. 走 **XInput**（`25_xbox_control` 里现成的 `xinput_out.py` 那条路）还是先试裸 HID 输出报告 —— 前者稳、后者可能白干。

## 路线（2026-11-06 定的顺序，别再乱试）

1. **USB + 360 身份是主路**：有线 500Hz、不会自动休眠、XInput 直接可用；蓝牙（蓝灯 DS4 模式）身份变
   `Wireless Controller`，震动**同样只有两根强度线**，还要走 BT HID 输出报告 ⇒ **零收益，先别碰**。
2. **先跑阶梯测试再定产品**：`tone_xi.py --ladder`（左 6 档 / 右 6 档，各 1.6 秒，退出归零），
   用户回答"6 档是 6 个音高，还是 6 个响度" ⇒ 听得出 ≥3 个台阶才做"哼歌版"，否则做"鼓点版"。
3. **唯一值得折腾蓝牙的理由**：背面型号带 NS（音圈）且 NS 模式禁有线 ⇒ 枚举成 `057E:2009` 时把 24 的
   NS `0x10` 协议栈指过来实测。用户还没看背面，**这条是悬着的**。
4. 已知坑：纯充电线不通信（XInput 会报空）、180 秒无操作自动休眠、换 USB 口 = 新设备重装驱动。

## 工具清单（都是只读或"退出必归零"，可复跑）

`tools\probe_usb.py`（枚举 / `--watch N` 每秒扫上下线 / `--open` 试开）、
`tools\probe_windows_pnp.ps1`（PnP 事件史 + 问题码 + 游戏控制器类）、
`tools\probe_windows_env.ps1`（内核驱动、UpperFilters、XnaComposite 幽灵实例）、
`tools\probe_usb_power.ps1`（USBPcap/选择性挂起/省电位/驱动服务重试）、
`tools\probe_usb_registry.ps1`（每个 VID/PID 建过几个实例、按序列号还是按端口）；
`插拔监视.bat` = `probe_usb.py --watch 300` 的双击入口；`振动阶梯.bat` = `tone_xi.py --ladder` 的双击入口（会震，拿在手里再点）。
`tone_xi.py` 走 XInput（ctypes 加载 `xinput1_4/1_3/9_1_0`）：`--ping` 只查在线序号不震、`--ladder` 六档阶梯、
`--level/--side/--sec` 手动单档；结构体对齐按官方 `XINPUT_VIBRATION`，finally 里一定归零。
各脚本同级有 `*.out.txt` 本机证据（`tools/tone_xi_ping.out.txt` = 2026-11-06 那次 XInput 查不到的记录）。

相关：[[machenike-g6v2-hd-rumble-line]]（同项目另一条振动线，NS 0x10 协议栈在那边）、
[[feedback-instrument-and-explain-metrics]]、[[feedback-no-disruptive-probes]]
