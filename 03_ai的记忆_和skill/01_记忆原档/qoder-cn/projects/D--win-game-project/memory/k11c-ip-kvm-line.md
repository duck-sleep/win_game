---
name: k11c-ip-kvm-line
description: K11C(RK3566) JetKVM 式 IP-KVM：文档两层(给人/给AI)+§9 任务清单；10-18 T0–T8 闭环、10-19 软路径判死、10-20 T14/T15 电脑侧闭环（WebRTC=Go+pion 静态二进制，H.265 1080p60 零丢帧，板子 CPU 38% vs 软路径 370%）；含镜像坏 gadget 脚本会回退、板子靠 Type-C 供电、量渲染不能用 Qoder 内嵌浏览器、输入法是开关等坑
metadata:
  type: project
---

2026-10-16 起，K11C 板上开第二条用途线：**把它做成一台 JetKVM 式 IP-KVM**（远程看被控机画面 + 伪装键鼠控制 + 远程开机）。
方案文档：`D:\win_game_project\12_win_上机跑\14_K11C做JetKVM式IP-KVM_方案.md`（先总后分：结论→Q1–Q12 问题清单→逐条展开→排期）。
板子本身的编译烧录见 [[k11c-rk3566-line]]。

## 已定的路线（别再重新论证）

- **不自建/不移植 JetKVM 固件**：`jetkvm/kvm` 是 GPL-2.0 且视频管线绑 RV1106（Mini 更是 ESP32-P4 裸机）；
  org 里**没有原理图/Gerber/BOM**，抄硬件走不通。PiKVM 是 GPL-3.0 且官方只支持树莓派 → 只当**参考实现**。
  走**路线 C 自建精简栈**（UVC → 编码 → WebRTC/MJPEG；configfs HID；薄控制面），每块都是可替换通用件。
  GPL 边界规则：只看它的设计/接口自己写不传染；复制改造它源码就是衍生品，必须开源。
- **三条能力里只有"视频入"能被假掉**。HID 出必须有第二台机器当宿主（做不了假），带外网络省不掉（**已定走 WiFi**）。
- **用户 2026-10-16 的关键提议（已采纳）**：先不等 HDMI 输入，用**假源**把整条软件栈跑通 ——
  一张底图 + `drawtext` 每帧覆写**实时毫秒表** → 编码 → MJPEG/HTTP 上浏览器 → 拍屏量端到端延迟。
  取的是**渲染前内存里的那一帧**，完全不碰 HDMI 电气层。
  ⚠️ 由此推出的纪律：**P5 换真源之前，一个延迟指标都不许报**（假源测不到采集段），报告里要分段写。
- **2026-10-16 第二次改口（用户提"把采集棒去掉行不行"）→ 视频入定成三档**：
  档1 假源（证链路）→ **档2 被控机推屏 agent（零成本拿真画面，帧里带生成时间戳，延迟可直接算）** →
  **档3 采集棒（按需才买，可长期推迟）**。P5 因此不再花钱，BOM 变成"P1–P5 一件都不买"。
  🔑 **关键论证（下次别再重新推一遍）**：**档 2 能覆盖的场合 = 被控机已开机、装了软件、能上网 —— 那种场合本来就有 RustDesk；
  KVM 的价值恰恰在档 2 瞎掉的时刻（BIOS / 重装 / 蓝屏 / 没网 / agent 没起来）。**
  所以采集棒不是"能不能省"，它决定这台东西是 **KVM** 还是 **远程桌面中继**。
  JetKVM 自己也是这么分层的：硬件采集是本体，另出 "JetKVM OS Services"（guest 内采到 4K、剪贴板、终端、传文件）→ **并存，不互替**。
  ⚠️ **档 2 的坑**：帧带时间戳 ≠ 延迟可信，**两端时钟不同步算出来就是假的** → 必须先测 offset 或用"拍屏读毫秒表"校准。
- **2026-10-16 定稿（用户："被控电脑不用搞这些，就是开着的 Windows"）→ 档 3 采集棒 + 继电器 全部排除**：
  **最终硬件清单 = 板子 + 原装电源 + 一根 USB-C→A 线 + WiFi，一个新件都不买。**
  画面由**被控机 agent 截屏编码推给板子**（编码在 x86 上做，板子只转发）；板子的不可替代价值收缩为
  **"OS 挡不掉的 USB 键鼠"那一条腿**。放弃清单已写进 §1.2-B′（BIOS/重装/蓝屏/死机时画面和键盘一起瞎）。
  ⇒ 连带改动：**P3-A 从"测软编够不够"降级为冒烟测试**（编码不在板子上了）；
  **P5=档2 且是最终形态**；**P7 只剩供电+外壳，继电器不做**；Q5 关闭（内容留作回头参考）、Q12/Q10-BIOS 权重下降。
  🆕 **Q13 三条运行前提**（不做就"瞎"）：被控机永不休眠（注意关屏可能返回黑帧）、
  agent 开机自启+断线重连（重启后 60 秒内自己回来）、地址可寻 ——
  💡 **推荐让 agent 反向连板子**（板子开监听、IP 固定），这样只需固定板子一个地址，还顺便避开被控机入站防火墙。
  🆕 **Q14 画面过不过板子** → 建议**过**（单一入口、手机只记一个地址、只转发不重编≈零负载）。
- **2026-10-16 清单复核（用户主动要求"再对一下"）→ 又补 3 条我们自己的决定生出来的问题**：
  **Q15 被控机 agent 要自己写**（截屏 DXGI Duplication / 编码 / 推流 / 自启；
  🔴 **坑：做成 Windows 服务会截到黑屏，必须在用户会话里跑**；可先用 Sunshine/RustDesk 当替身，
  但**现成方案给不了带时间戳的帧**；Sunshine GPLv3 / RustDesk AGPLv3，别把代码抄进我们自己的 agent）；
  **Q16 被控机不接显示器可能截到黑帧**（headless 才撞上；解法 HDMI 诱骗头 10–20 元，**不是采集棒**，或虚拟显示器驱动）；
  **Q17 谁能操作这台设备**（板子开着能替你敲键盘的端口 ⇒ 至少绑地址+服务端口令，出门靠 Tailscale；
  **P4 做控制页时就带上，别等 P6 补**）。
  同时**降级**：Q6（硬编不再是瓶颈）、Q1（两个 A 座空着，只当 Q2 的交叉验证）、Q10 的"BIOS 那半"作废。
  📐 清单加了**口径图例**：🔴阻塞=不做一步都走不了（只有 Q3）｜🔴前置=某阶段前必须做完（Q8/Q8★/Q13）｜
  🟠定形态｜🟡影响体验｜⚪已关闭。**"阻塞只有一个"和"有 4 个红字"这两件事必须分开说**，别混。

## 2026-10-16 第二次收缩（用户 8 条回答）→ 现在的真实范围

**被控机 = 用户当前这台 Windows 笔记本；目标只验两件事**：① 插上去 Windows 把它当键鼠、记事本真能打字；
② 浏览器能看到带毫秒表的画面。**现阶段在被控机上唯一动作 = 插一根线，不装任何东西**（B3 原话"先别装怪东西"）。
⇒ **P5（agent 推屏）整体挂起**，Q13/Q14/Q15 跟着挂起；**Q16 关闭**（笔记本自带屏幕，没有"拔显示器黑帧"问题）；
**Q17 关闭**（C4"不管安全"）；**Q12 复活**（C5：以后要在 HDMI out 接显示器 —— 但要说清它只能显示板子自己渲染的东西）。
**Q4/Q5 仍关闭**（采集棒不买）。**C7 只做一台**。
**文档结构按用户要求改成两层**：`# 上半部分 · 给人读`（§1.1 要证明什么 / §1.2 接线图 / 8 条回答落点 / 下一步 / GPL）
+ `# 下半部分 · 给 AI 读`（§1.3 起：清单、Q1–Q18、背景、BOM、实施、§六 待回答）。**以后维护就守这个分层**。

## Q18 移植清单（已读 `jetkvm/kvm` 源码，照它实现 = 用户 C2/C6 明确授权）

- **HID 布局**：一个 composite 上挂 **4 个 `functions/hid.usbN` + 1 个 `acm.usb0`**：
  `hid.usb0` 键盘 protocol **1**/subclass **1**/report_length **8**；
  `hid.usb1` **绝对坐标**鼠标 protocol **2**/subclass 0/长 **6**/`no_out_endpoint=1`（descriptor 用 **Report ID 1 = Pointer+Absolute**）；
  `hid.usb2` 相对鼠标；`hid.usb3` **唤醒设备**（vendor page 0xff00，长 1，`wakeup_on_write=1`）；
  `acm.usb0` = `/dev/ttyGS0` 串口控制台（**正是我们 P1.5 要的那个 COM 口**）。文件：`internal/usbgadget/hid_keyboard.go` 等三个。
- 🔴 **移植必改**：`udc.go` 的 `getUdcs()` 读 **`/sys/devices/platform/usbdrd`**（RV1106 命名）→ **RK3566 是 `fcc00000.usb`**，直接抄会找不到 UDC。
  可沿用的：`/sys/bus/platform/drivers/dwc3/{unbind,bind}`、`/sys/class/udc/<udc>/soft_connect`、
  `hidWriteTimeout=100ms`（注释说 10ms 会在连发时丢报文）、
  **RV1106 DWC3 有个 unbind→bind race 会让 `/dev/hidg0` 永久 ENXIO**（防御=探测+100ms 后重绑一次；RK3566 未证但照抄无害）。
- **前端**：`ui/` 是 **React 19 + Vite + TS**（`kvm-ui`），文件式路由；通信 = **JSON-RPC（`jsonrpc.go`，`writeJSONRPCEvent` 推事件）+ WebRTC datachannel**。
  🔴 **P4 第一个决定**：要不要**连它的 JSON-RPC 方法名/事件格式一起实现** —— 一起实现前端几乎不改；自定接口反而更贵。
- **不抄**：`pkg/nmlite`（它自己写的 NM 客户端 + DHCP，因为原版纯有线 eth0）→ 我们用 Ubuntu 自带 NetworkManager/systemd-networkd。
- **GPL**：用户已选"照它实现" ⇒ **自用不分发没有公开义务；一旦公开/分发，衍生部分必须按 GPL-2.0 开源**（JetKVM GPL-2.0，PiKVM GPL-3.0 别混）。

## 硬件层已证/已答（非显然，靠翻文档翻不出来）

- **K11C 没有 HDMI 输入**：`hdmi@fe0a0000` 是 TX，板级 DTS 无 `hdmirx` 节点。
  🔴 坑：`CONFIG_VIDEO_ROCKCHIP_HDMIRX=y` 只是驱动编进去了（给 RK3588/3576 用的），**别被它骗**。
  所以"把 HDMI out 绕回板子当输入"是死路。
