# 03 SSD 部署分析 —— OK700 板 M.2 NVMe 识别问题排查【问题已解决 ✅】

> 日期：2026-08-25 软件排查 + 原理图核对；08-26 凌晨勘误 §3.5；**08-26 上午双根因闭环、SSD 实测识别成功**；
> **08-27 整包刷机验证通过：开机自动枚举成功，问题闭环（枚举≠挂载，挂载集成见 §10）**
> 环境：OK700_V1 板（SNM970_ZB_491PIN，原理图项目 XY102），Android 15 userdebug（自编译）
> 测试盘：Samsung SM951 128G（MZVPV128HDGM）、Kingston A2000 1TB
>
> **最终结论（两个根因，均已验证）**：
> **根因①（硬件，已被跳线修正）**：原理图 J901 的 4 对 PCIe 差分线 TX/RX 全部交叉接反。
> 硬件同事跳线修正后链路方向已正确。
> **根因②（软件，本次新发现）**：M.2 槽 3.3V 供电使能脚 **GPIO46/VCC5V_EN 从未被固件驱动**——
> U103（SK6690DP8）EN 脚被 R136(100K) 下拉恒低，**槽位一直没电**，SSD 无电自然不响应
> receiver detect，链路训练必失败（跳线修好后仍卡 Detect.Quiet 的真正原因）。
>
> **验证结果（2026-08-26，跳线修正板 + 软件拉高 GPIO46）**：
> ```
> [995.092] PCIe RC1 link initialized            ← 链路 60ms 训练成功
> [995.165] nvme 0001:01:00.0                    ← SM951 完整枚举
> [995.212] nvme0n1: p1                          ← 块设备 + 分区
> ```
> `/dev/block/nvme0n1p1`（ext4，125GB）手动挂载成功，数据完整可读。**硬件跳线 OK、盘 OK，缺的只是供电使能。**
>
> **验证结果（2026-08-27，260827 整包正常开机，零手动操作）**：
> ```
> /sys/block/nvme0n1                            ← 开机自动枚举
> nvme0n1p1：ext4，125,033,816 扇区(119.2G)      ← 分区完整，UUID=a418a8ca-...
> model: SAMSUNG MZVPV128HDGM-00000             ← SM951 128G
> /proc/device-tree/model: KalamaP HDK          ← UEFI 选了主 overlay（带修复）
> ```
> dtbo.img 含 6 处 pcie-slot-3v3-en（主 overlay 3 + gpiotest 3），选哪个条目修复都生效。
> **但枚举 ≠ 挂载**：fstab 无 nvme 条目、vold 无 public 卷，Android 文件管理器暂不可见，见 §10。

---

## 1. 问题现象

M.2 槽插入 NVMe SSD 后：
- `/sys/class/nvme/` 为空，`/dev/block/` 下无 nvme 设备
- 系统只有 UFS 分区（sda~sde，见 log.txt 串口记录）
- dmesg 无任何 nvme / 144d（Samsung）/ 2646（Kingston）设备 ID 痕迹

## 2. 排查过程与证据链（软件侧全部正常）

### 2.1 基础检查（均正常）

| 检查项 | 结果 |
|---|---|
| 内核 NVMe 驱动 | ✅ nvme / nvme_core 模块已加载 |
| PCIe 总线 | ✅ 正常，pcie0 上挂着 WiFi（WCN6855，vendor 17cb） |
| pcie1 控制器设备树节点 | ✅ 存在且未 disabled |
| pcie1 驱动绑定 | ✅ `pci-msm` 已绑定 `/sys/bus/platform/devices/1c08000.qcom,pcie` |
| 热插拔 | ✅ 已重启板子验证，非热插拔问题 |
| PERST 复位脚（gpio398 = TLMM GPIO97，见 §3.5） | ✅ 训练窗口内实测输出高（正确释放复位） |
| 强制 Gen1 速率 | ❌ 仍失败（排除速率协商问题） |
| 板上 PCIe 控制器 | 仅 pcie0 / pcie1 两个（另有 pcie_qtb、EP 模式节点 disabled），不存在枚举错控制器的可能 |

### 2.2 触发手动枚举（关键测试）

这块内核 PCIe 是"按需拉链路"模式：WiFi 驱动请求时才训练 RC0，RC1 因无客户端驱动从未被拉起。
所以插盘后系统毫无反应是**预期行为**，需要手动触发：

```bash
adb root
adb shell setenforce 0                       # SELinux 会拦 debugfs 写
adb shell mkdir -p /sys/kernel/debug
adb shell mount -t debugfs none /sys/kernel/debug   # debugfs 默认未挂载
adb shell "echo 2000 > /sys/bus/platform/devices/1c08000.qcom,pcie/debug/link_check_max_count"
adb shell "echo 1 > /sys/bus/platform/devices/1c08000.qcom,pcie/debug/enumerate"
```

触发后 dmesg：

```
pcie_phy_init: PCIe RC1 PHY is ready!
msm_pcie_enable: Release the reset of endpoint of RC1.
msm_pcie_link_train: PCIe RC1 link initialization failed
```

### 2.3 LTSSM 状态机采样（决定性证据）

将训练轮询次数调到 2000（约 10 秒训练窗口），期间用驱动 debugfs 寄存器接口
（`rc_sel=2` 选 RC1 → `base_sel=4` 选 ELBI → `wr_offset=0x8` → `case=11` 读寄存器）
并行采样 ELBI SYS_STTS 寄存器：

