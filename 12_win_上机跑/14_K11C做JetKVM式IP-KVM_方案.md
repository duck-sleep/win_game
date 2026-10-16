# 14 — 用 K11C（RK3566）做一台 JetKVM 式 IP-KVM：可行性与方案

> 2026-10-16 起。目标：拿手上这块 KICKPI K11C V1.2 做一台远程开关机/进 BIOS/装系统的 KVM over IP。
> 编译链和上板结果见 `13_KICKPI_K11C_RK3566_编译烧录.md`（已跑通，自编固件在板上活着）。
> 本文里每条硬件结论都标了**已证 / 待证**，别把待证当依据下单。

## 0. 一句话结论

**架构上可行，卡点只有一个物理问题：K11C 哪个口接在 OTG 控制器上。**
SoC 层面两条腿都齐：一个 USB 控制器能做 device（往被控机伪装键盘鼠标），一个只能做 host（吃 HDMI 采集棒），
外加千兆有线网口。真正的工作量在软件——**当前内核没有 HID gadget，要自己开并重编**。
视频输入 K11C 原生没有（HDMI 是输出），最省事是 USB 采集棒；想要低延迟就得走 MIPI 桥，那是硬件改造。

## 1. JetKVM 到底开源了什么

| 项 | 原版 JetKVM | **JetKVM Mini**（你给的那篇博客） |
|---|---|---|
| 形态 | 全功能 IP-KVM 桌面盒 | 火柴盒大小 |
| 主控 | Linux SoC（视频侧另有专芯，见下） | **ESP32-P4** |
| 视频 | 1080p@60，H.264，官方标 **30–60ms** | **1080p@30** |
| 音频 / USB 存储 | 有 | ❌ **都没有** |
| ISO 挂载 | 支持 | 用 **TF 卡**装 |
| 网络 | 有线 | 有线版 / 无线版两种 |
| 价 | 较高 | **$39–42** |

**开源范围（GitHub org `jetkvm` 实测，9 个仓库）**：

| 仓库 | 许可证 | stars | 是什么 |
|---|---|---|---|
| `jetkvm/kvm` | **GPL-2.0** | 5247 | 主固件，**Go + TypeScript + 部分 C**，跑在设备上 |
| `jetkvm/cloud-api` | GPL-2.0 | 233 | 官方云（WebRTC 远程穿透那套） |
| `jetkvm/rv1106-system` | 未标 | 177 | ⇒ **原版的视频采集侧是瑞芯微 RV1106**（MIPI 入 + 硬编 H.264），不是主控在抓视频 |
| `jetkvm/docs` | GPL-2.0 | 61 | 官网 |
| `jetkvm/jetkvm-native` | GPL-2.0 | 23 | 原生组件 |
| `dc-extension-firmware` / `atx-extension-firmware` | 未标 | 31/29 | 电源/ATX 扩展（远程开机那一层） |
| `rkcrypto` | 未标 | 4 | RV1106 侧密码学 |

> 🔴 **"开源"主要指软件。org 里没有原理图 / Gerber / BOM 仓库** —— 想照抄硬件这条路走不通，
>   想复用固件则要受 GPL-2.0 约束（衍生也必须 GPL-2.0）。
>   上面这些用 `curl -s https://api.github.com/orgs/jetkvm/repos` 一条命令就能复核，别信我抄的。

**结论：JetKVM 的固件不能直接搬到 K11C** —— 它的视频管线绑死 RV1106（或 Mini 的 ESP32-P4），
云鉴权/OTA 绑死官方 `cloud-api`。可以搬的是**设计**：分层方式、HID 报文封装、keymap、WebRTC 出流。

## 2. K11C 的硬件账（逐项，标注证据）

| 需要的能力 | 板子实际 | 状态 | 证据 |
|---|---|---|---|
| **往被控机伪装 HID** | `usbdrd_dwc3: usb@fcc00000`，**`dr_mode = "otg"`** | ✅ 硬件支持 | `rk356x.dtsi` |
| **接 USB 采集棒（host）** | `usbhost_dwc3: usb@fd000000`，`dr_mode = "host"` | ✅ 与 OTG 口分离，可同用 | `rk356x.dtsi` |
| UVC 主机驱动 | `CONFIG_USB_VIDEO_CLASS=y` | ✅ 插上即 `/dev/video0` | `kernel-6.1/.config` |
| **HID gadget 功能** | `# CONFIG_USB_G_HID is not set`、`# CONFIG_USB_FUNCTIONFS is not set`，config 里查不到 `USB_CONFIGFS_HID` | ❌ **要自己开+重编内核** | 同上 |
| gadget 底座 | `USB_GADGET=y`、`USB_LIBCOMPOSITE=y`、`USB_CONFIGFS=y`（ACM/MASS_STORAGE/F_FS）、`USB_F_UVC=y` | 🟡 底座齐，缺 HID 那一块 | 同上 |
| HDMI **输入** | 无。`hdmi@fe0a0000` 是 **TX**；`CONFIG_VIDEO_ROCKCHIP_HDMIRX=y` 是给 RK3588/3576 的驱动，板级 DTS 里**没有 hdmirx 节点** | ❌ 原生不可用 | `rk3566-kickpi-k11c*.dtsi` + `.config` |
| MIPI CSI 采集通路 | `dphy@fe850000`、`dphy@fe860000`、`rkcif` / `rkcif_mipi_lvds` 都在 SoC dtsi 里 | 🟡 **SoC 有，板上有没有引出未知** | `rk356x.dtsi` |
| 硬件编码 | `CONFIG_ROCKCHIP_MPP_SERVICE=y`；RK3566 带 VPU（H.264/H.265 档位以本地 `RK3566-Datasheet_V1.1.pdf` 为准，**我没核**） | 🟡 有，能力档位待核 | `.config` |
| 网络 | 千兆有线：`rk_gmac-dwmac fe010000.ethernet`，PHY `MAE0621A-Q2C`，接口名 **`end1`** | ✅ KVM 首选这条 | 板上 `dmesg` |
| 算力/内存 | 4×Cortex-A55，板上 Ubuntu 24.04 已活着 | ✅ 富余 | 上板实测 |
| 远程开关机 | 板上有 RECOVERY/RST/POWER 键 + 需接被控机 POWER SW | ❌ **要自己加一路继电器/光耦**（JetKVM 用 ATX 扩展做这事） | 设计缺口 |

