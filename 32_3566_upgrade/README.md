# K11C V1.2：官方 SDK 改成 Buildroot，并做成 A/B 双槽

这里只放相对官方包**新增和改过的文件**。没有整份 SDK，也没有 `update.img`。套回官方包之后按下面的步骤编，得到的就是 2026-11-15 烧进板子的那一版。

## 基线

| 项 | 值 |
|---|---|
| 包名 | `rk-linux6.1-2026091606.tar.gz` |
| md5 | `1d2c7c9480bbb48eedb91dab9ae0bb0f` |
| 解压后的 git | `a11afccc2` `feat(build): add K1Mini dual-lvds and K8C to batch build` |
| 板子 | KICKPI K11C，RK3566，V1.2。设备树名 `rk3566-kickpi-k11c-v12-linux` |

这个包是 KICKPI 的 rk-linux6.1 SDK。本机从网盘下到 `D:\02_baidu`，编译机解在 `~/k11c/rk-linux6.1-2026091606`。不要拿 5.10 线的 `buildroot-dl_20250430` 来配这份内核。

## 套进去

在 SDK 根目录：

```sh
git apply /path/to/32_3566_upgrade/patches/01-kernel-hid-and-peripheral.patch
git apply /path/to/32_3566_upgrade/patches/02-libxcrypt-host.patch
cp -a /path/to/32_3566_upgrade/sdk/. .
```

`sdk/` 里的路径就是 SDK 里的相对路径，直接覆盖进去。两份补丁只动原文件，新文件都在 `sdk/`。

根文件系统里多出来的脚本和服务在 `overlay/`。编译前放到：

```sh
mkdir -p /home/rk/k11c
cp -a overlay/. /home/rk/k11c/k11c-br-staging/
# 把 example 改名并填上自己的 WiFi，不要把填好的文件提交进仓库
cp /home/rk/k11c/k11c-br-staging/etc/wpa_supplicant/wpa_supplicant-nl80211-wlan0.conf.example \
   /home/rk/k11c/k11c-br-staging/etc/wpa_supplicant/wpa_supplicant-nl80211-wlan0.conf
cp users.txt links.txt sync-overlay.sh /home/rk/k11c/
sh /home/rk/k11c/sync-overlay.sh
```

自己的 SSH 公钥写到 `overlay/root/.ssh/authorized_keys`，再同步一次。仓库里不带钥匙。

Buildroot 配置里写死了这两个路径，换机器要改 `sdk/buildroot/configs/rockchip_rk3566_k11c_kvm_defconfig` 最后两行：

```
BR2_ROOTFS_OVERLAY+="/home/rk/k11c/k11c-br-overlay"
BR2_ROOTFS_USERS_TABLES="/home/rk/k11c/k11c-br-users.txt"
```

## 改了哪些地方

### 补丁，打在官方文件上

| 补丁 | 文件 | 改什么 |
|---|---|---|
| `patches/01-kernel-hid-and-peripheral.patch` | `kernel-6.1/arch/arm64/configs/rockchip_linux_defconfig` | 打开 `CONFIG_USB_CONFIGFS_F_HID`。没有它，Type-C 上组不出键盘鼠标 |
| 同上 | `kernel-6.1/arch/arm64/boot/dts/rockchip/rk3566-kickpi-k11c-v12.dtsi` | `&usbdrd_dwc3 { dr_mode = "peripheral"; }`。这块板的 Type-C 没有角色控制器，默认 otg 时 UDC 不稳定 |
| `patches/02-libxcrypt-host.patch` | `buildroot/package/libxcrypt/libxcrypt.mk` | 补上 host 版 libxcrypt。选了 systemd 之后，编译机上的 host-systemd 依赖它，原文件只编目标机 |

### 新文件，按路径放进 SDK

| 仓库里的文件 | 放到 SDK 的位置 | 作用 |
|---|---|---|
| `sdk/buildroot/configs/rockchip_rk3566_k11c_kvm_defconfig` | 同路径 | 精简 Buildroot：systemd、python3、GStreamer 和 `mpph265enc`、libdrm、dropbear、WiFi、avahi。不带 Weston、Chromium、NPU、相机 |
| `sdk/device/.../parameter-k11c-ab.txt` | 同路径 | **现在这块板子用的分区表**。见下一节 |
| `sdk/device/.../rockchip_rk3566_kickpi_k11c_v12_buildroot_ab_defconfig` | 同路径 | 板级配置：Buildroot + 上面那张表 + `RK_AB_UPDATE=y` + uboot 用 `k11c-ab`。关掉 SDK 自带的 USB adb |
| `sdk/u-boot/configs/k11c-ab.config` | 同路径 | 在官方 `rk3566.config` 上打开 `CONFIG_ANDROID_AB`。uboot 靠这个读 misc，决定下次从 A 还是 B 启动，并改掉内核 cmdline 里的 `root=` |
| `sdk/external/mpp/build/cmake/merge_objects.cmake` | 同路径 | 官方树里 mpp 的 CMakeLists 要这个文件，包里却没有。从 rockchip-linux/mpp 的 develop 分支补的同名文件。不补的话 Buildroot 编到 `rockchip-mpp` 会停 |
| `sdk/device/.../parameter-k11c-kvm.txt` | 同路径 | 更早的单槽表（带 recovery，userdata 2GB）。build1 / build2 用过。**不要和这次的 A/B 固件混烧** |
| `sdk/device/.../rockchip_rk3566_kickpi_k11c_v12_buildroot_defconfig` | 同路径 | 单槽那一版的板级配置。对照用 |