```
10 次采样全部： register 0x400000008 value = 0x1
LTSSM 状态 = (0x1 >> 12) & 0x3f = 0x00 → LTSSM_DETECT_QUIET
链路 up 位（bit10）= 0
```

**LTSSM 全程卡在 Detect.Quiet（链路训练的第 0 步）**——控制器在差分线上做接收端检测
（receiver detect），10 秒内没有一次检测到对端设备。两块不同品牌、不同年代的盘
（SM951 2015 年 / A2000 2019 年）表现完全一致 → **排除盘的问题**。

> LTSSM 枚举值定义见内核 `drivers/pci/controller/pci-msm.c` 的 `enum msm_pcie_ltssm`，
> Detect.Quiet = 0x00。接收端检测都过不去，意味着对端发送端在电气上是"沉默"的：
> 对面没电、没时钟、或者线根本没接到这个控制器。

### 2.4 供电检查（软件侧）

- pcie1 GDSC 电源域（`gcc_pcie_1_gdsc` / `gcc_pcie_1_phy_gdsc`）训练失败后按预期下电
- 3.0V `pm_humu_l13` 保持使能——**原理图核对后确认与 M.2 槽供电无关**（M.2 走 U103，见 §3.3）

### 2.5 设备树的重要发现

HDK overlay（`kalamap-hdk-overlay.dts`）显示 pcie1 的默认用途不是 NVMe：

```dts
&pcie1 {
        qcom,drv-name = "lpass";          /* 分配给 LPASS 子系统 */
        msi-map = <0x0 &gic_its 0x1480 0x1>, <0x100 &gic_its 0x1481 0x1>;
};

&pcie1_rp {
        /* This property is needed only for SoC-to-SoC communication
         * (EP mode support) on HDK platform. */
        mhi_0: qcom,mhi@0 { ... status = "disabled"; ... };
};
```

即：HDK 参考设计的默认软件配置里 pcie1 留给**板对板调试（SoC-to-SoC，EP 模式）**。
而 OK700 板原理图把 pcie1 的 TX/RX/REFCLK/边带全部引到了 J901 M.2 插座（见 §3），
说明板厂的原厂固件里 pcie1 是当通用 RC 用的——**自编译系统沿用了 HDK overlay，与板子实际用途不符**，
开机不会自动枚举 M.2（GPIO 配置本身无误，见 §3.5；须去掉 drv-name，见 §7）。

板上实测设备树同样只有 pcie0 / pcie1 两个 RC 节点：
- `qcom,pcie@1c00000`（pcie0，WiFi 用）
- `qcom,pcie@1c08000`（pcie1，本应给 M.2 用）
- `qcom,pcie@0x40000000`（EP 模式，status=disabled）

---

## 3. 原理图核对结果（决定性证据）

原理图：`D:\win_game_project\01_资料\OK700_V1 原理图.pdf`
- 第 9 页（09_PCIE）：J901 M.2 插座（91302-32-067R2B）、U901 电平转换、ESD 防护
- 第 2 页：SoC（SNM970_ZB_491PIN）侧 PCIE1 信号引脚

### 3.1 J901 差分对接线 vs M.2 Key M 标准 —— TX/RX 全部交叉接反

| J901 引脚 | 板上网络（SoC 侧） | M.2 Key M 标准定义（主机视角） | 判定 |
|---|---|---|---|
| 29 / 31 | PCIE1_TX1_M / **PCIE1_TX1_P**（SoC 发送 lane1） | PERn1 / PERp1 —— 主机**接收** lane1（模块的发送脚） | ✗ 接反 |
| 35 / 37 | PCIE1_RX1_M / PCIE1_RX1_P（SoC 接收 lane1） | PETn1 / PETp1 —— 主机**发送** lane1（模块的接收脚） | ✗ 接反 |
| 41 / 43 | PCIE1_TX0_M / PCIE1_TX0_P（SoC 发送 lane0） | PERn0 / PERp0 —— 主机**接收** lane0 | ✗ 接反 |
| 47 / 49 | PCIE1_RX0_M / PCIE1_RX0_P（SoC 接收 lane0） | PETn0 / PETp0 —— 主机**发送** lane0 | ✗ 接反 |
| 53 / 55 | PCIE1_REFCLK_M / PCIE1_REFCLK_P | REFCLKn / REFCLKp（主机提供给模块的 100MHz） | ✓ |
| 50 | PCIE_RESET | PERST#（主机→模块复位） | ✓ |
| 52 | PCIE_CLKREQ | CLKREQ#（模块→主机） | ✓ |
| 54 | PCIE_WAKE | PEWAKE#（模块→主机） | ✓ |
| 2/4、70/72/74（及 12~18） | PCIE_3V3 | +3.3V 主电源 | ✓ |

SoC 侧对应关系（第 2 页逐脚复核）：TX0=球 434/433、TX1=球 55/56、RX1=球 57/60、RX0=球 62/59、REFCLK=球 58/61。
**关键证据：SoC 符号引脚名与网络名逐一相同**——名为 PCIE1_TX1_M 的球，所接网络就叫 PCIE1_TX1_M，
不存在"网络按模块视角交叉命名、实际接线其实正确"的可能：SoC 发送端确凿落在 J901 的主机接收脚位上。
另查全图共 7 处"v1.02变更"标记（页 2 的 GPIO56/GPIO58/GPIO199/GPIO47 区域及页 3 各一处），
均不在 PCIE1 引脚或 J901 区域——交叉走线属初版设计，并非后期改版引入。

