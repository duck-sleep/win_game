先纠正我刚才一个说得太硬的点：原理图标注“B-Key”确实是重大线索，但不能仅凭这一点就 100% 断言 SSD 一定插错。还要以实物插槽的机械缺口、实际 PCB/BOM 为准。
不过 Samsung SM951 和 Kingston A2000 都属于典型 M-Key NVMe SSD；如果实物确实是纯 B-Key 插槽，它们按正常机械防呆本不该完整插入。
下面把这些概念拆开讲。核心是：SSD、M.2、Key、PCIe、NVMe 分别在说不同层面的东西。

先记住一句话

M.2 是外形和插槽规范，Key 是缺口/引脚能力标识，PCIe 是高速通信总线，NVMe 是 SSD 在 PCIe 上使用的通信协议。
它们不是同一个东西。
例如：

Kingston A2000
= SSD（存储设备）
+ M.2 2280（外形尺寸）
+ M-Key（缺口/接口类型）
+ PCIe（通信总线）
+ NVMe（通信协议）

───

1. SSD 是什么

SSD 是固态硬盘，本质上由三部分组成：

主控（Controller） + NAND 闪存颗粒 + 缓存/电源管理

• NAND：真正存数据的闪存；
• 主控：负责读写、坏块管理、磨损均衡、ECC 纠错、垃圾回收等；
• 缓存：加速映射表和突发读写。
SSD 可以用不同外形、不同总线接到主机上：
• 2.5 寸 SATA SSD
• M.2 SATA SSD
• M.2 NVMe SSD
• U.2 / U.3 NVMe SSD
• PCIe 插卡 SSD
所以，“SSD”不等于“NVMe”，也不等于“M.2”。

───

2. M.2：卡的外形和插槽

M.2 可以理解为一种小型扩展卡标准。SSD、Wi-Fi、蓝牙、4G/5G、AI 加速器、GNSS 等设备都可能做成 M.2 卡。
常见尺寸的写法：

2230 = 22 mm 宽、30 mm 长
2242 = 22 mm 宽、42 mm 长
2260 = 22 mm 宽、60 mm 长
2280 = 22 mm 宽、80 mm 长
22110 = 22 mm 宽、110 mm 长

你常见的消费级 SSD 大多是 2280。
注意：

两张卡即使都叫 M.2、都长 2280，也未必能插，也未必能工作。
因为还要看 Key 和实际接出的信号。

───

3. B-Key、M-Key 是什么

Key 就是金手指上的“缺口”

它首先是机械防呆：避免卡插进不兼容的槽。
但它背后也对应一组不同的引脚定义和能力。
常见的三类：

B-Key：缺口靠左侧（从金手指一侧看）
M-Key：缺口靠右侧
B+M-Key：卡上有两个缺口

可以粗略理解：

B-Key 槽 ← 常见于 WWAN / SATA / 部分 PCIe x2 设备
M-Key 槽 ← 最常见于 NVMe SSD，通常 PCIe x4
B+M-Key 卡 ← 兼容性较好，但实际能力取决于卡和槽的布线

常见能力对比

| 类型                               | 常见用途                             | PCIe 通道能力         | 常见 SSD 情况    |
| -------------------------------- | -------------------------------- | ----------------- | ------------ |
| B-Key                            | WWAN、4G/5G 模块、部分 SATA / PCIe SSD | 通常最多 x2           | 较少见 NVMe SSD |
| M-Key                            | NVMe SSD                         | 通常最多 x4           | 最常见          |
| B+M-Key                          | 兼容 B/M 插槽的卡                      | 常见 SATA，或 PCIe x2 | 老款/特定型号较多    |
| A/E-Key                          | Wi-Fi、蓝牙                         | PCIe x1 / USB 等   | 不是常规 SSD 槽   |
| 这里的 x1 / x2 / x4 是 PCIe Lane 数量： |                                  |                   |              |