- **Q1 已答**：1× Type-C（DXF 网络名直接叫 `TYPE-C_OTG`）→ `usbdrd @fcc00000`（DRD，能做 device）；
  1× USB3.0 A → `usbhost30 @fd000000`（host-only + `combphy1_usq PHY_TYPE_USB3`，真 SuperSpeed）；
  1× USB2.0 A → `usb_host0/1 ehci/ohci`。→ **HID 走 Type-C、采集棒走 USB3.0 A，两条不抢口**；
  原来担心的"SuperSpeed 和 device 角色抢同一个座"最坏情况**已被证伪**。
  证据来源方法值得复用：**原理图 PDF 是 CID 字体抽不出文字，但 DXF 的 TEXT 实体能抽**（`K11C_V1.2_20260811.dxf` 抽出 15852 条）。
- **Q2 已答（用户提的方案）**：**把 `dr_mode` 写死成 `"peripheral"`**，不让它协商角色 → PC 做 host，板子在被控机眼里就是键鼠。
  之所以原本不确定：本板 dtsi 里 usb/typec/dwc3 **覆盖 0 命中**，吃的是 SoC 默认 `otg`，
  而 Type-C 座**没有 CC 控制器** → 插上去进哪个角色没人保证。
  代价可接受：Type-C 从此不能当 host，而我们不需要。**先用 `ls /sys/class/udc/` 判（0 成本）：非空则 dts 一行都不用改。**
  （"烧录不受影响"这条是推理未证：MASKROM/LOADER 由 ROM/U-Boot 自己设 device，不读 Linux 的 dts。）
- **Q3 是唯一真阻塞**：内核 `# CONFIG_USB_G_HID is not set`、`# CONFIG_USB_FUNCTIONFS is not set`
  （底座齐：`USB_GADGET=y`/`USB_LIBCOMPOSITE`/`USB_CONFIGFS` 含 ACM·MASS_STORAGE·F_FS/`USB_F_UVC=y`）。
  一轮内核重编约 9 分钟，纯 VM 就能做。⚠️ **强制 device ≠ 就有键盘**：角色对了但没有 HID 功能，Windows 只认到"未知 USB 设备"。
- **鼠标必须用绝对坐标**（report descriptor 含 `Usage (Pointer)` + `Absolute`），只做相对坐标远程会漂到没法用（Q10）。
  💬 **讲解要点（2026-10-16 用户手绘图暴露的认知差）**：他默认"**PC 的 HDMI 线插进板子 HDMI 口就能收画面**"，
  而板子那个口是**输出**——所以**每次讲架构要先讲这一条**，再讲"采集棒 = 把 HDMI 翻译成 USB 摄像头"，
  否则"为什么要买这玩意/为什么要接 GPIO"会反复卡住。他真正想的产品形态是
  **手机连同一 WiFi，手机当鼠标键盘** —— 这个理解完全正确，讲的时候顺着它讲最省力。
  另外：**GPIO/继电器只是"从关机状态远程开机"，他不需要就可以整块砍掉**（已把 P7 标成可选）。
- **采集棒选型**：MacroSilicon **MS2109/MS2130** UVC；🔴 方向别买反 —— 要 **HDMI→USB 的采集棒**，
  不是 **USB→HDMI 的转接头**（DisplayLink 那类是输出）。USB2 天花板：1080p30 只能 MJPEG，YUY2 只到 720p。
  预期管理：**JetKVM 标的 30–60ms 是 MIPI+硬编路线，USB 棒达不到。**
- **供电（Q9）**：device 按规范该从 PC 取 5V，但被控机 BIOS 阶段可能限流/不给，而 KVM 要常在线
  → **板子保持原装电源独立供电，Type-C 线只走数据**。

## 延迟基线与"能不能拿来打游戏"（2026-10-17 补，用户连着两轮问 120Hz 打游戏）

**🔑 下次他再问延迟，先分清两种形态，别直接报数字**：
- **A 形态 = 眼睛看本地屏、手机/板子只发键鼠** → 单向 WiFi 约 5–15ms（未证），可忽略，120Hz 照打。
  这是用户最初说的产品形态。**买 JetKVM 对这条毫无帮助**，KVM 解决的是"画面也要走网络"。
- **B 形态 = 画面也过网络、浏览器里看** → 才是延迟问题。

🔴 **最硬的一条（之前没讲过，比 WiFi 加多少毫秒重要）**：**EDID 会把 120Hz 先吃掉**。
KVM 采集端刷新率上限就是被控机 GPU 按 EDID 出图的上限 → 插上 KVM 后游戏**自己退回 60/30fps**，
present 等待从 8.3ms 变 16.7ms。**这跟网络、跟设备贵贱、跟 DIY 还是买都无关**，是采集层物理上限。
（原版 JetKVM = 1080p60，Mini = 1080p30/720p60 → Mini 连"看到 120Hz"都不可能。）

**已证基线（第三方 vs 厂商口径差一倍，报数时必须分开）**：
| 数字 | 出处 | 条件 | 定性 |
|---|---|---|---|
| 30–60ms @1080p60 | `jetkvm/kvm` README | **有线** | 营销口径 |
| **80–100ms 稳定** | Jeff Geerling 2024-10-26 拍屏实测 | **有线 LAN** | ✅ 已证（第三方） |
| 60ms@1080p60 / 80ms@2K60 / 100ms@4K30 | Sipeed NanoKVM Go 官方 wiki | WiFi6 | 厂商口径 |
| Mini W 95–150ms 典型、尾部 200ms+ | 我 10-17 的分段估算 | WiFi + 1080p30 | ⚠️ **未证，纯估计** |

⇒ **结论：$69 原版走网线也只测到 80–100ms。** 买现成的不会把 150ms 变成 30ms，它省的是"自己写固件"，不是"能打游戏"。
**买 Mini W 现在也买不到**：10-26 才发售当天才开源（10-16 已核实 org 里 Mini 固件仓库不存在）→ 想买就等第三方实测。
**GL.iNet Comet Pro / RM10** 宣传"远程打 PS5"，它是 **4K@30**，当营销看。

**WiFi 上真正咬人的不是带宽**（1080p30 低延迟 H.264 只要 6–12Mbps）：
① **省电模式** → 唤醒等 TIM，尾延迟能顶到 100–200ms → 板上必做 `iw dev wlan0 set power_save off`；
② **半双工重传** → 尖峰比平均值更毁手感（甩枪时"画面没跟上"那一下）。
中位只比有线多 5–20ms。⚠️ 这两条全部**未证**，属 Q8.5 待实测。

**决策落点**：远程打游戏请改用 **Sunshine/Moonlight**（被控机 NVENC 硬编，有线 20–40ms）——
但它要求被控机装软件、能进系统，**正好就是档2那条论证里"KVM 的价值失效的反面"**，两者并存不互替。
体感门槛：<30ms 无感｜30–60ms 竞技 FPS 可察觉｜60–100ms casual 可玩但发肉｜>100ms 瞄准类直接废。
**上面所有 ms 都不是这块板测的**，P3-B 之前"一个延迟指标都不许报"的纪律照旧有效。

## Q8 网络：**已定走 WiFi**（2026-10-16 用户拍板，覆盖我先写的"先用网线"）

**最终决定**：主网络 = **板载 WiFi**（Seekwave SWT6621S），**网线降级为调试备胎**。
理由：WiFi 同样满足"带外"（网络路径不经过被控机）；板子要贴着被控机放、路由器口不一定够；JetKVM Mini W 证明纯无线 KVM 是能做产品。
**代价 = 一条新硬约束**：WiFi 配错就把自己锁死门外（板子没屏没键盘）→
**必须先有不依赖网络的通道**，所以 **P1.5（Type-C 的 CDC-ACM gadget，Windows 上多一个 COM 口）从"顺手"升级为"前置必须"**，
且 `apt install ffmpeg/iw/fonts-dejavu-core` 只能在 P2.5 配上 WiFi 之后做（鸡生蛋，见 N6）。
🔴 **蓝牙仍然彻底排除**（BT PAN 1–2Mbps、Windows 侧基本废、BIOS 阶段没蓝牙栈；BLE 配网是裸机 MCU 没串口才需要的复杂度）。
**WiFi 要还的 5 笔债（Q8.1–Q8.5，全部未证，命令在 `14_` §2-Q8）**：电台频段能力 / `iw`·`wpa`·apt 出公网 / 首配通道 / 固定地址（按 MAC 绑租约或 mDNS）/ 实测吞吐（**格式定 H.264 优先**，MJPEG 只当降级壳；2.4G only 就降到 720p60/1080p30）。

### 调研依据：读 `jetkvm/kvm` 源码 + Mini 公告原文（2026-10-16）

**原版 JetKVM 是纯有线**（注意：**这是它的产品定义，不是我们的结论**）：
- `network.go` 写死 `const NetIfName = "eth0"`；网络栈自己实现（`pkg/nmlite` = NetworkManager D-Bus 瘦客户端 + `pkg/nmlite/jetdhcpc` 自带 DHCP 客户端）；
- `jsonrpc.go` 的 `rpcGetDeviceCapabilities()` 返回的能力表**没有 `wifi`** → UI 里 `{hasWifi && <WifiNetworksCard/>}` 在原版上不渲染；
- 全仓库 633 文件 `git grep -i "bluetooth\|\bble\b"` **0 命中** → JetKVM 配网**不靠蓝牙**；出门靠 **Tailscale + mDNS**。
- ✅ 已证实（读 2026-10-16 Mini 公告原文）：同一份 web UI 服务两个型号，靠 `capabilities` 门控。
  **JetKVM Mini 基础款 $39 带 RJ45；只有 Mini W $42 用 ESP32-C5 走 WiFi（2.4+5GHz），蓝牙只做首配**
  （原话 "Setup happens over Bluetooth … pick a network, enter the password"）。
  产品线**基础款仍是有线**（它的机柜场景），**我们因为部署场景不同反过来选 WiFi** —— 别把这条当"WiFi 不可行"的证据。
  ⏳ **Mini 固件仓库现在还不存在**：公告承诺 2026-10-26 上市当天开源（"open source from day one"），
  org 现有 9 个仓库里没有，`jetkvm/docs` 里 grep "jetkvm mini" 0 命中，猜的 `mini-firmware`/`esp32-p4-firmware`/`jetkvm-mini` 全 404。
  → **想参考 Mini 的 WiFi/BLE 配网实现要等 10-26。**
- 📌 **Mini 的规格 = 我们的天花板参照**：ESP32-P4X 裸机（片内 H.264 硬编，无 Linux/无 eMMC），**1080p30 或 720p60**；
  对被控机是 **USB2 HS 480Mbps 复合设备（键+鼠+虚拟光驱，ISO 走侧面 TF 卡）**；另一口 USB2 FS 接 ATX/DC/串口扩展。
  ⚠️ **它从被控机取电，我们不能照抄**（板子功耗大得多，见 Q9）。
  ⇒ 所以 P5 用 USB 采集棒做到 **1080p30 MJPEG 就该算达标**，别拿 1080p60 当基线。