**标准依据（三个独立来源交叉验证，结论一致）**：
- congatec AN43《M.2 Pinout Descriptions and Reference Designs》Key M 表：
  https://wiki.congatec.com/wiki/M.2_Pinout_Descriptions_and_Reference_Designs_(AN43)
  其设计注记明确写道："If the M.2 socket is used for a PCIe based storage device,
  **pin 43 must be connected to the positive signal of the differential pair used for PCIe Rx**"——
  而 43 脚标准名为 PERp0，即 **PER 脚位 = 主机 PCIe RX 的落点**
- Supermicro SYS-422GL-NR 手册 M-Key x4 引脚表（47=PETn0、49=PETp0、50=PERST#、52=CLKREQ#、53/55=REFCLKn/p）
- Swissbit N3202（M.2 NVMe 模块）数据手册：模块 11 脚 = PERn3 = 模块 PCIe RX 输入
  → 模块接收脚位于 11/13、23/25、35/37、47/49；模块发送脚位于 5/7、17/19、**29/31、41/43**

**易踩的命名陷阱（本次设计错误的根源）**：M.2 插槽引脚名里的 PET（"Transmit"）/
PER（"Receive"）与模块手册里的 PET/PER **同名异义**：
- 插槽/主机侧表格：PET = **主机发送**的落点（=模块的接收脚），PER = 主机接收的落点（=模块的发送脚）
- 模块侧手册：PET = 模块发送，PER = 模块接收

OK700 的设计者显然按"TX 对 TX"的字面匹配接线：把 SoC 的 PCIE1_TX 接到了模块的发送脚位
（29/31、41/43，即主机侧表格中标 PER 的位置）、PCIE1_RX 接到了模块的接收脚位
（35/37、47/49，主机侧标 PET 的位置）——主机的发送端与模块的发送端直接对撞，
方向恰好全部接反。这与 UART 收发交叉接反是同一类错误。

### 3.2 为什么完全解释 Detect.Quiet

PCIe 链路训练第一步是接收端检测：主机在自己的 TX 差分线上发检测脉冲，
检测对端（模块的 RX 输入）是否呈现规定的终结电阻（Z_RXIDLE）。
- 本板 SoC 的 TX 接到了模块的**发送**脚（29/31、41/43）——发送驱动器在空闲态不呈现可检测的终结电阻，
  接收端检测永远失败；
- 同时模块的接收脚（35/37、47/49）接到了 SoC 的 RX 输入，没有任何设备向这些线发检测脉冲；
- 结果：双方 LTSSM 永远停在 Detect.Quiet（0x00），与 §2.3 的 10 次采样值完全一致。
- 两块不同年代/品牌的盘症状一致，也印证这是板级共性问题，不是盘的问题。

### 3.3 供电电路（电路设计正确，但使能脚 GPIO46 固件从未驱动 → 根因②）

- U103（SK6690DP8，降压，VOUT=3.3V/3A）→ L102（3.3µH）→ **PCIE_3V3** → J901 的 2/4、70/72/74 脚；
  C903/C904（4.7µF）储能；原理图注记"兼SOC侧管控电量"
- 使能链：**GPIO46 / VCC5V_EN** → R135（0Ω）→ U103 EN 脚，R136（100K）下拉（默认关断）
- **同一网络还使能 U104**（TPS61023，VOUT=5V/1.5A）→ L103 → VCC_5V（USB OTG 5V 供电），
  EN 经 R143（0Ω）接 GPIO46，R145（100K）下拉——即 GPIO46 是"整机 5V/PCIe 3.3V"总使能

**实机验证（2026-08-26）**：
- 拉高前：`gpio46 : in low func0 2mA pull down`（无人驱动、下拉恒低）→ U103/U104 全关 → **槽位无电**
- 拉高后：`gpio46 : out high` → U103 输出 PCIE_3V3 → 链路 60ms 训练成功、SM951 完整枚举

**为什么原厂固件能用**：板厂 BSP 会驱动 GPIO46（设计注记"兼SOC侧管控电量"即此意图）；
自编译系统沿用 HDK overlay，DT 里根本没有这个 GPIO 的任何配置 → 上电后悬空被下拉 → 槽位永远没电。
~~GPIO46 与整机 5V 主电源使能同网络——板上电即应输出 3.3V，供电大概率正常~~（此旧推断错误，已纠正）
- 之前存疑的 PMIC 轨 `pm_humu_l13` 与 M.2 供电无关，已排除

### 3.4 REFCLK（位置正确，SoC 输出方向待实测）

SoC 的 PCIE1_REFCLK（球 58/61）直连 J901 的 53/55 脚（标准 REFCLKn/REFCLKp 位置），
途中疑似串 C901/C902（100nF，交流耦合）。

注意：pcie1 的默认软件配置是 EP 模式（SoC 收时钟）；作 RC 挂 NVMe 时 SoC 需在 REFCLK 球上
**输出** 100MHz 给模块。板上 GPIO 命名带 NTN/SDX 字样（NTN_PCIE_1_RESET_N、PCIE1_SDX_CLKREQA_N），
说明该 M.2 槽参考了高通 NTN/SDX 模组的参考设计，而高通原设计 pcie1 正是 RC 直挂 M.2——
SoC 输出时钟的路径应该是通的。可用示波器实测 pin 53/55 确认（见 §6）。

### 3.5 边带信号：电路与设备树完全匹配（早前"GPIO 不匹配"的推断已证伪）

