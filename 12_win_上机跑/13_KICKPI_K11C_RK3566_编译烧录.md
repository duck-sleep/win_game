# 13 — KICKPI K11C（RK3566）：从干净系统到固件上板

> 2026-10-15 实跑留档（本文合并了原 13 指南 + 原 14 回归记录，旧的 13/14 内容以本文为准）。
> 板子 **K11C V1.2，无屏走 HDMI**；主线 **linux-kernel-6.1**（5.10 线官方已停维护）。
> 编译机：`rk-vm`（`rk@rk-vmachine`，Ubuntu 22.04.5，VMware NAT `192.168.234.141`）。
>
> **结果**：一条 `./build.sh` 出 `rockdev/update.img` = 7,172,475,466 B，md5 `c9d895169b7d886f86daea13742f2d0b`，
> 已烧进板子，串口登录，`uname -v` = `#2 SMP Thu Oct 15 14:18:30 EDT 2026` —— 跑的就是我们编的内核。

## 1. 起点条件

| 项 | 本机实测 | 官方要求 | 判定 |
|---|---|---|---|
| 系统 | Ubuntu 22.04.5 (jammy) | 22.04 | ✅ |
| 磁盘 | 可用 456G（最终占 91G） | ≥200G | ✅ |
| 内存 / CPU | 15.6G / 6 核 | ≥16G / ≥4 核 | 🟡 内存差 0.4G，RK 线远比 AOSP 轻，够用 |
| swap | 2G | 未要求 | 🟡 建议补 8G |
| apt 组件 | main/restricted/universe/multiverse 全开 | 必需（很多包在 universe） | ✅ |
| i386 多架构 | 已启用 | `libncurses-dev:i386` 需要 | ✅ |
| 用户 | `rk`（sudo 组，非 root） | 禁止 root 登录编译 | ✅ |
| 外网 | 通 | 装包 + chroot 一次 apt upgrade | ✅ |

> 🔴 官方红线两条：**SDK 不能放在共享目录下编译**；**不能用 root 账号编译**。
> 🔴 这台 RK VM 和安卓编译 VM（`vm-laide`）**不要同时开机**（43G+15.6G > 宿主机 64G）。
> 安卓那台"别动 `/usr/bin/python`、别装 `python-is-python3`"的红线**在这台不适用**，照 RK 官方清单做。

## 2. 完整命令序列

### ① 免密 SSH

VM 终端里粘公钥（`install -d -m 700 ~/.ssh` + `>> authorized_keys` + `chmod 600`），
Windows `~/.ssh/config` 加：
```
Host rk-vm
  HostName 192.168.234.141
  User rk
  IdentityFile ~/.ssh/id_ed25519
  IdentitiesOnly yes
```
判据：`ssh -o BatchMode=yes rk-vm 'echo SSH_OK'`。家目录必须**组不可写**（`drwxr-x---` 可以，775 会被拒）。

### ② 依赖（约 8 分钟）

```bash
PKGS="autoconf bc binfmt-support bison build-essential bzip2
chrpath cmake cpp-aarch64-linux-gnu curl device-tree-compiler diffstat
expat expect tcl8.6-dev fakeroot flex
g++ g++-multilib gawk gcc gcc-multilib git gnupg gperf gpgv2 imagemagick
libncurses-dev libncurses-dev:i386 lib32readline-dev lib32z1-dev libgmp-dev
libgucharmap-2-90-dev liblz4-tool libmpc-dev
libncurses5-dev libsdl1.2-dev libssl-dev libwxgtk3.0-gtk3-dev
libxml2 libxml2-utils live-build lzop
make module-assistant openjdk-8-jdk
patchelf pngcrush python2 python-is-python3 python3-pip
qemu-user-static rsync schedtool squashfs-tools ssh sudo
texinfo u-boot-tools unzip xsltproc yasm zip zlib1g-dev
gettext cpio file pkg-config libtool dpkg-dev"

sudo apt-get update && sudo apt-get install -y $PKGS
python3 -m pip install --user pyelftools
sudo apt-get install -y --reinstall binfmt-support qemu-user-static
sudo ln -sf /usr/bin/python2 /usr/bin/python
```