PCIe x1 = 1 条高速 Lane
PCIe x2 = 2 条高速 Lane
PCIe x4 = 4 条高速 Lane

Lane 越多，理论带宽越大。

4. PCIe：SSD 和主控之间的高速道路

PCIe 是一种高速串行总线。你可以把它理解成主控和设备之间的一条高速公路。

SM8550 / SNM970 主控的 PCIe Root Complex
 │
 │ PCIe 差分高速链路
 │
 M.2 插槽
 │
 NVMe SSD 控制器

PCIe 两端的角色：

• Root Complex / RC：主控侧，例如 SoC 的 PCIe 控制器；
• Endpoint / EP：设备侧，例如 NVMe SSD、网卡、Wi-Fi 芯片。
你们抓的 RC1，就是主控侧的 PCIe1 控制器。
SSD 则应当是它的 Endpoint。

PCIe 的 Lane 是什么

每一条 PCIe Lane 都包含两组高速差分信号：

主控 TX+ / TX- ─────→ SSD RX+ / RX-
主控 RX+ / RX- ←───── SSD TX+ / TX-

所以它是全双工的。

• x1：一条 Lane；
• x2：两条 Lane；
• x4：四条 Lane。
你的原理图里，J901 有：

PCIE1_TX0_P/N、PCIE1_RX0_P/N
PCIE1_TX1_P/N、PCIE1_RX1_P/N

也就是设计上接了 PCIe x2。
这意味着即使它能接 NVMe，最大也只是 x2，不是典型 M-Key SSD 在 PC 上常见的 x4。
但 x2 本身并不妨碍 NVMe 工作：能协商成功即可，只是带宽较低。

5. NVMe：PCIe 上专门给 SSD 用的协议

PCIe 只是传输通道，不限定设备类型。
例如 PCIe 可以连接：

• 显卡；
• 网卡；
• Wi-Fi；
• AI/NPU 加速卡；
• NVMe SSD。
NVMe（Non-Volatile Memory Express）是专门为闪存 SSD 设计的协议，跑在 PCIe 上。
类比：

PCIe = 高速道路
NVMe = SSD 在这条道路上说的语言
SSD = 跑在道路上的货车

NVMe 和 SATA 的区别

| 项目          | SATA SSD  | NVMe SSD       |
| ----------- | --------- | -------------- |
| 常见总线        | SATA      | PCIe           |
| 常见协议        | AHCI      | NVMe           |
| 设计年代        | HDD 时代延续  | 为闪存/并行队列设计     |
| 并发队列        | 较低        | 很高             |
| 常见物理形态      | 2.5 寸、M.2 | M.2、U.2、PCIe 卡 |
| 性能上限        | 较低        |





我把原理图的 09_PCIE 页和主控端连线认真对过了。结论比原先“可能板级硬件问题”更明确：

最关键结论：这是 M.2 B-Key 槽，两块测试 SSD 都是 M-Key NVMe 盘

原理图明确标了：

• 接口：J901 = 91302-32-067R2B
• 设计框图直接写：PCIE M.2 B KEY
• 你的盘：
  • Samsung SM951 MZVPV128HDGM：M-Key NVMe
  • Kingston A2000：M-Key NVMe

B-Key 槽不是通用的 M-Key NVMe SSD 槽。
所以这里极可能不是软件、驱动、甚至不是 SSD 坏了，而是 接口键位/定义就不匹配。

正常情况下，M-Key 单缺口盘不应该能完全插入 B-Key 插座；如果你确实“插进去了”，需要特别检查：

1. 是否并没有插到底；
2. 插座实际装配型号是否与原理图不一致；
3. 是不是用了转接板、或插槽的键位识别看错；
4. 板子 PCB 版本/实际装配与这份 V1 原理图有改版差异。

───

原理图确认到的连接关系

这不是一个“没接 PCIe 的空槽”，它确实接到了主控的 PCIe1：

