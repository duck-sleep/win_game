---
name: rk-vm-k11c
description: K11C/RK 编译专用虚拟机（rk@rk-vmachine, 192.168.234.141, ssh 别名 rk-vm）——配置、sudo 口令、AI 可代跑、勿与安卓 VM 同开
metadata:
  type: project
---

2026-10-15 新建的**第二台**虚拟机，专门给 [[k11c-rk3566-line]] 编 RK Linux SDK。与 SNM970 安卓编译机
（`vm-laide` 192.168.64.130）是两台独立机器，规矩不通用。

## 访问方式

- `rk@rk-vmachine`，单网卡 `ens33` = VMware NAT `192.168.234.141`（DHCP，重租会变，连不上先 `ip addr` 核对）
- 宿主机可直连 NAT 段，**不需要**像安卓那台一样加仅主机网卡
- 已配**免密 SSH**：Windows `~/.ssh/config` 别名 **`rk-vm`**，复用现成的 `~/.ssh/id_ed25519`
  （Gitee/GitHub 同一把，这机器一贯这么用），公钥已写入 VM `~/.ssh/authorized_keys`（2026-10-15）
- **sudo 口令 = <已脱敏>**（用户 2026-10-15 主动给出："你输 <已脱敏>就行了 这个问题不大"；我提过一次
  "明文存长期记忆合不合适"，他没在意，**别再拿这事问他**）。口令只留在这份本机记忆文件里，
  **绝不写进仓库文件 / 技术文档**。非交互执行的可用写法：临时 askpass 脚本 + `SUDO_ASKPASS` +
  一个 `sudo -> sudo -A` 的 PATH 包装器（这样脚本里几十处 sudo 都不用改），用完 `rm -rf` 掉含口令的文件。

## 实机体检（2026-10-15）

Ubuntu 22.04.5 LTS (jammy)｜内核 6.8.0-138｜6 vCPU｜内存 15.6G（可用约 14G）｜swap 只有 2G｜
`/` = sda3 491G｜apt 四组件 main/restricted/universe/multiverse 全开｜**i386 多架构已启用**｜
用户 `rk` 在 sudo 组、家目录 `drwxr-x---`（公钥认证正常）｜外网通｜装包前整套编译工具链是空的。

对照官方要求：磁盘 ✅、CPU ✅、**内存 15.6G 略低于官方 16G**（RK 线远比 AOSP 轻，实测编得动，
buildroot 那段也没因内存出问题）。swap 2G 够用，用户没补。

## 当前状态（2026-10-15 收工）

- 依赖全装好（55 个官方包 + 补的 `gettext cpio file pkg-config libtool dpkg-dev`），`python` 按官方指向 2.7
- SDK 解在 `~/k11c/rk-linux6.1-2026091606/`（**23G** 工作树，git 到 `a11afccc2`）
- `~/k11c/prebuilt/update.img`（官方成品 7.17G，用来拆 rootfs）；`buildroot/dl` 已摆 262M 离线源码
- 一轮全量编译成功，产物 `rockdev/update.img`（7,172,475,466 B）
- 磁盘：已用约 91G / 剩 375G。⚠️ `ubuntu/mk-image.sh` 会 **`rm ubuntu-rootfs.img` 再重建**（自我消耗输入 img），
  所以官方成品那份 `prebuilt/update.img` 要留着，别清
- VM 上的安装脚本 `~/setup_rk_env.sh`（v3，官方清单 + 三处包名修正 + 逐包兜底 + 末尾自检），
  日志 `~/k11c/build1.log` / `recovery1.log` / `build2.log`

## 2026-10-21 全量改动审计（"VM 丢了会掉什么"的准确答案）

SDK git：`master` = `a11afccc2`，**和 `origin/master` 齐平、没有任何本地提交** ⇒ 所有改动都在工作区。

**已跟踪文件只改了 3 个（共 9 行）**，已导出成补丁存进仓库 `26_k11c_kvm/sdk/sdk-tracked.patch`：
1. `kernel-6.1/arch/arm64/configs/rockchip_linux_defconfig` → `+CONFIG_USB_CONFIGFS_F_HID=y`
   （官方底座 `USB_CONFIGFS/ACM/MASS_STORAGE/F_FS/F_UVC` 全有，**唯独缺 HID** ⇒ 少了它板子永远不会变成键鼠）
2. `kernel-6.1/arch/arm64/boot/dts/rockchip/rk3566-kickpi-k11c-v12.dtsi` → `+&usbdrd_dwc3 { dr_mode = "peripheral"; }`
3. `ubuntu/overlay/home/kickpi/.config/autostart/onboard.desktop` → 改成 `Hidden=true`（+755→644）

**`git diff` 看不到的两类，都查了**：
- 🔴 `device/rockchip/.chip`（= `.chips/rk3566_rk3568`）**被 .gitignore 挡着** ⇒ 重装 SDK 后必须重做
  `./build.sh chip:rk3566_rk3568` + 选 `rockchip_rk3566_kickpi_k11c_v12_ubuntu_defconfig`，否则报 `No available defconfigs for:`
- 🔴 `~/setup_rk_env.sh`（我们写的依赖安装器：三处包名修正 + 去掉与 `python3-pip` **互斥**的 `python-pip` + 逐包兜底 + 二进制自检）
  ⇒ **已拷进仓库 `26_k11c_kvm/sdk/setup_rk_env.sh`**，全量重建步骤写在同目录 `VM-STATE.md`

**只有 VM 一份、丢了最贵的**：`~/k11c/prebuilt/update.img`（7.17 GB 官方成品，rootfs 唯一源头；
本机 `D:\02_baidu\linux\rootfs\` 那几份是 **5.10 内核线的，配不上 6.1**）、`ubuntu/ubuntu-rootfs.img.bak-20261020`（回滚退路）。
⇒ **建议给这台 VM 打快照**（磁盘剩 353 G）。用户尚未决定。

**两个别再搞错的**：① `~/k11c/release_sdk.sh` 是 **KICKPI 官方脚本**（MD5 校验+解包），不是我们写的；
② **Go 的 PATH 没写进 `~/.bashrc`** ⇒ 调 go 必须显式 `PATH=$HOME/go-toolchain/go/bin:$PATH GOPATH=$HOME/gopath GOCACHE=$HOME/gocache`。
`~/k11c-gw` 是 Go 工程目录（源码在 git，产物不在）。


- 🔴 **不要和安卓编译 VM 同时开机**：安卓那台占 43G，加这台 15.6G 已超宿主机 64G；官方文档也写"一次只能开一台虚拟机"。
- SDK **不能放在共享目录**里编译；不能以 root 登录编译（用 `rk` 用户即合规）。
- 安卓编译机上"别动 `/usr/bin/python` / 别装 `python-is-python3`"那条红线**在这台不适用**，
  这台按 RK 官方清单照做。别把两台的规矩串。
- VM 上的工作目录：见下面「当前状态」

**How to apply:** 需要上机操作时用 `ssh rk-vm '<cmd>'`（BatchMode 已可用），不必再让用户代敲；
涉及 sudo 就按上面的 askpass 包装法自己跑，跑完清理临时文件。动系统级配置（扩容、加 swap、改网络）前仍先说一声。