**相对官方页的 6 处修正**（照抄必然失败）：

| 官方写 | 改成 | 原因 |
|---|---|---|
| `ncurses-dev` | `libncurses-dev` | Debian 叫法，Ubuntu 无此包 |
| `lib32ncurses5-dev` | `libncurses-dev:i386` | 老包名，22.04 无 |
| `expect-dev` | `tcl8.6-dev` | 22.04 无此包 |
| `python-pip` | **删掉，只留 `python3-pip`** | 🔴 `python3-pip : Breaks: python-pip`，两个都在 → **整批一个不装** |
| 末尾 `pip` / `sudo pip install` | `python3-pip` / `python3 -m pip` | 22.04 没有叫 `pip` 的包也没有 `pip` 命令 |
| `sudo ln -s ...` | `sudo ln -sf ...` | `python` 已被 `python-is-python3` 占住，`-s` 直接报错 |
| （清单里没有） | **补 `gettext`**（另加 `cpio file pkg-config libtool dpkg-dev`） | recovery 走 buildroot，`mk-buildroot.sh` 要 `msgmerge` |

> ⚠️ 官方 `python-is-python3`（`python`=py3）和 `ln -s python2 → python`（`python`=py2）两条**本身矛盾**。
> 这里按最后一条走；回退：`sudo ln -sf /usr/bin/python3 /usr/bin/python`。
> **装完必须跑自检**，别信 apt 没报红字：
> `for t in git make bison flex dtc msgmerge cpio python java pip3; do printf "%-9s " $t; command -v $t \|\| echo 缺; done`

### ③ SDK 传输与展开（约 3 分钟）

```bash
mkdir -p ~/k11c && cd ~/k11c          # ← 先建目录！scp 到不存在的目录会失败
# 三件套一起传：tar.gz(6.28G) + .md5sum + release_sdk.sh
md5sum -c rk-linux6.1-2026091606.tar.gz.md5sum    # 9.6 秒，md5 1d2c7c9480bbb48eedb91dab9ae0bb0f
chmod +x release_sdk.sh && ./release_sdk.sh
```
包里**只有 `.git`**，工作树靠 `git reset --hard` 还原 —— 正常现象。解出 **23G**，`git log -1` = `a11afccc2`。

### ④ 选配置

```bash
cd rk-linux6.1-2026091606
./build.sh chip:rk3566_rk3568                                  # 🔴 必须先跑
./build.sh rockchip_rk3566_kickpi_k11c_v12_ubuntu_defconfig
grep -E "^RK_(UBUNTU_ARCH|UBUNTU_VERSION|UBUNTU_MIRROR|ROOTFS_SYSTEM|KERNEL_DTS)" output/.config | sort
```
🔴 跳过 `chip:` 会报 `No available defconfigs for:`（脚本按 `device/rockchip/.chip` 软链 glob）。
`chip:` 那步末尾会抛一串 `init_hook failed` 红字，但**软链已建成，忽略即可**。

实测解析值（K11C 只有 4 个 defconfig，全 `_{ubuntu,debian}_`，官方网页那张 defconfig 表里**没有 K11C**）：
```
RK_KERNEL_DTS_NAME="rk3566-kickpi-k11c-v12-linux"   RK_ROOTFS_SYSTEM="ubuntu"
RK_UBUNTU=y  RK_UBUNTU_ARCH="arm64"  RK_UBUNTU_VERSION="noble"
RK_UBUNTU_MIRROR="mirrors.ustc.edu.cn"  RK_UBUNTU_USER/PASSWORD=kickpi/kickpi
```
ARCH 必须 arm64 —— `ubuntu/packages/` 下只有 `arm64`，装错架构会 `cp packages/$ARCH/*` 扑空。

### ⑤ rootfs：走 overlay，不联网造桌面