• SoC PCIE1_TX0/1、PCIE1_RX0/1
→ J901
• SoC PCIE1_REFCLK_P/N
→ J901
• GPIO97 → PCIE_RESET
• GPIO98 → PCIE_CLKREQ
• GPIO99 → PCIE_WAKE
• U901 (UM3204Q) 做了 1.8 V ↔ 3.3 V 的侧带信号电平转换。
• 槽位的 PCIE_3V3 也已画进电路，并有 C903/C904=4.7uF、C901/C902=100nF 去耦。

所以，之前“差分线可能完全没接到 RC1”的猜测，在这份原理图上不成立：它接的是 PCIe1，而且是 x2 通道设计。

但它是给 B-Key 设备准备的。图纸旁边甚至写了：

“不接 WWAN 网卡，可悬空”

这句话进一步说明它的设计意图更偏向 WWAN/蜂窝模块类 B-Key 卡，不是给 M-Key NVMe SSD 的标准插槽。

───

这也解释了 Detect.Quiet

你们抓到的 LTSSM 一直在 Detect.Quiet，代表 RC1 做 receiver detect 时，对端没有呈现有效的 PCIe 终端特征。

若把 M-Key SSD 放进 B-Key 槽（或靠接触不完整“硬插”），就很可能：

• SSD 的 PCIe TX/RX 金手指没有与槽位对应触点正确接通；
• SSD 的 3.3 V、REFCLK、PERST# 也可能不在正确位置或没有可靠接触；
• 主控自然永远检测不到对端终端；
• 于是就固定停在 Detect.Quiet。

而且两块不同 SSD 现象完全一致，正符合“槽/键位/接触定义问题”，不是两块盘同时坏。

───

我对原报告的修正

原报告里这几项排序要调整：

第一优先级：键位错误 / 接口用途错误

不是泛泛的“可能插错槽”，而是原理图已明确写为：

PCIE M.2 B KEY

两块盘都是 M-Key，应先判定为不适配。

第二优先级：实物与原理图是否一致

如果你肉眼确认插座真的是 M-Key，或两块 M-Key SSD 都能完全插入、压平、螺丝固定，那说明存在异常，必须核实：

• 实物 PCB 版本是否真的是 OK700_V1；
• J901 实装料号和原理图的 91302-32-067R2B 是否一致；
• 是否有人改过插座或板版；
• 是否拿错了原理图。

第三优先级：槽位 3.3 V / REFCLK 实测

只有确认“实际是可接 M-Key NVMe 的插座、且针脚定义匹配”后，才继续查供电、时钟和复位。

───

建议的排查顺序

1）先做机械键位确认，不要先改 DTS

关机断电后拍两张清晰照片：

• M.2 插槽正面，重点看塑胶定位凸键的位置；
• SSD 金手指和缺口位置，最好是盘未插入时拍。

判断规则：

• B-Key 槽：只能原生匹配 B-Key 或 B+M Key 卡；
• M-Key 槽：才原生匹配 M-Key NVMe SSD；
• B+M Key SSD 可适配 B 或 M 槽，但通常 PCIe 通道会受限；
• M-Key 单缺口 SSD 不该直接适配 B-Key 槽。

2）核对 J901 实装型号

看连接器本体、BOM 或贴片位号。原理图中 J901 是：

91302-32-067R2B

名字后缀和图纸标注明确指向 B-Key。若实物不同，这是设计资料与实物脱节。

3）若要让当前 B-Key 槽工作

应找一张真正的 B-Key / B+M-Key PCIe SSD 或符合该板 PCIe x2、3.3 V、侧带定义的模块来验证。
但要注意：很多常见 NVMe SSD 都是 M-Key，不能因为“同叫 M.2”就认为可替换。

4）若目标就是使用现有两块 M-Key NVMe SSD

硬件正确方案是：