板上实际电路（边带均经 U901 UM3204Q 1.8V↔3.3V 电平转换，ESDSU5V0A1×10 + ESD5451N×4 防护）：

| 信号 | M.2 脚 | 板上实际驱动（SoC TLMM） | 设备树原文（板上 /proc/device-tree 实测） | 匹配？ |
|---|---|---|---|---|
| PERST# | 50 | GPIO97（NTN_PCIE_1_RESET_N） | `perst-gpio = <&tlmm 97 0>` | ✓ |
| CLKREQ# | 52 | GPIO98（PCIE1_SDX_CLKREQA_N） | pinctrl 复用 func1（gpio98: in high func1） | ✓ |
| PEWAKE# | 54 | GPIO99（PCIE1_WAKE_N） | `wake-gpio = <&tlmm 99 0>` | ✓ |
| LED1# | 10 | GPIO163（PCIE_LED1#） | — | — |

**勘误（2026-08-25 深夜复核）**：本文档早期版本曾断言"DT 用 gpio398/400 是 PMIC 域 GPIO、与板上
TLMM GPIO97/99 不符，导致 PERST# 恒为有效"。经实机验证，该推断**错误**，已撤回：

1. **gpiochip 映射**（`/sys/kernel/debug/gpio` 实测）：
   `gpiochip0: GPIOs 301-511, parent: platform/f000000.pinctrl`——即 TLMM 的 Linux 全局编号 base=301。
   因此 **gpio398 = TLMM GPIO97、gpio400 = TLMM GPIO99**（398-97=301、400-99=301，偏移一致）。
   日志里驱动打印的 gpio398/400 只是全局编号，并非接到了别的控制器。
2. **设备树原文**（`/proc/device-tree/soc/qcom,pcie@1c08000/`）：
   - `perst-gpio` 字节串 `0000007e 00000061 00000000` → phandle 0x7e + GPIO 0x61(97)
   - `wake-gpio` 字节串 `0000007e 00000063 00000000` → phandle 0x7e + GPIO 0x63(99)
   - phandle 0x7e 经 `__symbols__` 解析 = `/soc/pinctrl@f000000` = **tlmm** ✓
3. **电平实测**（边采样 gpio97 边触发枚举，perst_watch.sh）：
   训练 11 秒窗口内 `gpio97: out high`（PERST# 释放），失败后回到 `out low`，
   与 dmesg "Release the reset of endpoint of RC1"（252.1s）→ "Assert the reset"（263.2s）完全对应。

即：PERST 一直是被正确驱动和释放的，SSD 在训练窗口内并未被按在复位里。
Detect.Quiet 的解释**完全归于 §3.1 的 TX/RX 交叉**，不存在第二个独立原因。
（SoC 侧 1.8V → U901 → J901 pin50 的 3.3V 链路仍建议硬件实测一次，但软件侧已无嫌疑。）

### 3.6 其他核对项

- CONFIG0/CONFIG2/CONFIG3 接地、CONFIG1（PEDET，69 脚）悬空——PCIe 卡本来就不接 PEDET，
  本板也没有 SATA/PCIe 自动切换电路，不影响使用；但 AN43 注记建议载板对 PEDET 加上拉，改版时可顺带补上
- SMB_CLK / SMB_DATA / ALERT#（40/42/44 脚），R908~R910（10K）上拉到 1.8V，符合规范
- 未在 J901 页找到 SoC TX 侧的交流耦合电容（C901/C902 疑似挂在 REFCLK 上）——
  PCIe 规范要求 TX 线串 75~200nF，改版时建议顺带核实/补上

---

## 4. 最终结论

1. **根因①（硬件，已修正）**：OK700_V1 原理图 J901 M.2 插座的 PCIe 差分对 TX/RX 全部交叉接反。
   SoC 的 TX 落在模块的发送脚位（29/31、41/43），SoC 的 RX 落在模块的接收脚位（35/37、47/49）。
   接收端检测永远失败，LTSSM 卡 Detect.Quiet。**硬件同事已跳线修正，且经 08-26 实测验证修正有效**
   （供电拉高后链路 60ms 训练成功，证明跳线后的差分方向正确）。
2. **根因②（软件，08-26 新发现）**：M.2 槽 3.3V 供电（U103）与整机 5V（U104）共用使能脚
   **GPIO46/VCC5V_EN**，默认 100K 下拉关断，必须由 SoC 拉高。自编译固件（HDK overlay）里
   该 GPIO 无任何配置，上电后恒低 → **槽位一直无电** → 跳线修正后链路训练依然失败的真正原因。
   软件拉高 GPIO46 后 SSD 立即完整识别（nvme0n1 + nvme0n1p1，ext4 挂载数据可读）。
3. **附带问题（软件）**：pcie1 被 `qcom,drv-name="lpass"` 占用，开机不自动枚举（手动触发可绕过）。
   去掉后开机即可自动拉起链路。
4. PERST/WAKE GPIO 配置正确（§3.5 实测），无需改动。软件链路（nvme 驱动、控制器、PHY）全部正常。

> 复盘：Detect.Quiet 在本板上其实由**两个独立原因叠加**造成——差分方向反（硬件）+ 槽位无电（软件）。
> 前期只修硬件时症状不变，差点误导为"跳线无效"；实际是供电这层从未被剥开。
> 教训：receiver detect 失败的第一性排查顺序应是 ①对端供电 ②线路连通 ③方向/极性，缺一不可。

## 5. 修复方案评估（更新）