SDK **不带任何 rootfs**（`*rootfs*.img`、`ubuntu-base*.tar.gz`、`linaro-*.tar.gz` 全 0 命中，被 `.gitignore` 排除）。
`build_ubuntu()` 的分支就一句：`if [ -f ubuntu/ubuntu-rootfs.img ]` → 有就走 overlay，没有才去跑
`mk-base-ubuntu.sh`（从 cdimage 下 ubuntu-base + chroot 里 apt 装 xfce 桌面，数 GB、1~2 小时）。

**官方文档给的正是"放预置 img"这条路**（只是那页拿 5.10 SDK 做示例）。我们没有 6.1 线的预置 rootfs，
但**官方成品 `update.img` 里就封着一个** —— 用 SDK 自带工具拆出来喂回去：

```bash
mkdir -p ~/k11c/prebuilt
scp "Ubuntu2404/K11C_V1.2/update-rk3566-kickpi-k11c-v12-linux-ubuntu2404-multi-2026073120.img" \
    rk-vm:~/k11c/prebuilt/update.img
cd rk-linux6.1-2026091606/tools/linux/Linux_Pack_Firmware/rockdev
cp -f ~/k11c/prebuilt/update.img ./update.img && ./unpack.sh
cp output/rootfs.img ~/k11c/rk-linux6.1-2026091606/ubuntu/ubuntu-rootfs.img && rm -f update.img

tar -xzf ~/k11c/buildroot-dl-rk-linux6.1-20260801.tar.gz -C buildroot/   # buildroot 离线源码，否则逐个联网下
```
> `rk-linux6.1` 侧官方另有自建脚本 `ubuntu/mk-rootfs-noble.sh`、`debian/mk-rootfs-bookworm.sh`（overlay 在 `ubuntu/overlay`）。
> `mk-image.sh` 会 `rm ubuntu-rootfs.img` 再用 `binary/` 重建 —— 流程自我消耗输入 img，正常；
> 留 `~/k11c/prebuilt/update.img` 和 `rockdev/output/rootfs.img` 两份原件兜底。
> ⚠️ 本地 `D:\02_baidu\linux\rootfs\` 和 `rootfs\` 里那两份 rootfs 是 **5.10 线**的（Debian 那份日志写死
> `/lib/modules/5.10.160/`），**不能配 6.1**。`Ubuntu2404\`、`Debian12\` 成品镜像才是 6.1 线。

### ⑥ 编译

```bash
./build.sh          # 默认目标 = all
```
可用目标（`./build.sh --help` 实测）：`uboot` `kernel` `kernel-6.1` `kernel-config` `kernel-modules`
`recovery` `ubuntu` `debian` `buildroot` `yocto` `rootfs` `updateimg` `misc` `firmware` `extra-parts`
`loader` `all` `release` `config-rootfs-type` `clean-*`。
> ⚠️ 官方页写的 `all_multi_dtb` / `kernel_multi_dtb` **在这套 6.1 SDK 里不存在**（那是 5.10 的）。
> 无屏走 HDMI 也不需要多 dtb。有 `./build.sh clean`，比安卓那边只能 `rm -rf out/` 舒服。

## 3. 时间线与产物

| 阶段 | 起 | 止 | 用时 | 结果 |
|---|---|---|---|---|
| `./build.sh` 首轮 | 12:36:33 | 13:03:32 | 27m | **rc=1**，卡 recovery（缺 `gettext`） |
| `./build.sh recovery` | 13:05:54 | 14:17:23 | 72m | rc=0，0 ERROR |
| `./build.sh` 全量 | 14:18:04 | 14:26:42 | **8m38s** | **rc=0**，0 ERROR，13 阶段 succeeded |

产物在 `rockdev/`（全是指向 `output/` 的软链，看真实大小要 `ls -lL`）：`update.img` +
带板名软链 `update-rk3566-kickpi-k11c-v12-linux-ubuntu2404-2026101514.img`。

**分区逐个对账（我们编的 vs 官方成品拆出来的）：**

| 分区 | 自编 (B) | 官方 (B) | |
|---|---|---|---|
| MiniLoaderAll.bin | 481,728 | 481,728 | ✅ |
| uboot.img | 4,194,304 | 4,194,304 | ✅ |
| misc.img | 49,152 | 49,152 | ✅ |
| recovery.img | 47,502,336 | 47,502,336 | ✅ |
| oem.img | 12,582,912 | 12,582,912 | ✅ |
| userdata.img | 8,388,608 | 8,388,608 | ✅ |
| rootfs.img | 7,056,916,480 | 7,056,916,480 | ✅ |
| **boot.img** | **41,867,776** | 42,333,184 | ⬅ 唯一真实差异 = 自编内核+DTS，预期 |
| **update.img** | **7,172,475,466** | 7,172,940,362 | 差 0.006% |

**回传校验**（7G 镜像跨网络必经；烧坏一次可能要重刷）：
```bash
ssh rk-vm 'md5sum ~/k11c/rk-linux6.1-2026091606/rockdev/update.img'   # c9d895169b7d886f86daea13742f2d0b
certutil -hashfile "D:\02_baidu\自建镜像\K11C_v12_ubuntu2404_selfbuild-20261015.img" MD5   # 同一串
```

## 4. 烧录

**工具**（已解压，zip 套三层是压缩包本身结构）：
```
驱动  D:\02_baidu\win_x64_DriverAssitant\DriverAssitant_v5.13\DriverAssitant_v5.13\DriverInstall.exe
烧录  D:\02_baidu\win_x64_RKDevTool\...\RKDevTool.exe
TF卡  D:\02_baidu\win_x64_SDDiskTool\...\SD_Firmware_Tool.exe
```
**进刷机模式**：K11C 靠按键，**没有短接点**；板上 4 键 RST / RECOVERY / POWER / **MASKROM（在主板背面）**。
- LOADER（常规完整烧录）：通电 → 插 USB → 长按 MASKROM/RECOVERY → 短按 RESET
- MASKROM（强刷）：断电 → 长按 MASKROM → 上电 + 插 USB → 识别到后松手
- **RKDevTool → Upgrade Firmware → 选 `update.img` → Upgrade**；分区级用 Download Image 页 + Load Config（**必须勾 Write by Address**）

> ⚠️ 官方曾建议"先烧一发成品镜像验硬件"。本次实际是**直接烧自编固件并成功**，那条不是必需步骤，
> 只在"第一次不确定硬件/驱动是否 OK"时当保险用。

## 5. 上板实测结果（2026-10-15 夜）

### ✅ 已证

| 项 | 结果 |
|---|---|
| 是不是我们的内核 | `uname -v` = **`#2 SMP Thu Oct 15 14:18:30 EDT 2026`**；`uname -a` = `Linux kickpi 6.1.141 ... aarch64` |
| DTS 有没有生效 | `/proc/device-tree/model` = **`Rockchip RK3566 KICKPI K11C Board`**，compatible = `rockchip,rk3566-kickpi-k11c` |
| 模块加载 | `dmesg \| grep -ic 'vermagic\|invalid module format\|disagrees\|unknown symbol'` = **0**；`lsmod` = `skwbt` `swt6621s_wifi` `skw_sdio_lite` |
| 显示通路 | `card0` / `card0-HDMI-A-1` / `card1` / `renderD128` / `renderD129`；`rockchip-vop2 fe040000.vop` 正常分 plane |
| HDMI | `dwhdmi-rockchip fe0a0000.hdmi: Detected HDMI TX controller v2.11a with HDCP (DWC HDMI 2.0 TX PHY)` |
| WiFi / BT | Seekwave 驱动 boot 成功（`boot bt sucessfully`，chip 0x5302），固件 `SWT6621S_SEEKWAVE_*.bin/ini` 齐 |
| 声卡 | 3 张：`rockchip-rk809`、`rockchip,hdmi`、`rockchip,bt` |
| 有线 | `rk_gmac-dwmac fe010000.ethernet`，PHY `MAE0621A-Q2C Gigabit`，接口名 **`end1`** |