- 📖 **另一个比 JetKVM 更能直接参考的开源实现**：[`espkvm/espkvm`](https://github.com/espkvm/espkvm)（已核实存在）——
  **ESP32-P4 + 东芝 TC358743 HDMI→MIPI 采集桥**，单芯片同时当 USB device(HID) 和采集管线；
  目录含 `kvm_hid/`(复合 HID)、`kvm_atx/`(电源与复位键)、`kvm_cec/`、`kvm_board/`(引脚表)。
  → 若 P5 后真要走 Q4 的桥路线，先看它，别等 JetKVM。
- ✅ **抄到一条好东西（现在是必须项）**：JetKVM 有 CDC-ACM gadget（`cdc_acm_console.go` 读写 `/dev/ttyGS0`）。
  我们内核 `CONFIG_USB_CONFIGFS_ACM=y` **已内建** → **不用重编内核**就能 configfs 建 ACM，
  Type-C 插 Windows 多一个 COM 口：① 当场实锤 device 角色（Q1/Q2）② 白得一条不占 COM14 的控制台 ③ 网挂了还能自救。
  这就是新增的 **P1.5**（零重编、零成本的角色探针）。

## 排期（**2026-10-16 第二次修正版**；下面第一行是当前有效的）

**当前（目标收缩后）**：`P1 开 HID gadget（照 §2-Q18 四个 hid.usbN + acm.usb0，一律 =y）`
→ `P1.5 ACM 探针（结 Q1/Q2 + WiFi 救命通道）` → `P2 插这台笔记本打字（唯一不能假的一条）`
→ `P2.5 配 WiFi 拿 IP + SSH（从 P1.5 的 COM 口进去，重启后仍通才算过）`
→ `P3-A 假源自环冒烟 + 顺手查 /dev/mpp_service 与 Q6` → `P3-B 假源上浏览器 + 拍屏量延迟 + iperf3 记吞吐`
→ `P4 移植 JetKVM 前端（先定要不要连它的 JSON-RPC 一起实现）` → `P6 无人值守` → `P7 收尾（供电+外壳，继电器不做）`。
⏸ **P5（agent 推屏）挂起**；⚪ **P5b 采集棒排除**；⚪ Q13/Q14/Q15 随 P5 挂起，Q16/Q17 关闭。

**历史（别照这个做）**：`P1 → P1.5 → P2 → P2.5 配 WiFi → P3-A/B → P4 → P5 推屏 → P6 → P7`
—— 网络原本排 P6，但假源 P3-B 就要"浏览器连板子"→ **提到 P2.5**；又因选了 WiFi 而非网线，**P1.5 变成 P2.5 的前置**。
（这类"新方案/新决定暴露的排期矛盾"用户明确要我自己找出来。）

**Why:** 这条线的硬件前提全部要靠板上/DXF 实测，官方资料只讲烧录不讲 USB 拓扑；
而且"先花 0 成本证软件栈"是用户提出的，直接改变了排期和花钱顺序。

**How to apply:** 2026-10-16 状态是**方案已验、一行代码一行内核都还没动**（见 [[feedback-plan-validation-mode]]）。
下次接着做从 P1 开始，且必须先拿到用户"干"的指令。涉及 K11C/USB/HID 的问题先读 `14_...md`，别重新论证路线。

**【2026-10-17 更新 —— 上面那句已过期】** 用户已下"干"的指令，P1/P1.5/P2 都做完并**上板实测通过**，
详细记录在 `14_...md` 的 **§5.4**（四个坑 + 结果表）和 **§2-Q18**（移植清单）。
当前堵点：**等用户烧 `K11C_v12_ubuntu2404_selfbuild-P2hid-noadb-20261017.img`**
（md5 `467b9973a4804a5944955ff8128f9daa`，7,172,541,002 B，在 `D:\02_baidu\自建镜像\`）——
这版已把 gadget 脚本 + 开机自启烘进 rootfs，并 **mask 掉官方 `usb-gadget.service`**，
所以**开机插上 Type-C 就是键鼠，不用跑任何脚本**。烧完的下一步是 P2.5 配 WiFi（COM15 就是控制台）。

## 上板实测的四条硬教训（2026-10-17，别再踩）

1. 🔴 **别沿用官方 `VID_2207&PID_0006`**：Windows 装过的 Android 驱动会按硬件 ID 把复合设备**父节点整台认领**，
   连 `MI_xx` 子设备都不生成 → HID 接口"人间蒸发"，看起来像我们描述符写坏了。
   排查特征：`Get-PnpDevice -PresentOnly` 里只有 `AndroidUsbDeviceClass`、没有任何 `MI_` 子节点。
   解法：自己的 VID/PID（实测 `1d6b:0104` 可用）+ `bDeviceClass=EF/02/01`。
2. 🔴 **configfs 换 function 必须先解绑 UDC**：绑着的时候 `ln -s functions/x configs/b.1/x` 返 EBUSY。
   而且**千万别给 `ln -s` 加 `|| true`** —— 我就是把错误吞了，才出现"function 都建好了、config 里只有 adb"这种诡异现象。
3. **SDK 的 6.1 内核 hid function 没有 `wakeup_on_write`**（JetKVM 5.10 的厂改属性），写它 `Permission denied`；远程唤醒另说。
4. **换 gadget 会杀 adb，adbd 一死会带走它派生的脚本**（`setsid nohup` 也没扛住）⇒ 用 **`systemd-run --collect`** 丢给 PID1。

🟡 **中文输入法会把我们发的字母吃进候选框**（不进文档），表现极像"键盘不通"，但 CapsLock 照样生效（IME 不拦它）。
板子发 `Ctrl+Space` 切英文后立刻正常 ⇒ **P4 前端必须处理输入法**（JetKVM 用 `setKeyboardLayout` + 文本粘贴通道）。

✅ 已量到的效果：绝对鼠标把光标从 `1281,162` 移到 **`959,539`**（1920×1080 正中）；
键盘打字经 `Ctrl+A`/`Ctrl+C` 从剪贴板读回 `HELLO NZS` 逐字符正确；Windows 出现 **COM15**（ACM 控制台，比 1500000 的 COM14 好用）。

## 【2026-10-17 22:00 追加】复验烘进镜像的 P2hid-noadb 版：**自启成了，Windows 端这次没测到**

烧的是 `K11C_v12_ubuntu2404_selfbuild-P2hid-noadb-20261017.img`（md5 `467b9973a4804a5944955ff8128f9daa`）。
**✅ "不跑脚本"这条成了**：`k11c-gadget.service` = enabled+active、`usb-gadget` = masked、configfs 里
`k11c` 的 `configs/b.1` = `acm.usb0 hid.usb0 hid.usb1`、`UDC=fcc00000.usb`、`/dev/hidg0 hidg1 ttyGS0` 都在、
`1d6b:0104` + `bDeviceClass=0xef`、内核 `6.1.141 #3 SMP Oct 16 13:32:40`。**详细数字在 `14_...md` §5.4 的追加小节**。

🔴 **新查出来的缺陷（已改 repo，板上只是内存里临时补，重启回退）**：烘进去的 `k11c-gadget.sh` 写出的
`strings/0x409/serialnumber` 是**空串**。两个原因叠在一起：① 这颗 RK3566 的 dwc3 **没有**
`/sys/class/udc/*/mac_address`；② 那行 `cat … | tr -d … >file || echo 兜底 >file` —— **管道返回的是 `tr` 的 0，
`||` 永远不触发**。17:49 那次通过的基线用的是 `k11c_min.sh` 写死的 `00000001`，这是两者唯一的实质差异。
⇒ 教训（可推广到别的 configfs 脚本）：**别在管道后面接 `||` 当兜底**；iSerialNumber 为空是隐患。

🟡 **`/sys/class/udc/*/state` 是粘的** —— `echo '' > UDC` 解绑后仍读 `addressed`，不回 `not attached`。
⇒ **`state≠configured` 不能反推"主机在试枚举"**；本轮那个 `addressed` 是 21:52 烧写会话的残值。
判"对面有没有真主机"要看 `dmesg` 里**连续多轮** `device reset`（约 0.67s 三次 = 主机重试节奏）、
`/sys/class/extcon/extcon0/state`，和被控机侧 PnP 有没有变。

⬜ **Windows 端这次没测到，原因在物理层**：present 里 0 个 `1D6B`；我在板上做了 3 次可控拔插
（板侧 dmesg 有 DISCONNECTED/CONNECTED/reset），被控机 250ms 轮询两轮（55s/70s）present **204 个设备 0 变化**；
注册表 `USB\VID_1D6B&PID_0104\00000001`(usbccgp) arrival 17:49:30 / **removal 21:47:18**。
⇒ 就是 §六 **A1**（"把 Type-C 数据线插到被控机上"）没做，或插的是无数据的口。

⚪ **两个嫌疑已排除，别再查**：① **VMware 没抢设备** —— 唯一在跑的 `rk_ubuntu.vmx` 里 `lsusb` 没有 `1d6b:0104`，
`vmware.log` 端口 `1/0/0/10` 最后事件是 21:56:29 的烧写态 `2207:350a Rockusb/USB-MSC`；本机那个 present 的
`VMware USB Device`(`5&299D89E&0&10`, `QUSB_BULK_CID:0437_SN:E2EB513B`) 是烧写残桩；而且 17:49 成功枚举时
arbitration 也在跑。② **被控机不是虚拟机** —— `LENOVO 82AV`、`HypervisorPresent=False`，
`HID\VMULTIA` 那批是主机上 VMware 自己装的桩。

🛠 **本机现成工具**（都在 repo，别再重写）：`26_k11c_kvm/host/serial_probe.ps1`（COM14 @1500000，
"发一条、等哨兵再发下一条"，每条命令前先 `^C` 清续行；哨兵靠 `printf '\nKZ%sZK\n' "$q"` 让**回显文本 ≠ 输出文本**）、
`watch_new_device.ps1`（present 设备集增量）、`quick_check.ps1`。
⚠️ 这台机器上 **bash 里别内嵌 `$_`/`$()`**（会被吃掉），也**别往 project 目录外写临时文件**（权限会拦），
脚本一律放 `26_k11c_kvm/host/`。串口用完要关端口，别占着 COM14。

## 【2026-10-18 通宵场】T1–T4 / T6 / T7 全部闭环，只剩 T5（等电视）+ T8/T9

用户 10-18 的指令是"按高级 ai 的指令继续干活"—— 方案文档已被另一个会话**整份重写**成 §9 任务清单
（T0 现状核对 → T1 COM15 自动登录 → T2 WiFi+SSH → T3 部署通道 → T4 假源+MJPEG → T5 电视 →
T6 RPC → T7 手机网页 → T8 开机自启 → T9 量延迟），**执行规则：一次只做一个、验收全过才打勾、
实测行只贴量出来的数字、本轮不重编内核不烧固件**。新目标三件：手机过 WiFi 控电脑 / 手机看到彩条+码表 /
板子 HDMI OUT 同画面接电视。

**已过的**：T1（`serial-getty@ttyGS0` autologin）· T2（连 `Duck_5G`，SSH enable）· T3（免密 `ssh k11c` + `/opt/k11c-kvm`）·
T4（假源 fps 30.0、1280×720、码表在走）· T6（鼠标 16384→**960,540** 精确、`typeText` 经剪贴板逐字相等、
滚轮 5 格=15 行、300 次串行 **3.086s** 0 错误）· T7（手机 `192.168.31.18` 实际打了 **1742 次 absMouseReport，0 错误**，
用户自测滑动/右键菜单/打字都成）。

### 🔴 10-17 那条"空 iSerialNumber 只在内存里补了"的警告，10-18 原样爆雷

板子一重启就变**"无法识别的 USB 设备"**，UDC 卡 `addressed`，`/dev/hidg*` 写全 EAGAIN。
**换 USB 口 + 重启电脑 + 重启板子全都无效** —— 因为镜像里 `/usr/local/sbin/k11c-gadget.sh` 就是带 bug 的旧版
（md5 `cc42db76`，`cat|tr > serialnumber || 兜底` 写进空串）。把 repo 的 `31743bd6` 拷上去重启服务，
**立刻 `configured`、`serial=eaf4b2430e0d`**。
⇒ **硬结论：`P2hid-noadb` 镜像是坏的（重启即坏），下一次出固件必须带新版脚本**；
在没重烧之前，**不要在这块板上做"重启看自启"的测试**（会退回坏脚本，白排查一小时）。

### ⚡ 新的硬件层事实（和上面 Q9 那条规划要分开看）

- **这块板现在就是靠那根 Type-C 供电的** —— 用户拔插数据线直接把板子断电重启了（我一度以为是自己的命令生效）。
  所以"拔线=拔电源"，排查时看到的"莫名重启"先想这条。Q9 里"原装电源独立供电、Type-C 只走数据"是**规划**，不是现状。
- ACM 在 Windows 上从 **COM15 变成 COM16**（枚举次数变了）⇒ 别写死 COM 号。
- 板子 WiFi：`Duck_5G`（口令记在 `03_ai的记忆_和skill/04_workbuddy_记忆与skill/日志/2026-10-18.md`），
  IP **192.168.31.89**，重启后 DHCP 会先给 `.90` 再把 `.89` 续回来 → **网卡同时挂两个地址**；
  路由器 `.1`、笔记本 `.98`、手机 `.18`。
  **用户 10-18 拍板：不在路由器绑 MAC、不写静态 IP** → AI 侧一律 `ssh k11c`（= `kickpi.local`），手机侧用当时查到的 IP。

### 📏 量延迟的唯一正确口径（10-18 花了一小时才分清）

板子 loopback 一次 RPC **3ms**、板子→路由/→笔记本 ping **3.2–3.4ms**，但同一台笔记本发 HTTP 要 **55–62ms**：
① `Invoke-RestMethod` / `HttpClient` 自身开销占大头；② 用 `kickpi.local` 更惨 —— **298ms/次**（.NET 先试 IPv6 link-local 再回退）；
③ 笔记本无线网卡 **Power Saving Mode = 开启**，ICMP 抖 **1–103ms**。
⇒ **测延迟一律 raw socket + 直连 IP**；T9 报数前必须先关笔记本网卡省电，否则量到的全是它。
（`TCP_NODELAY` 已加在服务端；单次真往返 12–19ms。）

### 板子环境的三条硬约束（不在代码里，会反复咬人）

1. `/dev/hidg0`/`hidg1` 是 `crw------- root root` ⇒ **KVM 服务必须以 root 跑**（T8 的 unit 就是这么定的）。
2. 这块板的 sudo 环境**缺 `CAP_DAC_OVERRIDE`**：`id` 是 uid=0，却追加不了 kickpi 拥有的文件（`>>/tmp/x.log` 直接 EACCES）。
   新建文件可以 ⇒ 日志永远写新路径。
3. 从 ssh 会话里 `setsid nohup` 起的进程会留在 `user-1000.scope`，**会话登出被 logind 整组杀掉**（表现是"服务无声消失"）
   ⇒ 用 `systemd-run --unit=… --collect`（已封在 `board/run.sh`，口令走环境变量不落盘）。
4. **HID 的 IN 队列只有 1 深**：按下+松开连着发，第二枪必 EAGAIN ⇒ 写 HID 要**有界重试**（服务端 20×5ms），
   既不能直接报错也不能无限阻塞。
5. 板上跑 `pkill -f 'x[.]py'` 时**别在同一条命令里再出现明文 `x.py`**，否则把自己的 ssh 会话杀了。

### 前端：JetKVM 的 UI **一行都没搬**（用户 10-18 直接问过，答法记下来）

手机页面是我自己写的单文件（`board/www/index.html`，~200 行、零外链）。从 JetKVM 拿的只有三样协议层东西：
HID 报文格式 + report descriptor、JSON-RPC 方法名（为了以后能接它的 `useKeyboard.ts`）、"板子跑本地服务 + 浏览器当界面"这个架构。
没拿：React19/Vite/TS 那 160 个文件、绑死 WebRTC 的视频管线、虚拟 U 盘、改 MAC、ATX、云中转、音频、nmlite 配网、OTA。
**为什么不搬**：它假定后端 118 个方法 + 视频必须 WebRTC + 读 RV1106 路径（`/sys/devices/platform/usbdrd`，我们是 `fcc00000.usb`），
搬 UI = 连信令一起搬。能力缺口：只支持 ASCII/US 布局、无"粘贴到目标机"通道、无画质控制、无宏。
**`切输入法` 按钮要保留**（用户质疑过"输入法不是本来就有吗"）：KVM 的场景就是人不在电脑前，
电脑卡在中文输入法时没法伸手点右下角，而候选框会吞掉手机发的字母 —— 这是唯一能远程掰回英文的入口。

**Why:** 10-18 这一场把"能不能用"从推测变成了实测数字，也证明了 10-17 的修复如果只落在运行态就会回退。

## 【2026-10-18 深夜收尾】T5/T7/T8 也闭环了 ⇒ T0–T8 全过，只剩 T9 + 一个待拍板的性能问题

**新过的**：T5（电视全屏彩条+码表，人确认）· T7（手机五条全对，板子计数 `absMouseReport=2710`/`typeText=1`/`last_err` 全空）·
T8（`k11c-kvm.service` root + `~/.config/autostart/k11c-tv.desktop`；**冷启动 HID 25 s、HTTP 28 s**，`fps` 稳态 29.7）。

🔴 **T8 挖出来的新坑：镜像自带 onboard 虚拟键盘开机自启，会盖住码表**（第一次截图就看见一把键盘压在画面下面）。
要**两份** `Hidden=true` 才盖得住，因为条目名字不同：`~/.config/autostart/onboard.desktop`（镜像自己加的 tray 条目，
跑 `/usr/local/bin/onboard-tray.sh`）+ `~/.config/autostart/onboard-autostart.desktop`（覆盖 `/etc/xdg/autostart/` 那份）。
顺带又自伤一次：`pkill -f "/usr/bin/onboard"` 会匹配到自己的 ssh 命令行把会话杀掉 ⇒ 用 `pkill -x onboard`。

### 用户报"电视卡、手机反而顺"，量完的账（**这条是下一次的性能起点**）
`load average 9.78`（4 核 A55）｜`ffplay` **193.3%**｜`ffmpeg`（软编 MJPEG）**126.7%**｜`python3` ~0%。
**电视没有累积落后**：真实墙钟 7.343 s 内屏上码表走 7.433 s（≈1.01× 实时）⇒ 卡是 **ffplay `-framedrop` 丢帧保时钟**，
平均对、瞬时一顿一顿。手机顺是因为解码在手机上做，板子只付"编码+发流"。
🔴 **顺带把"fps=30"这个口径打掉了**：编码器实际 **270 帧 / 7.343 s = 36.8 fps**，因为 `-re` 的节拍挂在
这颗板子**会随墙钟跳的 `CLOCK_MONOTONIC`** 上（无 RTC + NTP；journal 有 `Time jumped backwards`；
`/proc/uptime` 43.6 h、服务 monotonic 差值 33.7 h、码表 `33:39:19` 三者互不对）。
⇒ **T9 之前必须先定这个口径**，任何"从启动算多少秒/多少 fps"都不可信；但码表烧在帧里，两屏读同一个数，
**用两屏码表差值量相对延迟仍然成立**。
**待用户拍板的四选项（已写进文档 §8.3）**：① 电视那路改 GStreamer `mppjpegdec ! kmssink`（硬解+绕开 X）
② `fakesrc.sh` 换 `mppjpegenc` 硬编 ③ 降规格 720p15/960×540 ④ 不动。AI 建议 ①+②（板子自带 MPP，不装东西）。

⚠️ **T9 还不能报数**：手机+电视同框照片里手机那串码表被手机自己的 UI 遮了一半，肉眼读数不可信
（初读差 47 s，但电视既然实时就不可能差 47 s ⇒ 是读错不是真有 47 s）。重测：**手机双指放大到只剩码表再拍**。

📌 **下一步除了 T9 还有一件必须做的**：现在**板子上的东西比镜像新**（修好的 `k11c-gadget.sh`、整个 `/opt/k11c-kvm/`、
`k11c-kvm.service`、autostart 覆盖、T1 的 getty drop-in）——**重烧就全丢**。要重新出一个镜像把它们烘进去。

**How to apply:** 先看 `12_win_上机跑/14_K11C做JetKVM式IP-KVM_方案.md`（§8.1 攒到 23 条坑、§8.3 有待拍板项、
§9 每个任务下面有实测行），别凭这条记忆下结论。WiFi 口令 `Duck_5G` 记在 `03_ai的记忆_和skill/04_workbuddy_记忆与skill/日志/2026-10-18.md`。

## 【10-19 深夜】第二轮 T10–T17 开工：codec 定 H.265，T11/T12 已落地

用户拍板："**确定要用 265**，你看能做啥就开始做啥" ⇒ 上一轮"要不要开 T10"的悬案作废，第二轮直接开工。

**已过的**：T11 素材（`bars_nv12.yuv=3110400` / `glyphs.gray=41600`，字形基线正、没切边）·
T12 `fakevo` 机器侧三条（**60 帧 / `miss=0` / `noslot=0` / `dt_avg=16.67ms` / CPU 4.3%**，
第一行 `conn=121 crtc=90 primary=58 nv12plane=98` 与文档固定参数表逐字一致）。
待确认两条：T12 第 4 条（人看电视）、T10（手机 `probe.html` 的 `webrtc H265` 是不是 true）。

🔑 **这一轮最该记住的一个数**：同一块板子、同样 1080p60 上电视，
**软路径（ffplay 软解）≈320% CPU + 13 秒缓冲 + 肉眼卡**；
**原始帧 DRM 直出 = 4.3% 单核 + 抖动 0.2 ms + 一帧不差**。
⇒ "电视那一路不该再解一次码"不是洁癖，是数量级差别。

⚠️ **板上现在是"停 lightdm"状态**：电视上没桌面/没 ffplay，画面由 `systemd-run --unit=k11c-fakevo` 常驻直出。
恢复桌面 `sudo systemctl start lightdm`（重启也会自动回来）。别把这个当成故障。

🛠 **写 DRM 直出程序的四个真错**（都从"零警告"里抓出来的，下次直接避开）：
`drmEventContext` 是 typedef 不能用 `struct` 写；`page_flip_handler2` 是**六个参数**
`(fd, seq, tv_sec, tv_usec, plane_id, user)`；`drmModeAddFB2` 的 handles/pitches/offsets **固定按 4 元素数组读**；
`snprintf` 缓冲区不留够会 `-Wformat-truncation`。另外这版 `systemd-run` **不认 `--directory`**，要用 `-p WorkingDirectory=`。

**How to apply:** 接着做从 T13（同一块缓冲送 `mpph265enc`）开始，前提是先拿到 T10 的手机截图和 T12 的人眼确认。
细节以 `14_...md` §9.2 为准。

## 【10-20】T14/T15 电脑侧闭环：WebRTC 走 **Go + pion 静态二进制**，MJPEG 软路径已退场

用户拍板 **D：照着 JetKVM 移植**（"选d 我们就是要照着移植的"）⇒ A 自编 libnice 插件、B fMP4+MSE、C 维持 MJPEG 全都没选。
`webrtc_gw.py` 停用（保留作参考），新实现 `26_k11c_kvm/board/gw/{main.go,util.go}`，
在 rk-vm 交叉编译成**静态 ARM64 单文件**（9.8 MB，板上零依赖，`/opt/k11c-kvm/k11c-gw`），
信令接口与 Python 版一致所以 `webrtc.html` 没改。**下次要 WebRTC 就直接改这个 Go，不要再碰 `webrtcbin`**。

**量到的数（电脑 Chrome 当远端，1080p60）**：`inbound-rtp` `framesDecoded` 在涨、`framesPerSecond=60`、
**`framesDropped=0`、`packetsLost=0`**，抖动缓冲 **8.4 ms**、**解码 0.46 ms/帧**；
网关**进出包数完全相等**（134.6 pps，950 kbps，`rtp_err=0`）。
- **判断硬解没有现成字段**：这版 Chrome 的 H.265 `decoderImplementation` 是 `undefined` ⇒ 用 `totalDecodeTime/framesDecoded` 当证据
  （0.46 ms/帧只有硬解做得到，软解 1080p HEVC 远大于此）。
- **CPU 账（`/proc/<pid>/stat` 差值、6 s 窗口、4 核满值 400%）**：`fakevo` **30.4%** + `k11c-gw` **7.3%** + `kvm_server` <0.5%
  ≈ **38%**，对比软路径 **≈370%**、load **1.89** vs **9.5**；`--no-mjpeg` 下 `pgrep ffmpeg` 已空。
- ⚠️ **别用 Qoder 内嵌浏览器验渲染流畅度**：它 `visibilityState=hidden`，Chrome 把不可见页的合成器渲染节流掉，
  `getVideoPlaybackQuality()` 会报 `droppedVideoFrames ≈ totalVideoFrames`（本次 3009/3010），**看着像疯狂丢帧其实是量的地方不对**。
  渲染体感只能靠真人（手机或可见窗口）。

**两个 pion 专属坑（已写进 `14_` 坑 31/32，这里只留一句）**：非 trickle 必须回 `pc.LocalDescription().SDP`
（`CreateOffer` 那份**一行 candidate 都没有**，症状是协商成功、`ontrack` 收到、30 s 后 `failed`）；
"只服务一个观看端"的 `swap()` 关旧连接时，**旧连接的 `closed` 回调会抹掉刚装上的新连接**，回调要按连接身份判。

**手机页现状**：`index.html` 默认建 `<video>` 走 WebRTC，`?mjpeg=1` 才回退旧 `<img>`；坐标换算取证 = 画面 25%×25% →
`Cursor::Position` 精确落在 **(480, 270)**（屏 1920×1080）。打字第一次打出**中文乱码**，
`Ctrl+Space` 按一下离开中文后 `ab1cd1ef` 逐字命中 —— **`切输入法` 是开关不是"切到英文"，可能要按两次**（坑 30，10-17 那条的加强版）。

**板上现在全是"跑出来的"，比重烧前更多**：`k11c-fakevo` / `k11c-gw` / `k11c-probe` / `k11c-kvm-run --no-mjpeg`
都是 `systemd-run --collect` 瞬态单元，lightdm 仍停着 ⇒ **重烧=全丢**，出固件要带：修好的 `k11c-gadget.sh`、
`/opt/k11c-kvm/` 全部（含 `k11c-gw` 二进制和 `vo/` 素材）、三个正式 unit、`--no-mjpeg`、autostart 覆盖、getty drop-in。

**待人的**：T14 验收 3/4（手机看画面+读统计行）· T15 验收 1（手机眼验与电视同源）· T16（同框 3 张照片）。
T17（关桌面做产品形态）**必须等用户点头**，回滚命令在文档里。

### WiFi 省电这条 10-17 立的债，10-20 实测推翻了（**别再照着老结论去做 hack**）

用户点名"WiFi 那个得修 因为延迟越低越好" ⇒ 装了 `iw` 真去测，结论是**省电不是这条链路的杠杆**：
`iw` 确认 `power_save: on`（NM 默认 `wifi.powersave = 3`）；**ON/OFF 交替 5 轮、60+60 样本**量"空闲 400 ms 后发一条完整 TCP 往返"，
**中位 14 / p90 111 两边完全一样**，只有最大值 194→114。真正决定尾巴的是**链路忙不忙**：
同一个省电开的设置，视频流一跑起来 max 123→26（真实使用中 p90 = 16 ms）。⇒ 产品里手机一直在收流，这条咬不到。
- ⚠️ 测法教训：**单时段"先测后测"会测出"关掉省电更差"这种假效果**（环境漂移）。归因必须交替 A/B。
- ⚠️ NM 持久化在这个驱动上没走通：`conf.d` 里 `[device-wifi]` 和官方的 `[connection] wifi.powersave = 2` 两种写法，
  重连后 `iw` 都还报 `on`（手动 `iw ... set power_save off` 立刻生效）。**要持久化得上 NM dispatcher，不值**。
- 这台笔记本挂着 **FlClash / Meta Tunnel（TUN 代理，fake-IP `198.18.0.x`）** —— `git push` 断在 `198.18.0.21:443` 就是它。
  量局域网延迟前先 `Find-NetRoute <板子IP>` 确认走的是 WLAN 直连，否则数字全是代理的。
- ⚠️ **板上比镜像多 1 个包 `iw`（2395→2396）**，下次做一致性审计会看到，别当漂移。

## 【10-26~27】鼠标"不跟手"修完并出固件（mousefix-20261026）

用户报不跟手、怀疑"烧进去还差东西"。**固件不缺**（`dc_in=838` 证明鼠标报文走的就是 datachannel）。真因两条：
`dc_drop=56`（64 深队列溢出 = 丢 6.7%）+ 我把 `hid-unreliable` 设成 `ordered:false`（**乱序到达 = 光标来回跳**）。

**修法（下次遇到"绝对坐标类输入发不出去"直接照这个想）**：
纯移动**不进队列**，走"只保留最新一条"的槽位（`latest` + `doorbell`）—— 绝对坐标只有最新一条有意义，
把 200 ms 前的位置补发只会让光标倒回去，**那才是"不跟手"本身**；带按键的、键盘、文字仍进 FIFO（不然一次点击会被顶掉）。
不可靠通道要 **`ordered:true` + `maxRetransmits:0`**（保序、不重传）。节流 DC 下 16 ms、HTTP 下 30 ms。
计数器必须分开：`dc_coalesced`（主动作废，正常）≠ `dc_drop`（溢出，事故）。

手机实测 20 s：`dc_in=1152`（58/s，几乎打满 16 ms 上限）、`coalesced=426`、**`drop=0`**，用户"**手感可以了**"。
新瓶颈已量化但没修：转发实际 ~39 次/秒（每条 25 ms），而 Python handler 只花 0.8 ms ⇒ **25 ms 不在 Python 里**；
因为永远发最新位置，不产生累积延迟，只是刷新率封顶 39 Hz。

🔴 **一条我制造过事故、但还没修的设计缺陷**：网关**收到 `GET /offer` 就立刻 `swap()` 踢掉当前观看端**
⇒ 我那个协商不上 H.265 的内嵌浏览器每 2 秒重连一次，就把用户的连接每 2 秒踢一次
（他"手机画面加载很久还不动"很可能就是这个）。将来 iPhone 打开页面会现场复现。
修法：① 等 `POST /answer` 协商成功再接管；② 页面区分永久失败（codec 不支持 → 停止重连 + 说人话）和临时断线。

**产物**：`D:\02_baidu\自建镜像\K11C_v12_ubuntu2404_selfbuild-kvm-mousefix-20261026.img`
7,188,269,642 B / md5 `f4511892e0869b9b0044ee3b68a95583`（VM 与本机两边一致）。
验法和以前不同：**把镜像里的 `k11c-gw`、`index.html` dump 出来算 md5 和板子上正在跑的逐字节对**
（`c34ec5ab…` / `aa2cee19…` 两边一致），并查了镜像内四个关键文件都是 `0755`（防 203/EXEC）。
退路：VM 上 `ubuntu-rootfs.img.bak-20261026`（= 上一版 dc-20261021 的 rootfs）。
**10-27 用户烧了 mousefix 版并复测"确实很好了"** ⇒ 覆盖式转发确认活在固件里，不是只活在 `/opt` 那份手改文件；
"镜像 dump 出来和板上逐字节对 md5"这条验法由此拿到了端到端闭环（机器一致 + 人体感一致）。



### 【10-20 下午】固件烧上了 + T16 量出第一个真实端到端数

**手机比电视慢 2 帧 = 33–40 ms**（三张同框照片，时间差和帧号差两个独立量互相印证：−40/−33/−40 ms、都是 −2 帧）。
对比软路径的"电视落后手机 13.166 秒"⇒ **方向反了、量级差约 400 倍**。
手机侧 `H265 1920x1080 fps=60 dropped=7 lost=0 jb=10–11.7 ms`；板子 CPU **≈38%**、load 1.86。
冷上电真数：**电视约 10 秒出画面**（fakevo @8.0 s 启动、9.7 s active）、**手机 16–20 秒能连**（`network-online` 15.4 s）。
`multi-user.target` 要 29.4 s 是 `snapd.seeded` 22.6 s 拖的，**不在 fakevo 关键路径上** ⇒ 别拿它当"开机慢"的证据。

🔴 **下一个该打的靶子已经换人了**：人报"RPC 一般 60 ms"，而板子内部 `last_ms=0.3`、`last_err` 全空
⇒ **手感现在被上行控制的 60 ms 主导，不是视频那 33 ms**。方向：把控制从 HTTP `fetch` 挪到
和视频同一条 **WebRTC datachannel**（JetKVM 就是这么做的）。别再去做 WiFi 省电那条（上面已证零收益）。

### 【10-20 晚】T20 鼠标搬到 WebRTC datachannel（照 JetKVM 的 hidrpc）

**JetKVM 的控制通道不是 JSON-RPC，是二进制报文**（读 `jetkvm/kvm` 的 `internal/hidrpc/hidrpc.go`+`message.go`+`ui/src/hooks/hidRpc.ts` 才确定）：
`[1 字节类型][载荷]`；`0x01 Handshake(版本) / 0x02 KeyboardReport / 0x03 PointerReport / 0x04 WheelReport / 0x05 KeypressReport / 0x06 MouseReport / 0x07 KeyboardMacroReport`，
**`PointerReport = 0x03 + x(int32 大端) + y(int32 大端) + buttons(u8)` 共 10 字节**；收包侧按类型分 4 条队列、`IsString` 拒收、队列满就丢。

我们的取舍（下次别推翻）：
- **只搬鼠标**（移动+按键共用 PointerReport 这一个报文，是唯一吃延迟的）。键盘/文字继续 HTTP：
  他的 `WheelReport` 源码里**只有类型号没有字节布局**，`KeyboardReport` 是状态式、和我们服务端 `keyCombo`（按压语义）不匹配 ⇒ **不自己发明格式**。
- **HID 逻辑只保留 Python 一份**：网关收包线程只入队，一条 worker 串行转 `absMouseReport` 打给本机 `127.0.0.1:8000/rpc`。
  转发必须把响应体读干净（`io.Copy(io.Discard, resp.Body)`），否则 keep-alive 不复用、每次多几毫秒。
- **一处故意偏离**：JetKVM 是浏览器建通道 + perfect negotiation 二次协商；我们改成**板子在 offer 里先建、浏览器 `ondatachannel` 接**，
  报文逐字节一致但省掉整套重协商。
- 前端 `sendPointer()` 通道没开就自动退回 HTTP，状态行显示 `鼠标 DC / HTTP`。

实测：`dc_open=true`、`dc_bad/dc_drop/dc_http_err` 全 0、Python `absMouseReport` 计数对得上；
落点精确（画面 90% → 光标 `1727,971`，期望 `1728,972`，差 1 px 是取整）；手工 `dc.close()` 后自动退回 HTTP 且落点照样对。
⚠️ **省了多少毫秒没量**：DC 不等回执，页面上量不到往返 ⇒ 只能靠手机体感（他还没反馈）。
⚠️ **固件里还是 T18 那份**（没有 datachannel）；板上 `/opt/k11c-kvm/k11c-gw` 已是新版 10,289,336 B。
**等他手机验过再重打一次镜像，免得烧两遍。**

🛑 **这次自己制造的一次事故**：用 `sed -e '1,1284p' -e '1326,$d'` 搬文档段落，**漏了 `-n`** ⇒ sed 默认还要再打一遍，
整份 1450 行文档被写成 2650 行重复内容。靠 `git checkout --` 还原 + 追加备份块救回（备份块是提前 `sed -n '1285,1325p' > /tmp/t20.blk` 存的）。
⇒ **下次改文档段落顺序：先 `git diff --stat` 看清净变化，别用不带 `-n` 的 `sed p`。**

烧录后确认到的（T18 那份固件的验收，仍然有效）：`/etc/netplan/90-NM-k11c.yaml` 在（WiFi 烘进去生效，冷上电直连 `Duck_5G`）、
`k11c-gw` 可执行、`iw` 不在（故意没烘）、gadget 脚本是修好的 `31743bd6` ⇒ **重启不再变"无法识别的设备"这条终于闭环**。

## 【10-21】控制全搬 datachannel：**HTTP 53ms → DC 10ms**（同一条链路交替 A/B，各 15 样本中位数）

用户"直接改吧 别人怎么做照着做" ⇒ 不再只做鼠标。**JetKVM 的通道划分**（`ui/src/hooks/useHidRpc.ts`）：
`hid`（可靠有序）/ `hid-unreliable`（**不重传**）/ unreliable-nonordered 三条；
报文补齐 `0x01 Handshake`（**设备原样回一条**，对端据此判定 hidrpc 可用）、`0x02 KeyboardReport[modifiers][keys…]`、`0x05 KeypressReport[key][press]`；
**`0x04 WheelReport` 他设备侧根本没有 case**（滚轮走 JSON-RPC）⇒ 照此不实现，别自己编布局。

🔑 **最重要的一个认知纠正**：他手机上"RPC 60 ms"**主要不是无线电**——
裸 socket 同一条路 8–26 ms（T19 口径），浏览器 `fetch('/rpc')` 却量到 **53 ms**，
多出来的 ~40 ms 是**浏览器 HTTP 那套机制**（请求对象/连接调度/隐藏页节流）。
datachannel 是消息帧、不经过这套 ⇒ **10 ms**。**以后判断"网络慢不慢"，先分清是哪一层的开销。**
- 量法：页面加了 `测延迟 DC vs HTTP` 按钮，**交替**发 30 次 `ping`、各取 15 个样本算中位数
  （交替 + 中位数是硬要求，单时段先测后测会测出假效果，见坑 34）。
- 一处**故意偏离**：他把按键也放不可靠通道，我们按键走可靠 ——
  我们的"按下/松开"是两条独立报文、没有后续覆盖，丢了会**卡在按住状态**；只有"新值覆盖旧值"的移动才适合不重传。
- 两个"看着成功其实没通"的坑：**`pending` 和鼠标节流变量撞名**（一点打字就抛异常）；
  **`Send()` 发二进制帧** ⇒ 对端 `JSON.parse` 拿到 ArrayBuffer 静默失败、Promise 只能等超时，**要用 `SendText()`**（他设备也是发文本帧）。
- 板子上已跑通；**10-21 已重打固件**：`K11C_v12_ubuntu2404_selfbuild-kvm-dc-20261021.img`
  7,188,269,642 B / md5 `32e0c0fac4289e1de79ad484b03dc79f`。抽查改成**从镜像 dump 出来算 md5 跟板上正在跑的逐字节对**
  （`k11c-gw 5c2cc0c6…`、`index.html 25b6136b…`），不看 `debugfs ls` 就下结论。

🔴 **但"省 43 ms"这条被人的实测否掉了**：用户真机试完说"**体验不出来，不过已经很好用了**"。
⇒ 那个 53 ms 基线是**我这台笔记本隐藏页面**量的，Chrome 节流把它抬高了（坑 33/34 同一类）；
手机页面可见，HTTP 本来没那么慢。**方向没错（少一层浏览器 HTTP 机制、移动不重传），但收益量级必须在手机上用同一个 A/B 按钮重测才算数，现在没有这个数。**
⇒ **手感下限现在由视频回程 33–40 ms 决定，控制传输这层已经不是瓶颈**；要再往下压该动视频侧
（`gop=60` 写死、无 RTCP/PLI、无拥塞控制），不是控制侧。
**教训：报"省了多少毫秒"之前先问一句这个基线是在什么状态下量的**——我这台机器上"隐藏页面"这个状态反复咬我（丢帧假象、事件冻结、HTTP 被抬高），已经是第三次了。









## 【10-20 晚】T17 定了 A 形态并上板过了两次重启 ⇒ 固件已经编出来等人烧

用户原话："**我要桌面没用 tv 只要显示这个码流 1080 60** … 你先弄 弄好就编译固件"。
他有一句理解偏差要记着纠正：**硬编码不需要重烧**（`mpph265enc` 一直在跑），重烧只是为了**持久化板上跑出来的东西**；
电视给他的是**原始帧 scanout**，不经过解码。

- **A 形态上板实测**：`disable lightdm` + `set-default multi-user.target` + 三个正式 unit（fakevo / gw / kvm 带 `--no-mjpeg`）；
  两次热重启都过：**13.5 s 到 multi-user、fakevo 7.87 s 起来、`:8000` 24 s 就绪、`miss=0`、HID 两次都 `configured`+键盘鼠标都在**。
  重启后电脑浏览器**自己重连**上新 offer ⇒ 断线重连有机器证据了。
- ⚠️ **`quick_check.ps1` 报 `present=False` 不等于设备不在**：它读的是注册表里的旧到达/移除记录；
  判"现在有没有"要 `Get-PnpDevice -PresentOnly`（`host/t17_hid.ps1`）。
- **固件产物**：`D:\02_baidu\自建镜像\K11C_v12_ubuntu2404_selfbuild-kvm-h265-20261020.img`
  = **7,187,221,066 B / md5 `01c089b66e2472cde444f378ce560a0d`**（VM 与本机两边一致）。
  旧 rootfs 备份在 VM：`ubuntu/ubuntu-rootfs.img.bak-20261020`（md5 `d90cb0d6…`）—— 回滚就改这个名。
  🔑 镜像里 `/usr/local/sbin/k11c-gadget.sh` dump 出来是 **`31743bd6`**（坏的那版 `cc42db76` 彻底换掉了）。
- **烧完就没有桌面**（选 A 的结果，不是故障）；回桌面要先 `systemctl stop k11c-fakevo` 再 `set-default graphical.target`。
- 板上现在也是 A 形态。`k11c-probe`（8002 静态服务）**故意没进固件** ⇒ 以后要测手机 H.265 能力得临时起一个。

**出固件这一趟踩到的、下次一定会再踩的三条**：
1. `mk-image.sh` 是 `rm ubuntu-rootfs.img` 再用 `binary/` 重建 —— **输入被自我消耗**，不先备份就别编译。
2. 只有 `ubuntu/overlay/` 里的东西活得过下一次构建（每次构建 `rm -rf binary` → 从 img 重铺 → `cp -rpf overlay/*`）。
   **直接改 `binary/` 会被冲掉**。
3. Windows 侧 `scp` 回来的二进制是 644，**本机 chmod 保不住**；必须在 VM 上补 755，否则镜像里 644、开机 `status=203/EXEC`。
   软链同理（Git Bash 的 `ln -s` 建出来是普通文件）⇒ **属主/模/软链全部在 Linux 侧定**。

## 【10-21 晚】移植账 + 固件"开机即目标形态"的验收方式

**dc 版固件已确认就是"上电即产品形态"，不用重编**。验法不是推理，是**把文件从镜像 dump 出来看内容**：
`strings` 搜到 `hid-unreliable`/`jsonrpc`（证明是三条通道那版）、`index.html` 里有 `测延迟 DC vs HTTP`、
4 个 enable 软链、`default.target → /lib/systemd/system/multi-user.target`、`usb-gadget.service → /dev/null`、
netplan `0600 root`；**`rockdev/boot.img` 时间戳 = 10-16 13:47**（就是加了 `F_HID` 那次编的，
`build.sh rootfs/updateimg` 不碰内核 ⇒ 别以为重打固件会丢键鼠）。
冷上电预期：**~8 s 键鼠枚举 / ~10 s 电视出彩条 / ~16-20 s 手机可连**。
四个"它就是这样不是坏了"：① 开机是**彩条不是被控机画面**（没采集）② WiFi 口令写死 `Duck_5G`，换网络只能走串口重配
③ 板子 IP 会漂（`.89`/`.90`）④ 8002 调试页故意没烘。

**移植账（用户追问"哪些移植了哪些没移植、为什么是照设计不是直接移植"，答法定下来了）**：
- **照抄的是"和外界怎么说话"**：HID 报文与 report descriptor、JSON-RPC 方法名（为了以后能接他前端）、
  hidrpc 二进制报文 + 三条通道划分、Go+pion 这个选型、RTP 直通不重打包、"板子跑服务/浏览器当界面/局域网不用 STUN"。
- **不抄的是"他内部怎么组织"**：`internal/usbgadget` 那 16 个文件里的 changeset 事务机制（他要在运行时改 gadget，我们开机建一次就够）、
  `nmlite`+自带 DHCP（他有线上网需求，我们用 NetworkManager）、云/OTA/prometheus/TLS 鉴权（自用一台）、
  `ui/` 那 208 个 React 文件（**搬 UI = 连 118 个方法 + perfect negotiation 一起搬**）。
- **平台抄不动的**：他绑 RV1106（`/sys/devices/platform/usbdrd`、MIPI-CSI 采集、H.264）；K11C 只有 HDMI 输出。
- **明确的能力缺口（下次别再从零想）**：① 键盘直通 + `keyboardLayouts/*` 没做 ⇒ 只能"输入框打字"，不能当直通键盘
  ② **RTCP 完全没处理**（不收 PLI/FIR、不发 NACK、无拥塞控制）+ `gop=60` 写死 ⇒ 新连接/重连最多黑 1 秒、丢包要撑到下个 IDR
     ⚠️ **10-26 更正：这不是"落后于 JetKVM"，是打平**。他 `webrtc.go` 把 RTCP 读出来**直接丢弃**，
     且 `webrtc.NewAPI()` 只传 SettingEngine、**没注册 interceptor** ⇒ 他也没有 NACK/PLI/GCC（那段"for things like NACK"
     的注释是 pion 示例样板）。⇒ **做 PLI→强制 IDR 是超过他，不是追赶他**，别再说成补作业。
  ③ `0x06 MouseReport` 相对鼠标没做（gadget 没挂 hidg2）④ 键盘 LED 回读没做
  ⑤ 真画面来源未定（采集棒 vs 被控机 agent）——**这条决定它算 KVM 还是算远程桌面中继**。
- **GPL 界线（他已授权"照着移植"）**：只看设计/接口自己写 = 不传染；复制改造源码 = 衍生品。自用不分发无公开义务，
  **一旦公开或分发，上面"照抄的那一栏"必须按 GPL-2.0 开源**。

**备份/分布上的两个待办**：① **`github.com/duck-sleep/win_game` 的可见性没确认**（API 被限流 403），
而仓库里有明文 WiFi 口令 `00000000` 和板子 sudo 口令 `kickpi`（`host/fw_stage.sh` 当默认值写死、`wps_ab.ps1`、`01_工程说明.md`）
⇒ 若是 Public，删文件不够，**git 历史里还在**，要改历史 + 换口令。
② **VM 建议打快照**：`~/k11c/prebuilt/update.img`（7.17 GB，rootfs 唯一源头，本机 `D:\02_baidu` 那几份是 5.10 线的配不上 6.1）
和 `ubuntu-rootfs.img.bak-20261020` 都只有 VM 一份。

## 【10-26】T16 量完 + 用户烧了两版固件 + 鼠标手感修好；WiFi 省电那条债被数据销掉

**① 第一个真实端到端数：手机比电视慢 2 帧 = 33–40 ms**（用户拍 3 张同框照片）。
可信的原因是**两个独立量互相印证**：时间差 −40/−33/−40 ms，帧号差三张都是 −2（2×16.67=33.3 对得上）。
对比软路径"电视落后手机 13.166 秒"⇒ **方向反了、量级差约 400 倍**。
⚠️ 口径：起点是"帧已生成"，**不含采集段**（源还是假彩条），所以**不能和 JetKVM 宣传的 30–60 ms 直接比**（他那是从 HDMI 口起算）。

**② 冷上电真数**：电视 **~10 s** 出画面（fakevo @8.0 s 启动、9.7 s active）、手机 **16–20 s** 可连。
`multi-user.target` 要 29.4 s 是 `snapd.seeded` 22.6 s 拖的，**不在 fakevo 关键路径上** ⇒ 别拿它当"开机慢"。

**③ 🔴 WiFi 省电这条从 10-17 挂到现在的债，实测是零收益，别再照老结论做 hack。**
`iw` 确认板子 `Power save: on`；但**ON/OFF 交替 60+60 样本**量"空闲 400 ms 后一条完整 TCP 往返"：
**中位 14 / p90 111 两边一模一样**，只有最大值 194→114。真正决定尾巴的是**链路忙不忙**：
视频流一跑起来，max 从 123 掉到 26（真实使用中 p90=16 ms）。
⇒ 产品里手机一直在收流，电台不会睡，**这条咬不到**。
NM 的持久化也没走通：`conf.d` 里 `[device-wifi]` 和官方那种 `[connection] wifi.powersave = 2` 两种写法，
重连后 `iw` 都还报 `on`（手动 `iw set power_save off` 立刻生效）⇒ **为一条零收益的路径上 NM dispatcher 不值，故意没进固件**。
⚠️ 副作用：**板上 `apt install iw` 了，包数 2395→2396**，下次做板子/镜像一致性审计会看到这条差，别当漂移。

**④ 🔴 未修的设计缺陷（下次一定还会咬人）：`GET /offer` 一进来就把当前连接踢掉。**
网关"同一时间只服务一个观看端"，但接管发生在 **offer 阶段**而不是协商成功之后 ⇒
**一个注定连不上的客户端，只要每 2 秒重试一次，就能把正在看的人反复踢下线。**
10-26 真实事故：我那台内嵌浏览器协商不上 H.265（回了 `m=video 0`）→ 每 2 s 重连 → `offers` 冲到 329 →
用户手机"画面很久才加载还不动"、笔记本"鼠标不跟手"**很可能都是这一个原因**。我把测试页导航走就好了。
⇒ 修法两条（**还没做**）：① 网关等 `POST /answer` 真的成功了才 swap；② 页面区分"协商失败(永久)"和"网络断(临时)"，
永久的停止重连并显示人话。**将来有人拿 iPhone 打开页面就会重现**。

**⑤ 手感修好了（用户："手感可以了"）**：鼠标移动改成**只保留最新一条**（覆盖式，不再排队）+ 不可靠通道改**保序不重传** + DC 下节流 30→16 ms。
20 秒实测：`dc_in 1152`（≈58 条/秒，几乎打满 16 ms 上限）、`dc_coalesced 426`、**`dc_drop 0`**（之前溢出丢 56 条 = 6.7%）。
**根因不是丢包，是"排队转发会把 200 ms 前的旧位置补发给 Windows"⇒ 光标倒回去 = 不跟手。**
⚠️ 下一层瓶颈（已量到、未查）：**网关→Python 这一跳只吃得下 ~39 次/秒（每条 25 ms）**，而 Python 自身只花 0.8 ms
⇒ 时间不在 Python 里。因为"永远发最新位置"所以**不再产生累积延迟**，但刷新率被限在 ~39 Hz。

**⑥ 🔑 一条会反复用到的产品常识：在被控机自己的浏览器里操作被控机 = 正反馈回环。**
物理鼠标和板子的虚拟鼠标**控制的是同一个 Windows 光标**：你一动 → 页面发绝对坐标 → 光标被传送 →
浏览器又根据被传送后的位置发下一条 → 光标来回跳，表现就是"延迟很大、肉眼可见不跟手"。
手机没这问题（手指位置 ≠ 光标位置）。
⇒ 判别法（10 秒）：**别拖画面，只点页面上的"左键/右键"按钮**；按钮正常、只有拖动难受 = 回环，不是固件缺东西。
（我早先"笔记本 raw socket 8–26 ms"没暴露这个，是因为我用的是**合成 PointerEvent**，不移动真实光标。）

**⑦ 浏览器 H.265 支持是"状态相关"的，不是一锤定音**：同一个 Qoder 内嵌浏览器 10-20 能收 H265 60fps，
10-26 直接回 `m=video 0 UDP/TLS/RTP/SAVPF 0`（整个视频被拒）。⇒ **T10 那道"手机吃不吃 H.265"的闸门要允许重测**，
别把某一次 true 当永久结论。

**⑧ 用户已亲手烧了两版固件**（`...-kvm-h265-20261020.img` → `...-kvm-dc-20261021.img`），
第三版 `...-kvm-mousefix-20261026.img` 已出并拉回本机（7,188,269,642 B，md5 与 VM 侧一致），等人烧。
**验"烘进去的就是手上这版"的做法**（不是看目录列表）：把 `k11c-gw` / `index.html` **从镜像 dump 出来算 md5，
跟板子上正在跑的那份逐字节对**。备份命名沿用 `ubuntu-rootfs.img.bak-<日期>`（现有 `.bak-20261020`、`.bak-20261026`）。

**⑨ 工具环境一条**：`git push` 失败并出现 `Connection closed by 198.18.0.x port 443/22` ⇒
**是本机 Clash(TUN) 劫持了 GitHub 的 SSH，不是仓库权限问题**；让用户切/关 Clash 即可（10-26 实测两次都是这个）。

---

## 【10-27】公网接入调研（用户"好像有个公网方案是不是" + "JetKVM 是不是有类似方案"）

**⚠️ 先记一条环境事实**：`github.com/duck-sleep/win_game` **是 public**（未登录 `GET api.github.com/repos/...`
返回 200、`"private": false`）。里面有明文：WiFi `Duck_5G`/`00000000`（`26_k11c_kvm/host/t2_wifi.txt` 等 8 个文件）、
板子 `kickpi`/`kickpi` 与 `root`/`root`。用户口径是"安全问题无所谓 就我用"，**但那是以为仓库私有**。
我给了两条收口建议（转 Private / 换口令），他还没拍板。**以后往这个仓库推东西，默认按"公开"对待**。

**为什么现在出不了家门（已证，代码级）**：`board/gw/main.go:117` 建 PC 用**空配置** `webrtc.Configuration{}`
⇒ 无 STUN 无 TURN ⇒ 只有 host 候选（LAN IP）。这不是残缺：JetKVM `IsCloud=false`（局域网连）时
`iceServer` 也是空的，**我们等于他的 LAN 模式**。当年 §2 把"云/Tailscale/登录"划成"不做·按需"（方案文档 L320/L1112）。

**板子网络实测（只读命令，无安装无重启）**：`aarch64`；IPv4 出公网 OK（github 200/0.59s、ports.ubuntu.com 200）；
**IPv6 完全没有**（只有 `fe80::`，`ip -6 route get` = `Network is unreachable`）⇒ v6 直连这条最省事的路在家不通；
Tailscale 四件套全可达（`pkgs.tailscale.com` 200、`controlplane`/`login` 302、**`derp9.tailscale.com:443` 200**）；
`wlan0` 上挂了**两个 IPv4**（`.89` metric 600 / `.91` metric 3003，两条默认路由）但 `nmcli` 只有一个活动连接 —— 要固定地址先理清这个。

**JetKVM 的公网方案（读他 `dev` 分支源码得到，不是博客二手货）**，三块拼图：
1. **信令 = 设备主动出一条 WebSocket 到云**（`cloud.go:308`，ping 间隔要小于云侧超时；注册 `POST {cloud}/devices/token` 用配对码换 token，`cloud.go:226`）
   ⇒ 设备侧**不需要公网 IP / 端口映射 / IPv6 / 路由器设置**。
2. **媒体 = 云按会话下发 ICE**（`cloud.go:463 ICEServers: req.ICEServers` → `webrtc.go:453-458` 仅 `IsCloud` 启用）。
   他的 TURN **不是自建 coturn**，是找 **Cloudflare 托管 TURN** 现生成临时凭据
   （`cloud-api/src/webrtc.ts:114 rtc.live.cloudflare.com/v1/turn/keys/{CLOUDFLARE_TURN_ID}/credentials/generate`，
   还把 `turns:` 过滤掉 :134）。另有 `webrtc.go:461-475 SetICEAddressRewriteRules{External:[req.IP], Append, AsCandidateType:srflx}`
   = 把云发来的 IP 追加成 srflx 候选，不做 STUN 也拿到公网候选。
   ✅ **`req.IP` 语义已证**（`cloud-api/src/webrtc-signaling.ts:156-158`）= **云端从设备那条 WS 的 socket 源地址看到的设备公网 IP**
   （或 `REAL_IP_HEADER`）⇒ 设备不查 STUN 也知道自己的对外地址；对称 NAT 下这条失效，靠浏览器侧 TURN 兜。
   **ICE 分工（别记错）**：云给**设备**的 `iceServers` 被 `startsWith("stun:")` 硬过滤成**只有 STUN**（`webrtc-signaling.ts:26-33`）；
   **TURN 只发给浏览器**，是 `cloud-api/src/webrtc.ts:100-138` 现场找 Cloudflare 托管 TURN 生成的 `ttl:3600` 临时凭据
   （`customIdentifier=user.id`，还把 `turns:` 滤掉），旁边 `CreateTurnActivity` 按用户记中继字节 = 他的成本账本。

**🔴 读全实现挖出的三条"现在就能抄、不需要服务器"的板子侧改动**（clone 在 `C:\Users\123456\AppData\Local\Temp\jetkvm-ref`）：
1. **协商成功才接管**：`cloud.go:472-476` 先 `ExchangeOffer`，`err != nil` 直接 return、**不碰 `currentSession`**
   ⇒ 这就是我们 `/offer` 踢人那条缺陷的现成修法，不用再自己设计一遍。
2. **换人/关闭时清 HID 状态**：`cloud.go:479-480` `CancelAllAutoReleaseTimers()` + `rpcKeyboardReport(0, clearKeys)`，
   ICE 关闭路径 `webrtc.go:632-642` 再做一次。**我们完全没有**（`gw/main.go:296 shutdown()` 只 `close(s.queue)`，
   `kvm_server.py` grep `clear|release|reset` 只命中内核版本号）
   ⇒ **手机按住 W 键时断线/被接管 = Windows 永久卡在按住 W**（游戏里角色一直往前跑）。
   **这条优先级排在"公网"之前**，因为它是此刻就在发生的可感知故障。
3. **被踢的人收到事件不是黑屏**：`writeJSONRPCEvent("otherSessionConnected")` + **睡 1 秒**才 `peerConn.Close()`（`cloud.go:478-485`）。

**两条旧说法核实完毕**：① "他丢弃 RTCP"**成立**（全仓 grep `PLI|FeedbackType|OnRTCP|RequestKeyFrame` = 0，只注册 `playout-delay`，`webrtc.go:493`）
⇒ "我们做 PLI→强制 IDR 会比他强"这条判断继续有效；② `MqttConfig` 默认 `Enabled:false` + `EnableHADiscovery` ⇒ **是 Home Assistant 集成，不是穿透通道**。

**能不能白嫖他的云？查完注册流程的结论：不能、也不该**（10-27，用户"我们用他的公网服务吗 还是要自己注册"）：
入册 = App 走 Google 登录 → 云 `device.upsert({create:{id: deviceId, tempToken}})`（`cloud-api/src/oidc.ts:146-157`，tempToken 5 分钟）
→ 设备用 tempToken 换长期 `secretToken`（`devices.ts:95-110`）。**云侧对 `deviceId` 没有硬件验真**（就是个字符串），
但四条否决：① 他家 deviceID = **读 RV1106 芯片序列号**，读不到写死 `unknown_device_id`（`kvm/hw.go:70-81`）⇒ 我们 RK3566 天生对不上；
② 走通要把**整套设备端协议再实现一遍**，比自己搭隧道贵；③ TURN 是**他付钱的 Cloudflare 额度**（`CreateTurnActivity` 记字节=他的账单）；
④ 前端按他家 SKU/版本渲染，混进去的设备出问题没有解释权。
⇒ **要分清三个"别人家的服务"**：JetKVM 的云（借不到）／Cloudflare 托管 TURN（**可以自己注册**，要域名）／Tailscale（**可以自己注册**，Google 登录即可，免费 3 用户 100 设备，我们代码零改动）。
用户网络名词不熟，已在 `12_win_上机跑\15_KVM公网连接方案.md` 加 §0.5 名词小抄（NAT/CGNAT/信令/ICE 候选/STUN/TURN/隧道/DERP/OIDC 各一句人话）+ §5-F 这节对比。

**✅ 10-28 更正（用户说"我们是互相合作的，他们说新硬件序列号按开源填一个是不是也可以"）**：
我之前把"deviceID 绑 RV1106 专属编号 ⇒ RK3566 天生对不上"当成否决理由，**这条是错的**。
`hw.go:15-32` 读的是**通用** `/proc/cpuinfo` 里 `Serial\s*:\s*(\S+)`，而 **RK3566 也有这行**：
实测 `grep -i '^serial' /proc/cpuinfo` → `Serial : 598b4eba996bfdf6`（`/proc/device-tree/serial-number` 同值，来自 RK3566 OTP）。
备选唯一标识也都实测存在：eMMC CID `0x1bba93e1`、wlan0 MAC `60:48:9c:b7:57:d4`、`/etc/machine-id`。
⇒ **他的设备 ID 逻辑在我们板上开箱可用，不用改代码、不用伪造**；配合"云侧 `oidc.ts:146-157` 对 deviceId 无验真"，
"填个号注册进去"技术上成立。**剩下的真实障碍只有三条**：设备 API 面（前端不在开源仓库）、TURN 是谁的钱、协议解释权。
🔴 **砖机红线**：SKU 绝不能冒充 `jetkvm-v2` —— 他 `SKUS` 表里该 SKU 的更新包是 **RV1106 的 `system/update.img`**，
前端一弹更新就刷进 RK3566 = 废板。未知 SKU 反而安全（`releases.ts:46` `isKnownSku` 白名单，未知直接 400，刷不进去）。
⇒ 有合作就要三样：正式 SKU 名（如 `k11c-rk3566`）、TURN 额度书面同意、前端对未知 SKU 的行为。
另外他设备自己也开 `protected.GET("/webrtc/signaling/client")`（`web.go:202`），`isCloud=false` 时不填 ICE —— **和我们完全同款**，
本地那层鉴权是 `HashedPassword`/`LocalAuthToken`/`LocalAuthMode`/`LocalLoopbackOnly` + `/auth/login-local`；
他还得多背一个 `web_tls.go`（自签证书）就因为浏览器要求安全上下文才给 WebRTC。
3. **身份 = Google OIDC 卡归属**（`cloud.go:400-426`，id token 验完还要比 `config.GoogleIdentity`，不符回 `google identity mismatch`）；
   本地模式另有 `HashedPassword`/`LocalAuthToken`/`LocalAuthMode`/`LocalLoopbackOnly`（`config.go:101-104`）。
   `MqttConfig` **默认 Enabled:false**（`config.go:211`）——那是 Home Assistant 集成，**不是穿透通道**，别被仓库里的 mqtt 字样误导。

**给用户的三条路（未定，等他拍板）**：A. **Tailscale**（零代码改动，pion 把 tailscale 网卡当 host 候选，中继时 WG 连媒体都带得动；代价=每端装 App、手机变全局 VPN）；
B. **照 JetKVM**（信令走公网入口 + 两端填 `iceServers`；代码小、要养一台公网服务）；C. **白嫖版** = `cloudflared tunnel` 穿信令 + Cloudflare Network Turn 穿媒体
（**国内到 CF UDP/443 稳不稳未证**）。E 只穿 HTTP 的方案带不动 WebRTC 媒体，只能退 `?mjpeg=1`（固件里已 `--no-mjpeg`），只配应急看一眼。
🔴 **A/B/C/D 之前都必须先补两条**（他有我们没有）：**零认证**（谁能连 `:8000` 谁就能注 HID = 拿到被控 Windows 完全控制权）
+ **`GET /offer` 一进来就踢人**（公网会被循环 offer 变成持续 DoS）。建议顺序：修这两条 → 上 A → 需要"零安装"才做 B/C。

**取源码的土办法（下次还用得上）**：本机到 GitHub 的 HTTPS 会随 Clash 状态时好时坏（`curl` 直接 000），
**jsDelivr 稳定**：`https://cdn.jsdelivr.net/gh/<owner>/<repo>@<branch>/<path>`；
文件清单用 `https://data.jsdelivr.com/v1/packages/gh/<owner>/<repo>@<branch>?structure=flat`。
仓库名以 org API 为准：设备侧是 **`jetkvm/kvm`**（默认分支 `dev`，不是 `device`），云侧 `jetkvm/cloud-api`。