| 方案 | 状态 | 说明 |
|---|---|---|
| 硬件跳线修正 TX/RX | ✅ 已完成且验证有效 | 链路 60ms 训练成功即证明 |
| PCB 改版 | 建议保留 | 4 对差分线按标准交换：SoC TX0→47/49、RX0→41/43、TX1→35/37、RX1→29/31；顺带核实 TX 交流耦合电容、PEDET 上拉（§3.6、§9） |
| **软件拉高 GPIO46（临时）** | ✅ 本次验证用 | sysfs 导出 gpio347（=TLMM46，base 301）拉高即上电，重启后失效，见 §8 |
| **软件拉高 GPIO46（永久）** | ✅ 已完成并验证 | DT gpio-hog 已进 260827 固件，开机自动上电（§7） |
| 去掉 `qcom,drv-name="lpass"` | ✅ 已完成并验证 | boot-option=0x0 已进 260827 固件，开机自动枚举（§7） |
| fstab/vold 自动挂载 | ⭐ 下一步 | 枚举已通；Android 文件管理器要看到还需挂载集成，见 §10 |

## 6. 上板实测清单（已大部分由软件侧闭环，硬件侧仅剩补证）

1. ~~J901 pin 2/4 对 GND 应为 3.3V~~ → **已由软件侧闭环**：GPIO46 拉高后链路训练成功即证明
   PCIE_3V3 正常输出（无电链路不可能训练成功）。如需补证可在 GPIO46 高电平时量 pin 2/4。
2. J901 pin 50（PERST#）：SoC 侧 gpio97 已实测训练窗口内 out high；实物量测属低优先级补证
3. ~~J901 pin 53/55 REFCLK~~ → **已由软件侧闭环**：链路训练成功 + NVMe 完整枚举说明参考时钟正常
4. ~~示波器观察差分线~~ → 已不需要（链路已通）

## 7. 后续可做的事（软件侧两项 DT 修改，做完开机即自动识别 SSD）

**修改①：tlmm 节点加 GPIO46 hog（开机自动上电）**

在 `pinctrl@f000000`（tlmm）节点下追加（DTS 源码，位置参考 kalama-pinctrl.dtsi）：

```dts
pcie_slot_3v3_en {
    gpio-hog;
    gpios = <46 0>;
    output-high;
    line-name = "pcie-slot-3v3-en";
};
```

> 注：GPIO46 同时使能 U104（VCC_5V，USB OTG 5V）——拉高后 OTG 5V 也会常开。
> 板厂原厂固件即如此工作（SSD + OTG 均正常），无副作用；若想精细控制可改为
> regulator（fixed-regulator + enable-gpio）挂到 pcie1 的电源域，按需使能。
> 若 GPIO46 已被其他节点占用需先解绑（实测当前固件中该脚完全未被申请）。

**修改②：pcie1 的 boot-option 清零（开机自动枚举）**

实际落地的改法（`kalamap-hdk-overlay.dts` 顶层 `&pcie1` 块，已实施并编译验证）：

```dts
&pcie1 {
    qcom,boot-option = <0x0>;
    msi-map = <0x0 &gic_its 0x1480 0x1>, <0x100 &gic_its 0x1481 0x1>;
};
```

**关键补充（08-26 定稿验证时新发现）**：pcie1 的 boot-option 有**三层来源**，最终生效值按
fragment 应用顺序（后覆盖先）决定：

| 来源 | 值 | 编译后 fragment |
|---|---|---|
| 基础 dtsi（kalama-pcie.dtsi） | `<0x1>`（NO_PROBE_ENUMERATION） | 基础 DTB，被 overlay 覆盖 |
| kalamap-hdk.dtsi 第 33 行（overlay include 进来） | **`<0x2>`**（NO_WAKE_ENUMERATION） | fragment@28（先应用） |
| overlay 顶层 `&pcie1`（本次新增） | **`<0x0>`** | fragment@34（后应用，**最终生效**） |

即**修复前板上实际生效值是 0x2，不是 0x1**——BIT(0) 本来就是清的，probe 开机其实尝试过枚举
（因槽位无电而失败）；真正被挡住的是 BIT(1)：唤醒触发枚举。修复后 0x0 两位全清：
probe 枚举（配合 GPIO46 hog 供电应成功）+ WAKE 触发枚举（兜底：若开机枚举失败，
SSD 拉 PEWAKE# 还能再触发一次）。`__fixups__` 反编译实测确认 fragment@28/@34 均指向 pcie1。

> 注：基础 dtsi 与 kalamap-hdk.dtsi 残留的 `qcom,drv-name="lpass"` 无需处理——
> dtc overlay 模式下 `/delete-property/` 编译成空指令（已实测），且该属性只注册
> LPASS SSR notifier 回调，不拦截 boot 枚举，残留无害。
> PERST/WAKE GPIO **无需改动**——板上 DT 已是 `perst-gpio=<&tlmm 97>`、`wake-gpio=<&tlmm 99>`，与电路一致（§3.5 实测）。

**修改已全部就绪并通过编译验证（2026-08-26）**：
- 源文件：VM `~/Desktop/10_code/LA.VENDOR.15.4.3-irix/kernel_platform/qcom/proprietary/devicetree/qcom/kalamap-hdk-overlay.dts`（git diff 共 17 行）
- 语法：cpp 预处理 + dtc 编译通过，无错误
- dtbo 反编译验证：`gpios = <0x2e 0x00>`（46）+ output-high ✓、`boot-option = <0x00>` ✓
- 构建链路：userdebug → VARIANT=consolidate → `KALAMA_BOARDS` 列表含 `kalamap-hdk-overlay.dtbo`，
  `build_kernel` 在 inc 模式下照常执行，产物经 dtbo.img 打进刷机包