### ⚠️ 待处理

1. **3 个 systemd 单元 failed**：
   ```
   rockchip.service     Setup rockchip platform environment   ← 最该查，可能影响厂商多媒体/MPP/rga 设置
   networking.service   Raise network interfaces              ← 大概是没插网线 + 没配 SSID
   apport.service       automatic crash report generation      ← 无所谓
   ```
   查：`systemctl status rockchip.service`；`journalctl -u rockchip.service --no-pager | tail -40`
2. `card0-HDMI-A-1/status` = **`disconnected`** → **HDMI 出图仍未验证**（没插显示器；驱动认到 ≠ 点亮）
3. `iw` 没装，配网用 `nmcli` / `wpa_cli`，或 `apt install iw`
4. `/lib/modules` 只有 10 个厂商 `.ko`，**没有 `6.1.141/` 模块树**；我们编的 156 个 `.ko` 没进 rootfs
   （其余都 `=y` 内建，启动不受影响）。要往板上加内核模块时得先解决这个投递路径。
5. 内核里 `CONFIG_MODULE_FORCE_LOAD=y`：vermagic 不匹配也照样加载 —— **不报错不等于没问题**

### 无害噪声（别当失败）

```
W: GPG error: ... Couldn't create temporary file /tmp/apt.conf.XXX for passing config to apt-key
ln: failed to create symbolic link '/vendor/etc/firmware': File exists
E: Can not write log (Is /dev/pts mounted?) - posix_openpt (19: No such device)
dwhdmi-rockchip ... error -ENXIO: IRQ index 1 not found          ← RK 内核常见，一般不影响出图
Reserved memory: failed to reserve memory for node 'drm-logo@0'   ← 开机 logo 保留区
```