**唯一真正的未知项**：K11C 的哪个物理口（Type-C / USB-A）接在 `usbdrd`（OTG）那个控制器上。
板级 dtsi 里**完全没有 usb/typec 相关配置**（我 grep 过，0 命中），所以只能实测或看原理图。
判定命令（上板跑）：
```bash
ls -l /sys/class/udc/                              # 出现 udc = 那个控制器能做 device
ls /sys/bus/platform/devices/ | grep -i dwc3
cat /sys/devices/platform/fcc00000.usb/udc/*/state 2>/dev/null   # 插上线看会不会变 configured
```

## 3. 三条路线

| | 做法 | 工作量 | 风险 | 适合 |
|---|---|---|---|---|
| **A. 移植 JetKVM 固件** | 把 `jetkvm/kvm` 的视频源从 RV1106 换成 V4L2/UVC、编码走 rkmpp、HID 走 configfs，绕开官方云 | 大 | 高（管线绑芯片；GPL-2.0 传染；OTA/云要拆） | 想要 JetKVM 的 UI/OTA 体验 |
| **B. 跑 PiKVM** | GPL-3.0、10.4k stars，成熟设计（keymap/HID daemon/Web UI 分层很好） | 中 | **官方只支持树莓派系**，搬 RK3566 属社区移植，依赖它的 OS 层与 keymapd | 想少写代码、能接受踩坑 |
| **C. 自建精简栈（推荐 MVP）** | 通用件拼：UVC 采集 → 推流；configfs HID → 控制被控机；薄 web 控制面 | 中，但**每步都能单独验收** | 低（每块都是独立可替换的通用件） | 第一版能远程看到画面 + 打字就赢 |

路线 C 的零件（**许可证待核，别默认可以闭源用**）：
```bash
# 逐条核实，别猜
curl -s https://api.github.com/repos/bluenviron/mediamtx | python -c "import sys,json;d=json.load(sys.stdin);print(d['license'])"
curl -s https://api.github.com/repos/zone/niftypm  # 参考替代
```
- **推流**：MediaMTX（吃 `/dev/video0`，出 WebRTC/HLS/RTSP，arm64 有现成二进制）
- **HID**：configfs 直接写（键盘 + 鼠标；**鼠标一定要做绝对坐标 report**，否则远程操作会疯）
- **控制面**：一个小 Go/Python 服务，浏览器事件 → `/dev/hidg0` `/dev/hidg1`
- **穿透**：先局域网直连；要出门再加 Tailscale（JetKVM 也走这条路）

## 4. BOM 与选型要点

| 件 | 选什么 | 坑 |
|---|---|---|
| 主控板 | 已有 K11C V1.2 | 长期插电；无屏不影响 |
| **HDMI 采集** | USB 采集棒，芯片 **MacroSilicon MS2109 / MS2130**（UVC 免驱） | USB2 下只能 1080p30 MJPEG 或 720p YUY2；**这类棒固有延迟**，"30–60ms" 是 JetKVM 用 MIPI+硬编的指标，别指望 USB 棒达到 |
| 或：MIPI 桥 | HDMI→MIPI-CSI 桥（TC358746 / IT6161 一类） | 要板子上真引出 DPHY lane；**K11C 大概率没引**，等于自己画板/飞线 |
| 环出（可选） | 采集棒带 HDMI loop-out 的型号 | 现场接个真显示器方便对比 |
| HID 线 | OTG 口 → 被控机的 USB-A 线 | **必须先确认第 2 节那个未知项** |
| 网络 | 网线 + 交换机 | 别用 WiFi 做 KVM；且 **SSID 必须英文名**（中文 SSID 高通栈直接 `NO-CARRIER`，SNM970 那条老坑） |
| 远程开机 | 继电器/光耦模块接被控机 POWER SW + GND | 这是 KVM 的"关机也能开"能力，JetKVM 用 ATX 扩展做，我们得自己接 |