两项改完重编 DTBO 刷机后，开机应自动出现 `/dev/block/nvme0n1*`；届时再按需配 fstab/vold 自动挂载。

### ⚠️ 增量编译大坑：kp-dtbs 过期（2026-08-26 实测踩中）

> **补充坑 1b（2026-09-05 实测踩中）：改内核 defconfig（如 XPAD_FF）+ 增量编译同样不生效。**
> `build_kernel` 每次都跑，但内核 build.sh 对已有 out 目录（`out/msm-kernel-kalama-consolidate/-gki`）
> 走缓存，旧 `.config` 不重生成——板上 `/proc/version` 停在旧时间戳即中招。
> **修法**：`rm -rf out/msm-kernel-kalama-consolidate out/msm-kernel-kalama-gki` + 删
> `device/qcom/kalama-kernel/Image`，再增量编译。**任何内核源码/defconfig/DT/ko 改动，增量前都要清这套。**

**症状**：改了 overlay DTS，增量编译出的 dtbo.img 里却是旧值（板上 `boot-option` 仍为 0x2、
无 GPIO46 hog），烧录后验证失败。

**根因**：产物交接链 `内核 dist/ → device/qcom/kalama-kernel/kp-dtbs/ → dtbo.img` 中，
`prepare_vendor.sh` 的"要不要重拷"判断**只看两个条件**：`kalama-kernel/Image` 是否存在、
`build.config` 是否变化——**完全不看 dtbo/ko 的时间戳**。首次全编（8-20）铺了旧 kp-dtbs 后，
后续所有增量编译内核虽然正确重编了 overlay（dist 里是新的），但交接拷贝被跳过，
dtbo.img 一直用 8-20 的旧文件打包。

**修复**：删掉 `device/qcom/kalama-kernel/Image` 强制触发 COPY_NEEDED（dist/Image 还在，
**不会**引发内核重编，prepare_vendor 会秒级重铺 kp-dtbs + .ko + Image）：

```bash
cd ~/Desktop/10_code/LA.VENDOR.15.4.3-irix
rm device/qcom/kalama-kernel/Image      # 强制 prepare_vendor 刷新 kp-dtbs
./SNM970_A15_build.sh userdebug kalama 01 2>&1 | tee build.log
```

**以后任何内核 DT/ko 改动 + 增量编译，都要先删这个 Image**（或验证 kp-dtbs 时间戳已更新）。
**编译后烧录前先验货**（VM 上）：
```bash
python3 /tmp/extract_dtbo.py | grep -i kalamap-hdk
# 修复后应看到 gpio46hog=True 且 boot-option=['qcom,boot-option = <0x00>;']
```

### ⚠️ 第二个坑：gpiotest overlay 抢占 DTBO 选择（2026-08-26 晚发现）

**现象**：8-26 20:38 的包验货时发现 dtbo.img 里 68 个条目中，与我们板匹配的有两个——
表格条目[53]（`kalamap-hdk-overlay-gpiotest-*-vidc-iot`，旧内容）和条目[56]
（`kalamap-hdk-overlay-*-vidc-iot`，我们的新内容），**两者 msm-id/board-id 完全相同**
（603 v2.0 / 0x1001f subtype 0）。

**根因**：同事 huangxiaohui 8-25 合入的 `kalamap-hdk-overlay-gpiotest.dts`
（TaskID 86215，"gpio full pin test"，实际只有 13 行 = kalamap-hdk.dtsi + 根属性）
声明的 board-id 与 kalamap-hdk-overlay.dts 相同；字母序 g<h 使它在 dtbo 表中排在前面。
UEFI 选择逻辑（`edk2/QcomModulePkg/Library/BootLib/LocateDeviceTree.c` 的
`GetBoardDtb` → `ReadDtbFindMatch`）：**完全平局时先到的条目赢** → gpiotest 会赢，
我们的修复不会生效。（gpiotest 的 `qcom,oem-id=<3>` 按 `OEM_ID_MASK=0xff000000`
解析 variant=0，不构成区分。）

**修复**：把同样的两处修改（GPIO46 hog + `boot-option=<0x0>`）**镜像追加到
`kalamap-hdk-overlay-gpiotest.dts`**——无论 UEFI 选哪个条目，修复都生效。
编译验证通过（反编译：0x2 基础值 + `gpios=<0x2e>` hog + `boot-option=<0x00>` fragment）。
提交 PR 时需说明：gpiotest 与 hdk-overlay 声明相同 board-id 且在 dtbo 表中排序靠前，
M.2 修复必须同时存在于两个 overlay（建议与 huangxiaohui 同步）。

**验证附加项**（刷机后）：`adb shell cat /proc/device-tree/model`——
"KalamaP HDK gpiotest" = UEFI 选了 gpiotest 条目；"KalamaP HDK" = 选了 hdk-overlay 条目。
两者现在都带修复，都能出 nvme0。


- **验证盘好坏**：SM951 已完整识别（ext4 数据可读）✅；Kingston A2000 可再插一次复验（预期同样正常）
- **向板厂反馈**：TX/RX 交叉为初版设计错误（§3.1），建议下版修正（§9 附改版对照表）

## 8. 复现命令速查