## 6. 调试串口

**结论：板子有 DEBUG 引脚，但不集成串口桥 —— 必须自备 USB-TTL。**
官方 `Beginner-Guide/KICKPI-K11C/` 有 `K11C DEBUG引脚` 专节（二维引脚图 + 实物图）：
线序 **红=VCC（无需连接）/ 绿=TX / 白=RX / 黑=GND**，MobaXterm Speed 设 **1500000**，
**没输出就把绿和白对调**。

从我们自己编出来的 DTB 核实（比文档权威）：
```
fiq-debugger { rockchip,serial-id = <2>; baudrate = <0x16e360>; pinctrl-0 = <&uart2m0_xfer>; status = "okay"; }
bootargs = "earlycon=uart8250,mmio32,0xfe660000 console=ttyFIQ0 root=PARTUUID=614e0000-0000 rw rootwait"
```
→ **UART2 @ 1500000，复用 uart2m0 = GPIO0_D0/D1**。板上也确实起了 `serial-getty@ttyFIQ0.service`。
查法（换板子也能用）：`dtc -I dtb -O dts <板级>.dtb > x.dts`，再看 `fiq-debugger` 节点。
要降波特率就改 `rockchip,baudrate`（`ttyFIQ0` 的速度只由这个 DT 属性决定），重编 boot.img。

**FT232R 驱动装法（Windows 10 19045）**：设备错误码 28 = 无驱动；`ftdichip.com` 被 FlClash 解析成
fake-ip `198.18.0.24` 且 TLS 握不上（`--noproxy` 也一样，TUN 在网络层劫持）；winget 无 CDM 包。
**走 Windows Update 成功**：`SearchOrderConfig=1` → 禁用/启用设备 + `usoclient StartScan` + `pnputil /scan-devices`
→ `USB Serial Converter` + `USB Serial Port (COM14)`。**结论：这类驱动先想 WU，别急着去官网抓安装包。**

**用串口跑命令的可靠姿势**（踩出来的）：`.NET SerialPort` 连发会丢帧、把命令打飘
（我就因此误判过"sudo 密码不对"）。必须**发一条 → 等到哨兵标记 → 再发下一条**；
`finally { $p.Close() }` 交还端口；PowerShell 在 GBK 控制台打中文会 `UnicodeEncodeError`，落 UTF-8 文件再读。

### 凭据