## 5. 分阶段落地（每阶段有硬判据，不达标不進下一步）

**P0 — 把地基修干净（先做，别跳）**
```bash
systemctl status rockchip.service                    # 板上现在这个服务是 failed 的
journalctl -u rockchip.service --no-pager | tail -40
```
判据：`rockchip.service` 不 failed（它多半在配 udev/MPP/RGA 权限，关系后面硬编能不能用）。

**P1 — 打开 HID gadget，重编内核**
```bash
cd ~/k11c/rk-linux6.1-2026091606
./build.sh kernel-config        # Device Drivers → USB Support → USB Gadget →
                                #   USB Gadget Functions: HID / Configurationfs HID support
./build.sh kernel && ./build.sh uboot && ./build.sh updateimg
```
判据（板上）：`ls /sys/kernel/config/usb_gadget/` 可建实例，接上被控机后 `ls /dev/hidg*` 有节点，
被控机识别出"USB HID 键盘/鼠标"。

**P2 — 拿到视频**
```bash
ls /dev/video*; v4l2-ctl --list-formats-ext -d /dev/video0
ffmpeg -f v4l2 -i /dev/video0 -frames:v 1 /tmp/shot.png     # 出一帧
```
判据：分辨率/色彩正常，且**实测端到端延迟**（手机拍被控机秒表 + 采集端对比，别猜）。

**P3 — HID 打通到 BIOS**
在被控机 BIOS 里敲键盘、动鼠标。判据：绝对坐标鼠标能指到哪打到哪。

**P4 — 浏览器看到画面 + 控制合并**
MediaMTX 出 WebRTC；控制面把浏览器事件写进 hidg。判据：一个网页里能看能动能打，记上延迟数字。

**P5 — 无人值守能力**
静态 IP / DHCP 保留、开机自启、看门狗（`watchdog` 或 systemd `WatchdogSec`）、断线重连、
（要出门）Tailscale。判据：拔电重启后 2 分钟内自动恢复可用。

**P6 — 远程开机 + 形态**
继电器接 POWER SW；外壳/供电/散热。判据：被控机**关机状态**下也能开机进 BIOS。

## 6. 会差在哪（诚实边界）

- **延迟**：USB 采集棒做不出 JetKVM 的 30–60ms；1080p30 + 100ms+ 是现实预期。要压下去只能走 MIPI 桥 + 硬编。
- **没有音频**（K11C 有 codec 和 HDMI 声卡，但采集棒的音频路与 JetKVM Mini 一样是缺的）。
- **没有 USB 存储 / ISO 挂载**：想做"远程装系统"要另加 mass-storage gadget（内核里 `CONFIG_USB_CONFIGFS_MASS_STORAGE=y` **已开**，这条其实有戏）。
- **没有官方云/OTA**：自建方案自己管升级。
- **远程开机要外接硬件**，不是纯软件问题。
- 若复用 JetKVM/PiKVM 代码 → **GPL-2.0 / GPL-3.0 传染**，对外分发要开源。

## 7. 待确认清单（下一步就问清/测清）

1. **K11C 哪个物理口在 OTG 控制器（`fcc00000`）上？** → 看原理图 `K11C_V1.2.pdf` 的 USB 网络，或上板实测 §2 的命令
2. **板上有没有把 MIPI DPHY 引出**（决定能不能做低延迟路线）
3. RK3566 VPU 实际能编到什么档（`RK3566-Datasheet_V1.1.pdf`，本机 PDF 是 CID 字体、抽不出文字，要人眼看）
4. `rockchip.service` 失败原因（P0）
5. MediaMTX 等第三方件的确切许可证（§3 给了命令）
6. 你到底要"自己用的一台 KVM"还是"做成产品" —— 决定走 C 还是 A

## 8. 来源

- JetKVM Mini 公告：<https://jetkvm.com/blog/introducing-jetkvm-mini>
- JetKVM 固件仓库：<https://github.com/jetkvm/kvm>（GPL-2.0）；org：<https://github.com/orgs/jetkvm/repositories>
- PiKVM：<https://github.com/pikvm/pikvm>（GPL-3.0）
- 硬件依据：VM `rk-vm:~/k11c/rk-linux6.1-2026091606/kernel-6.1/`
  - `.config`（USB_GADGET / CONFIGFS / VIDEO_CLASS / HDMIRX / MPP / MODULE_FORCE_LOAD）
  - `arch/arm64/boot/dts/rockchip/rk356x.dtsi`（usbdrd=otg @fcc00000、usbhost=host @fd000000、dphy@fe85/860000、rkcif_mipi_lvds、hdmi@fe0a0000）
  - `rk3566-kickpi-k11c-v12.dtsi` / `-v12-linux.dts`（无 usb/typec/hdmirx 配置）
- 板上实测：`uname -a`、`dmesg`（gmac PHY、dwhdmi、skw*）、`/sys/class/drm/`、`/proc/asound/cards`
- 本地资料：`D:\02_baidu\KICKPI-K11C（规格书+原理图+机械图）\`、`D:\02_baidu\RK3566-Datasheet\`