### 放进根文件系统的文件（`overlay/`）

| 文件 | 作用 |
|---|---|
| `usr/local/sbin/k11c-gadget.sh`、`k11c-gadget.service` | 开机在 Type-C 上挂键盘、绝对鼠标、串口。VID:PID `1d6b:0104` |
| `usr/local/sbin/k11c-grow.sh`、`k11c-grow.service` | 把 `/bin/bash` 写进 `/etc/shells`（不然 dropbear 拒绝 root），并把当前根分区、userdata、oem 的 ext4 扩到分区那么大 |
| `usr/local/sbin/k11c-ab-mark.py`、`k11c-ab-mark.service` | 启动成功后把 misc 里当前槽标成 successful。不标的话，uboot 每个槽只给 7 次尝试 |
| `serial-getty@ttyGS0` 的 autologin | USB 串口直接登录 root |
| wpa / dhcpcd / dropbear / avahi 的 enable 软链 | Buildroot 不会自己把这些服务设成开机启动，`links.txt` 负责挂上 |
| `etc/k11c-release` | 版本戳。这版是 `k11c-br 2026-11-15 ab1` |

`k11c-upgrade.sh` 是以前单槽、走 recovery 的整包升级脚本。**这张 A/B 表没有 recovery，不要在这块板子上跑它。**

## 分区（`parameter-k11c-ab.txt`）

eMMC 大约 14.5GB。Buildroot 实际只用一百多 MB，所以每套系统给 2GB。

| 分区 | 大小 | 份数 |
|---|---|---|
| uboot | 4MB | 一份。芯片的第一级引导只认一个 uboot |
| misc | 4MB | 一份。A/B 标志在偏移 2048 字节，格式是 Android AVB 的 `AvbABData` |
| boot_a / boot_b | 各 64MB | 两份内核。这次烧录两份内容相同 |
| oem | 64MB | 一份 |
| system_a / system_b | 各 2GB | 两份根文件系统。名字必须是 `system_a` / `system_b`，uboot 按这个名字找 |
| userdata | 剩下约 10GB | 一份。升级包和用户数据放这里，升级包里不要再带 userdata 分区 |

没有 recovery，也没有 backup。正在跑的那一套写另一套，写完再改 misc。misc 仍指向旧槽时掉电，下次还从旧槽起来。

## 编译

SDK 根目录，非交互选配置：

```sh
./build.sh rk3566_rk3568:rockchip_rk3566_kickpi_k11c_v12_buildroot_ab_defconfig
```

先单独跑 `./build.sh chip:` 会停在菜单上。

然后分开跑，不要把几个目标写在同一条 `./build.sh` 里（第二条不会执行）：

```sh
./build.sh uboot
./build.sh rootfs
./build.sh firmware
./build.sh updateimg
```

`firmware` 一定要在 `updateimg` 前面。`updateimg` 发现 `output/firmware/parameter.txt` 已经存在就不会换新的，结果会把旧的单槽表打进包里。

打出来的包清单应是：

```
uboot        uboot.img
misc         misc.img
boot_a       boot.img
boot_b       boot.img
oem          oem.img
system_a     rootfs.img
system_b     rootfs.img
userdata     userdata.img
```

没有 recovery。`boot_b` 和 `system_b` 与 A 用同一份文件，所以第一次烧完两套内容一样，从 A 启动。

2026-11-15 打出来的包：

`update-rk3566-kickpi-k11c-v12-linux-buildroot-2026111509.img`  
244MB，md5 `25bed52b621f846ec26dd534a6ae2e6a`  
本机副本 `D:\02_baidu\自建镜像\K11C_v12_buildroot-ab-20261115.img`

镜像本身不进 git。

## 烧录和已经对过的结果

分区表变了，用 RKDevTool 的 **Upgrade Firmware** 整包烧。

烧完在板上读到：

- `/etc/k11c-release` = `k11c-br 2026-11-15 ab1`
- `/proc/cmdline` 里有 `android_slotsufix=_a`，`root=PARTUUID=` 指向 `system_a`（`mmcblk0p6`）
- `boot_a` / `boot_b` 各 65536 KB，`system_a` / `system_b` 各 2097152 KB，userdata 约 10.3GB
- misc 里 A 槽 priority 15、successful=1；B 槽 priority 14、tries=7、successful=0

根文件系统镜像只有约 148MB，分区有 2GB。`k11c-grow.sh` 写的是 `resize2fs /dev/root`，这块 Buildroot 上没有 `/dev/root` 这个节点，所以第一次没扩开。板上后来对 `/dev/mmcblk0p6` 手动 `resize2fs`，根分区变成 1.9GB。

接着做了一次槽切换，用来证明写的是另一套、启动也真的换了过去：只改 B 槽里未挂载的 `/etc/k11c-release` 为 `k11c-br 2026-11-15 ab1-slotB`，把 misc 里 B 的优先级调到 15、A 调到 14，重启。起来后版本是 `ab1-slotB`，cmdline 是 `android_slotsufix=_b`。这个字符串只存在于 B 槽。B 随后被标成 successful，A 仍是 successful、优先级更低。

## 还没做的

从网上下一个新根文件系统、写进空闲槽、再拨 misc。这次验证是直接改 B 槽里的文件。`k11c-upgrade.sh` 不能拿来做这件事。