| 系统 | 用户/密码 | |
|---|---|---|
| Ubuntu 24.04 | `kickpi`/`kickpi`（实测 `sudo -S` 回 `uid=0(root)`，`sudo:x:27:kickpi`）、`root`/`root` | ✅ 已验证 |
| Ubuntu 20.04 | 官方表：`kickpi`/`kickpi`、`root`/`root` | — |
| Debian 12 | `linaro`/`linaro`、`kickpi`/`kickpi`、`root`/`root` | — |

## 7. 已知坑速查

| 现象 | 原因 / 处置 |
|---|---|
| `apt install` 结尾没红字但 `git` 还是缺 | 一个包冲突 → **整批不装**（本次 `python3-pip Breaks python-pip`）。装完必跑 `command -v` 自检 |
| `scp` 后台任务报 exit 0 但目标没文件 | `scp ... \| tail` 管道吃掉了错误码。先单独 `ssh mkdir`，或 `set -o pipefail` |
| `No available defconfigs for:` | 没先 `./build.sh chip:rk3566_rk3568` |
| recovery 阶段 `Your msgmerge is missing` | 官方清单漏 `gettext` |
| `Run mk-base-ubuntu.sh first` | 没放 `ubuntu/ubuntu-rootfs.img`（overlay 输入缺失） |
| buildroot 满世界下源码 | 没解 `buildroot-dl` 进 `buildroot/dl/`；拉不到 GNU 源时把 `BR2_GNU_MIRROR` 改清华 `https://mirrors.tuna.tsinghua.edu.cn/gnu` |
| 改 rootfs 分区大小 | `device/rockchip/.chips/rk3566_rk3568/parameter-buildroot-fit.txt`，末分区 `-@...(rootfs:grow)`；改完注释掉 `rootfs/etc/fstab` 里 oem/userdata 自动挂载 |
| 板子有 MIPI 屏但点不亮 | 板级 dts 取消对应屏头文件注释（本次无屏，不涉及） |
| RKDevTool 认不到板 | 换后置 USB 口 / 重装驱动 / 管理员运行；必须是**数据线** |
| `设备类型不匹配，停止执行！` | 没进 LOADER/MASKROM |
| `校验芯片失败，固件中芯片标志不正确` | 镜像型号不对（V1.1/V1.2 选错、edp/multi 选错） |
| 蓝灯灭或常亮 | 内核死机。绿灯常亮 + 蓝灯闪 = 正常 |
| 中文 SSID 连不上 | 高通 WiFi 栈缺陷，`wlan0` 永久 `NO-CARRIER`，**SSID 必须纯英文** |
| eMMC 与 SD 都有系统 | **SD 优先**，测完先断电再拔卡 |
| 想换 rootfs 类型 | `./build.sh config-rootfs-type`；`RK_UBUNTU_SERVER=y` = 只装 base 不装桌面（省一大截下载） |

## 8. 来源

- 编译环境/包/lunch/烧录：<https://doc.kickpi.cn/Products/SDK-Compilation/RK356x-RK3588/Linux_SDK/>
- rootfs 定制与 package-file：<https://doc.kickpi.cn/Products/Linux-Customization/Linux_Rootfs/>
- 系统配对表与账号：<https://doc.kickpi.cn/Products/System-Login/System-Login/>
- K11C 按键 / LOADER / MASKROM / DEBUG 引脚：<https://doc.kickpi.cn/Products/Beginner-Guide/KICKPI-K11C/>
- 下载页与工具网盘：<https://doc.kickpi.cn/Products/Download/Download/>
- 引脚定义与 V1.1→V1.2（扩展引脚电源域改 3.3V）：<https://doc.kickpi.cn/Products/Peripherals-and-Interfaces/Pinout/>
- 本地：`D:\02_baidu\`（SDK / rootfs / 成品镜像 / 烧录工具 / 原理图），VM `~/k11c/build1.log` `recovery1.log` `build2.log`
- 执行手法（非交互 sudo、假成功三坑）：`03_ai的记忆_和skill\04_workbuddy_记忆与skill\skills\vm-ssh-sudo-exec\SKILL.md`