```bash
# ===== 临时方案（当前固件，每次重启后执行；本次验证成功的完整序列）=====
adb root; adb shell setenforce 0
adb shell mount -t debugfs none /sys/kernel/debug

# ① 拉高 GPIO46 给 M.2 槽上电（347 = 301 + 46，TLMM gpiochip base=301）
adb shell "echo 347 > /sys/class/gpio/export"
adb shell "echo out > /sys/class/gpio/gpio347/direction"
adb shell "echo 1 > /sys/class/gpio/gpio347/value"
adb shell sleep 1.5                                    # 等电源稳定

# ② 触发 RC1 枚举（去掉 drv-name 前需要手动触发）
adb shell "echo 2000 > /sys/bus/platform/devices/1c08000.qcom,pcie/debug/link_check_max_count"
adb shell "echo 1 > /sys/bus/platform/devices/1c08000.qcom,pcie/debug/enumerate"
adb shell dmesg | grep -iE "RC1|nvme"                  # 应见 link initialized + nvme0n1: p1

# ③ 手动挂载（ext4 示例）
adb shell "mkdir -p /mnt/ssd && mount -t ext4 /dev/block/nvme0n1p1 /mnt/ssd && ls /mnt/ssd"

# ===== 排查期用过的诊断命令 =====
adb shell cat /sys/kernel/debug/gpio | grep -E ' gpio46 | gpio9[789] '   # 供电使能/PERST/CLKREQ
adb shell ls /sys/bus/pci/devices/                    # 0001:01:00.0 = M.2 SSD；0000:01:00.0 = WiFi
adb shell "echo 2 > /sys/kernel/debug/pci-msm/rc_sel"        # 选 RC1
adb shell "echo 4 > /sys/kernel/debug/pci-msm/base_sel"      # 选 ELBI
adb shell "echo 0x8 > /sys/kernel/debug/pci-msm/wr_offset"   # SYS_STTS 寄存器
adb shell "echo 11 > /sys/kernel/debug/pci-msm/case"         # 读寄存器
adb shell dmesg | grep "msm_pcie_access_reg" | tail -3       # value: 0x1 = Detect.Quiet
```