• 换成 M-Key NVMe 槽；
• 或重新设计/改板，把 PCIe1 的 lane、REFCLK、PERST#、CLKREQ#/WAKE#、3.3 V 接到 M-Key 的标准引脚；
• 不建议靠“直接飞线”做长期方案：PCIe 是高速差分接口，x2 还有信号完整性、阻抗、长度匹配和参考时钟要求。

───

仍值得实测的三个点

如果后面确认实物槽实际支持 M-Key，再按这个顺序量：

1. PCIE_3V3：插盘并触发枚举期间，槽位 3.3 V 是否稳定；
2. REFCLK_P/N：是否有约 100 MHz 差分参考时钟；
3. PCIE_RESET：触发枚举后是否从低电平释放到高电平，并满足 SSD 上电后的时序。

但目前我不建议把精力先花在 DTS、NVMe 驱动或 PERST 时序上。
原理图最像根因的地方就是：J901 被设计为 M.2 B-Key，而你试的是两块 M-Key NVMe。











我觉得ai看的不仔细




你说得对。我前面把“B KEY”这个文字标注看得太重了，结论下早了。我重新按 J901 的实际针脚号和网络核了一遍：这套电路的电气针脚分配，实际上是 M-Key NVMe 的 PCIe x2 接法。

所以现在更合理的判断是：

实物 M-Key 槽是对的，M-Key NVMe SSD 能插入也正常；原理图框图里“PCIE M.2 B KEY”大概率是文字/BOM 标注错误或复制遗留。它不是 SSD 无法识别的根因。

───

为什么能确定它实际按 M-Key 接了

看 09_PCIE 页 J901 的关键信号所落的针脚：

J901 pin 29 / 31  ← PCIE1_TX1_M / PCIE1_TX1_P
J901 pin 35 / 37  ← PCIE1_RX1_M / PCIE1_RX1_P

J901 pin 41 / 43  ← PCIE1_TX0_M / PCIE1_TX0_P
J901 pin 47 / 49  ← PCIE1_RX0_M / PCIE1_RX0_P

J901 pin 53 / 55  ← PCIE1_REFCLK_M / PCIE1_REFCLK_P

J901 pin 50       ← PCIE_RESET
J901 pin 52       ← PCIE_CLKREQ
J901 pin 54       ← PCIE_WAKE

这一组位置就是 M-Key Socket 3 的 PCIe Lane 0 / Lane 1、REFCLK 和侧带信号位置。

尤其是这一段非常关键：

29/31：一条 PCIe TX Lane
35/37：对应 RX Lane
41/43：第二条 PCIe TX Lane
47/49：对应 RX Lane
53/55：100 MHz PCIe REFCLK

这不是随便“接了几根 PCIe 线”，而是严格按 M-Key 的典型 PCIe x2 针脚布局接的。

也就是说，图纸体现的实际设计是：

M-Key M.2 插座
       +
PCIe Gen? x2
       +
NVMe 所需 REFCLK / PERST# / CLKREQ# / WAKE#
       +
3.3V 供电

所以 A2000、SM951 这种 M-Key NVMe SSD 插进去，在硬件定义上是合理的。

───

“B KEY”为什么会出现在图上？

我现在认为有三个可能，按概率排序：

1. 框图/文字标签复制后没改
最可能。整份图里有不少兼容、预留、NC、版本变更痕迹，这种文字标签没同步是常见失误。

2. J901 的料号尾缀 R2B 被误读/沿用成 B-Key 叫法
91302-32-067R2B 的 B 不能直接等价于 “B-Key”；料号后缀经常表示高度、端子规格、包装或版本。

3. 早期版本计划用 B-Key/WWAN，后期实际改成了 M-Key x2，但框图没更新
“不接 WWAN 网卡，可悬空”这句也像是设计沿革留下的说明，不足以推翻实际针脚映射。

所以，以后这里应以：

实物机械缺口 + J901 的针脚网络

