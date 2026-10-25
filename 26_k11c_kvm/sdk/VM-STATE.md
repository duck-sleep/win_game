# 编译 VM（rk-vm）上的状态清单 —— **重开环境照着这个做**

盘点时间 2026-10-21。SDK 根目录：`~/k11c/rk-linux6.1-2026091606/`（git 在 `master` = `a11afccc2`，和 `origin/master` 齐平，**没有本地提交**）。

## A. 改了 SDK 里哪些文件

**全部改动都在 `sdk-tracked.patch` 里**（3 个文件，`git diff` 直接导出）：

| 文件 | 改了什么 | 不做会怎样 |
|---|---|---|
| `kernel-6.1/arch/arm64/configs/rockchip_linux_defconfig` | `+CONFIG_USB_CONFIGFS_F_HID=y` | 建不出 `functions/hid.usb0` ⇒ **Windows 看不到键鼠**（官方底座齐，唯独少 HID 这一个） |
| `kernel-6.1/arch/arm64/boot/dts/rockchip/rk3566-kickpi-k11c-v12.dtsi` | `+&usbdrd_dwc3 { dr_mode = "peripheral"; }` | Type-C 没接角色控制器，默认 `otg` 靠猜 ⇒ **UDC 出不出现不确定** |
| `ubuntu/overlay/home/kickpi/.config/autostart/onboard.desktop` | 官方那份"开机起虚拟键盘"改成 `Hidden=true`（顺带 755→644） | 开机一把 onboard 虚拟键盘**盖在画面上**（10-18 第一次截电视就中招） |

打补丁：

```sh
cd ~/k11c/rk-linux6.1-2026091606
git apply --check /path/sdk-tracked.patch && git apply /path/sdk-tracked.patch
git diff --stat        # 应该看到 3 files changed
```

⚠️ 改内核配置**只能改这个 defconfig 文件**，改 `.config` 会被每次构建 `make <defconfig>` 重新生成时**无声覆盖**。

## B. 往 SDK 里"新增"的东西（不在补丁里，靠脚本重建）

`ubuntu/overlay/` 下我们放了 17 项（`opt/k11c-kvm/`、4 个 `k11c-*.service`、enable 软链、
`default.target`、`usb-gadget.service → /dev/null` 的 mask、netplan、ttyGS0 autologin、`~/.ssh`、autostart 覆盖）。

**这些不用手工备份** —— 一条链从 git 重建：

```sh
sh host/fw_stage.sh --appliance          # 从板子拉只有板子上有的 + 从 repo 拷源码 → 推到 VM /tmp
ssh rk-vm 'RK_SUDO=<VM口令> sh /tmp/fw_install.sh --go'   # 写进 ubuntu/overlay/
```

🔴 **唯一例外：`/etc/netplan/90-NM-k11c.yaml`（WiFi 明文口令）不在 git 里**，
它由 `fw_stage.sh` 从**板子上现拉**。所以三个地方有一份：板子、VM 的 overlay、烧好的镜像。
**板子刷坏 + 镜像丢了 = 这份口令没了**（口令本身在 `12_win_上机跑/01_工程说明.md` 里有记录，所以其实丢不了，但配置文件里的 UUID 那份会丢）。

## C. SDK 之外、VM 上只有一份的东西

| 东西 | 位置 | 价值 / 丢了怎么办 |
|---|---|---|
| **`setup_rk_env.sh`**（本目录已留副本） | VM `~/setup_rk_env.sh` | 🔴 **我们写的依赖安装器**：v2 修三处包名（`ncurses-dev→libncurses-dev`、`lib32ncurses5-dev→libncurses-dev:i386`、`expect-dev→tcl8.6-dev`）、v3 去掉 `python-pip`（和 `python3-pip` **互斥**，一个坏名会让**整批一个都不装**）、逐包兜底、末尾跑二进制存在性自检。丢了要重新踩一遍官方清单的坑 |
| Go 工具链 | VM `~/go-toolchain/go`（1.23.4） | 重装即可，但 **PATH 没写进 `.bashrc`** —— 全靠显式路径调用，见下面 D |
| pion 模块缓存 | VM `~/gopath/pkg/mod` | 重新 `go mod download`；**当时只有 `mirrors.aliyun.com` 通**，GOPROXY 要指对 |
| 官方成品镜像 | VM `~/k11c/prebuilt/update.img`（7.17 GB） | 🔴 **我们 rootfs 的最初来源**（用它拆出 `ubuntu-rootfs.img`）。本机 `D:\02_baidu\linux\rootfs\` 那几份是 **5.10 内核线的，配不上 6.1，不能用** |
| buildroot 离线源码 | VM `~/k11c/buildroot-dl-rk-linux6.1-20260801.tar.gz`（272 MB） | 重新下载 |
| rootfs 备份 | VM `.../ubuntu/ubuntu-rootfs.img.bak-20261020` | 我打包前留的退路（md5 `d90cb0d6…`） |
| 构建日志 | VM `~/k11c/{build1,build2,recovery1}.log` | 排查用，可丢 |

**不是我们的**：`~/k11c/release_sdk.sh` 是 KICKPI 官方脚本（MD5 校验 + 解包），别当自己人写的。

## D. 环境状态（不是文件，但重开机器时必须知道）

```sh
# 1) 选芯片 + 选 defconfig（不做第一步会报 No available defconfigs for:）
./build.sh chip:rk3566_rk3568
./build.sh rockchip_rk3566_kickpi_k11c_v12_ubuntu_defconfig
#    ↑ 这个选择记在 device/rockchip/.chip 软链上，而它被 .gitignore 挡着 ⇒ 重装 SDK 后要重做

# 2) 非交互 ssh 里跑 build.sh：它内部有 read -s 要 sudo 口令，没 tty 直接 exit 1
#    绕法 = SUDO_ASKPASS + 一个 sudo→sudo -A 的 PATH 包装器（见 skill vm-ssh-sudo-exec）
export PATH=/tmp/.sudoexec/bin:$PATH SUDO_ASKPASS=/tmp/.sudoexec/ap.sh

# 3) 编 WebRTC 网关（也可以直接 sh host/../board/gw/build.sh，一条命令搞定）
export PATH=$HOME/go-toolchain/go/bin:$PATH GOPATH=$HOME/gopath GOCACHE=$HOME/gocache
cd ~/k11c-gw && GOOS=linux GOARCH=arm64 CGO_ENABLED=0 go build -ldflags="-s -w" -o k11c-gw .

# 4) 只重打固件的两步（改 overlay/文件时用，约 10-12 分钟）
./build.sh rootfs && ./build.sh updateimg
```

⚠️ `ubuntu/mk-image.sh` 会 **`rm ubuntu-rootfs.img` 再用 `binary/` 重建** —— 输入被自我消耗，
**编译前永远先备份这个 img**（`cp -a ubuntu-rootfs.img ubuntu-rootfs.img.bak-<日期>`）。