> 注：排查期间曾误触发 debugfs 用例 17（断言 PERST）和 12（读寄存器），
> 均只作用于 RC 控制器自身，已用用例 18 恢复 PERST 释放，不影响 SSD 数据。
>
> 原理图分析用的提取脚本与截图在 `C:\platform-tools\`（j901_exact.py、soc_page_verify.py、
> vcc5v_verify.py、page9_layout.txt、sch_j901_full.png、sch_j901_left.png 等）；
> §3.5 勘误的实测脚本与数据：perst_watch.sh（gpio97 采样实验）、gpio_dump.txt（gpiochip 快照）；
> 根因②验证脚本：power_test.sh（GPIO46 拉高 + 枚举 + 挂载一条龙）。

---

## 9. 附：M.2 Key M（Socket 3）标准引脚表（congatec AN43，主机视角）

> 来源：https://wiki.congatec.com/wiki/M.2_Pinout_Descriptions_and_Reference_Designs_(AN43)
> 奇数脚在插座底面、偶数脚在顶面；PET = 主机发送的落点（=模块的接收脚），PER = 主机接收的落点（=模块的发送脚）。
> AN43 设计注记：PCIe 存储用途时 "pin 43 must be connected to the positive signal of the differential pair
> used for PCIe Rx"（43 脚 = PERp0 = 主机 RX 落点）；且 PCIe 卡不接 PEDET，载板需对 69 脚加上拉。

| 奇数脚(底) | 信号 | 偶数脚(顶) | 信号 |
|---|---|---|---|
| 1 | GND | 2 | 3.3V |
| 3 | GND | 4 | 3.3V |
| 5 / 7 | PERn3 / PERp3（主机收 lane3） | 6 / 8 | NC |
| 9 | GND | 10 | DAS/DSS/LED_1# |
| 11 / 13 | PETn3 / PETp3（主机发 lane3） | 12 / 14 | 3.3V |
| 15 | GND | 16 | 3.3V |
| 17 / 19 | PERn2 / PERp2（主机收 lane2） | 18 | 3.3V |
| 21 | GND | 20 / 22 | NC |
| 23 / 25 | PETn2 / PETp2（主机发 lane2） | 24 / 26 | NC |
| 27 | GND | 28 / 30 | NC |
| **29 / 31** | **PERn1 / PERp1（主机收 lane1）← OK700 错接 SoC TX1** | 32 / 34 | NC |
| 33 | GND | 36 | NC |
| **35 / 37** | **PETn1 / PETp1（主机发 lane1）← OK700 错接 SoC RX1** | 38 | DEVSLP |
| 39 | GND | 40 | SMB_CLK |
| **41 / 43** | **PERn0 / PERp0（主机收 lane0）← OK700 错接 SoC TX0** | 42 | SMB_DATA |
| 45 | GND | 44 | ALERT# |
| **47 / 49** | **PETn0 / PETp0（主机发 lane0）← OK700 错接 SoC RX0** | 46 / 48 | NC |
| 51 | GND | **50** | **PERST#（主机→模块复位）** |
| **53 / 55** | **REFCLKn / REFCLKp（主机输出的 100MHz 差分时钟）** | **52** | **CLKREQ#（模块→主机）** |
| 57 | GND | 54 | **PEWAKE#（模块→主机）** |
| 59 ~ 66 附近 | M 键缺口区（无引脚） | 56 / 58 | NC |
| 67 | NC | 60 ~ 66 附近 | M 键缺口区 |
| 69 | PEDET（CONFIG1，需上拉） | 68 | SUSCLK |
| 71 / 73 / 75 | GND | 70 / 72 / 74 | 3.3V |

改版对照速查（把 4 对差分线按下表交换，其余不动）：

| SoC 信号 | 现在错接的脚位 | 应接脚位 |
|---|---|---|
| PCIE1_TX1_M/P | 29 / 31 | **35 / 37** |
| PCIE1_RX1_M/P | 35 / 37 | **29 / 31** |
| PCIE1_TX0_M/P | 41 / 43 | **47 / 49** |
| PCIE1_RX0_M/P | 47 / 49 | **41 / 43** |

---

## 10. 2026-08-27 整包刷机验证：枚举成功，挂载待集成

### 10.1 验证结果（260827 包，正常开机，零手动操作）

| 检查项 | 结果 |
|---|---|
| 开机自动枚举 | ✅ `/sys/block/nvme0n1` 直接存在，无需 debugfs 触发 |
| 分区 | ✅ nvme0n1p1，125,033,816 扇区 ≈ 119.2GB，ext4，UUID=`a418a8ca-5d49-4f1b-91d7-776e29a1d159` |
| SSD 型号 | ✅ SAMSUNG MZVPV128HDGM-00000（SM951 128G） |
| UEFI 选择的 overlay | ✅ `/proc/device-tree/model` = "KalamaP HDK"（主 overlay，带修复） |
| dtbo.img 修复完整性 | ✅ pcie-slot-3v3-en 共 6 处（主 overlay 3 + gpiotest 3），UEFI 选哪个条目都生效 |

至此：**根因①（硬件跳线）+ 根因②（GPIO46 供电）+ boot-option + gpiotest 抢占，四项全部闭环**，
开机 20 秒左右 nvme0n1 就在块设备列表里。

### 10.2 挂载验证成功（2026-08-27 晚，免编译运行时验证）

**方案 A（vold 便携存储）已全链路验证通过**，全程无需编译：

```bash
# 1. 关 verity（userdebug 固件允许）
adb root && adb disable-verity && adb reboot
# 2. 重启后 remount /vendor 为可写，追加 fstab 条目
adb remount
echo '/devices/platform/soc/1c08000.qcom,pcie/pci*/*/*/nvme/*/* /storage/ssd vfat nosuid,nodev wait,voldmanaged=ssd:auto' >> /vendor/etc/fstab.qcom
# 3. 重启让 vold 认领磁盘（此时盘还是旧 MBR 分区表 → vold 不认，需格式化）
adb reboot
# 4. vold 接管后格式化为便携存储（重建 GPT + exfat，破坏性操作）
sm list-disks                  # 看到 disk:259,64
sm partition disk:259,64 public
# 5. 再次重启 → 开机自动挂载
```

**最终验证结果（重启后，零手动操作）**：

| 检查项 | 结果 |
|---|---|
| 开机自动挂载 | ✅ `sm list-volumes` → `public:259,65 mounted 6BDF-E02B` |
| 文件系统 | ✅ exfat，119G 可用，支持 >4GB 单文件（游戏镜像） |
| 文件管理器可见 | ✅ DocumentsProvider 根列表：`root_id=6BDF-E02B, title=android`（带 SUPPORTS_CREATE 写标志） |
| 浏览通道 | ✅ SAF children 查询能列出盘内文件 |
| 直达路径 | ⚠️ `/storage/6BDF-E02B` 不存在（mountFlags=0 非 visible 挂载），见下 |

### 10.3 遗留问题与注意事项

1. **非 visible 挂载**：本机 SMS 给 public 卷的 mountFlags=0，vold 只挂 raw 层
   （/mnt/media_rw/6BDF-E02B），不建 /storage/<uuid> 直达视图。
   - 文件管理器（DocumentsUI，本机已装 com.android.documentsui）走 SAF 通道，**不受影响**；
   - 但"直接路径型"应用（模拟器前端扫 /storage/<uuid> 目录）看不到盘。
   - 如需直达路径，后续可查 SMS/vold 是否被厂商定制隐藏外置存储。
2. **原盘数据已清**：SSD 原有一套 Armbian Linux rootfs（xfding 装的，31G 数据），
   经用户确认"闹着玩的随便格"后已格式化为 exfat 便携存储。
3. **`sm mount` 手动挂载坑**：格式化后立即手动 `sm mount` 会被状态机拒绝
   （"mount requires state unmounted or unmountable"，卷还在 checking），
   重启走系统自动挂载流程即可，无需手动干预。
4. **首次格式化必须做**：vold 只认 GPT 分区表（旧 MBR → "unknown partition table" 放弃）。
   量产机用户插的新盘若带 MBR，文件管理器会引导格式化，属正常流程。

### 10.4 量产化（已落源码，待编译）

源码 fstab 位置：`device/qcom/kalama/fstab.qcom`（VM 内 LA.VENDOR.15.4.3-irix），
已追加与设备端验证完全相同的条目：

```
/devices/platform/soc/1c08000.qcom,pcie/pci*/*/*/nvme/*/* /storage/ssd vfat nosuid,nodev wait,voldmanaged=ssd:auto
```

下次编译该条目自动进 vendor.img；新机首次开机 vold 认领 SSD 后
在文件管理器里格式化一次即为最终用户形态。