为准，不应该以 “B KEY” 这几个字为准。

───

原理图现在给出的真实结论

SSD 识别不了，不是 B-Key/M-Key 不匹配。

从图上看，这个 M-Key 槽确实具备 PCIe x2 NVMe 所需的基本线路：

数据：PCIE1_TX0/1、PCIE1_RX0/1
时钟：PCIE1_REFCLK_P/N
复位：PCIE_RESET
省电侧带：PCIE_CLKREQ、PCIE_WAKE
供电：PCIE_3V3

结合你们的软件测试：

手工触发 RC1 枚举
→ PHY ready
→ 已释放 endpoint reset
→ LTSSM 始终 Detect.Quiet

新的排查重心应该收敛为：

1. SSD 插槽的 3.3V 是否实际到位
2. REFCLK 是否真实输出到 J901
3. PERST# 是否在 SSD 上电稳定后真正释放
4. PCIe TX/RX 差分线是否 PCB 走反、断线、ESD 损坏或装配异常
5. 实际板子是否与原理图一致

───

我认为最可疑的是 3.3 V 供电

重新看第 01 页，PCIE_3V3 不是 PMIC 直接输出，而是来自一颗独立降压：

U103：SK6690DP8
L102：3.3uH
输出网络：PCIE_3V3

它是一个标称 3.3 V / 3 A 的 buck 电源，PCIE_3V3 再去给 J901 的 M.2 插槽供电。

这很重要，因为：

• 软件里看到 pm_humu_l13 仍使能，不等于 J901 真正拿到了 PCIE_3V3；
• M.2 插槽的电源来自这颗外部 DCDC，应该在 J901 供电脚附近直接量；
• 如果 U103 没使能、输出异常、L102 虚焊、保险/磁珠/走线异常，SSD 就是没电；
• SSD 没真正上电时，RC 端非常容易一直是 Detect.Quiet。

原理图里还出现两个特别值得留意的 GPIO 命名：

GPIO186_PCIE_3V3_EN
GPIO141_AFC_PHY_TA_D_MINUS/PCIE_3V3_IN_EN

它们在主控页出现，但 09_PCIE 页没有清晰地把它们直接连到 J901 电源开关。这存在两种可能：

• 名字是历史遗留，实际未参与该 SSD 槽供电；
• 供电使能/控制在原理图表达上有遗漏，或者实物 PCB 与图纸不一致。

这个点值得用万用表先秒杀掉，不必先拿示波器。

───

建议现在按这个顺序排

第一步：直接量 M-Key 槽供电

板子开机、SSD 插着，黑表笔接地，红表笔量 J901 的 3.3V 供电针脚或 PCIE_3V3 去耦电容：

C903 / C904：4.7uF
C901 / C902：100nF

预期：

稳定约 3.3V

结果解释：

0V / 很低           → 先查 U103、EN、L102、PCIE_3V3 路径
只有触发时跳一下     → DCDC 保护、过流、使能时序问题
3.3V 稳定            → 转查 REFCLK / PERST# / 高速链路

这是目前最高优先级。

第二步：看 PERST#（PCIE_RESET）

J901：

pin 50 = PCIE_RESET

原理图路径：

SoC GPIO97
  → U901 电平转换（1.8V ↔ 3.3V）
  → R905 0Ω
  → J901 pin 50

预期时序：

上电初期：低电平（SSD 保持复位）
枚举前后：升高到约 3.3V（释放复位）

注意：原先软件里“PERST 已释放”的结论是在 SoC/GPIO 侧得出的；
还必须确认 J901 pin 50 的物理电平真的跟着到 3.3V。

U901、R905、焊接或 PCB 断线都会造成“软件认为释放了，SSD 脚上却没释放”。

第三步：测 100 MHz REFCLK

J901：

pin 53 = PCIE1_REFCLK_M
pin 55 = PCIE1_REFCLK_P

需要示波器