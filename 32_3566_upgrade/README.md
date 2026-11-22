# K11C V1.2：官方 SDK 做到 Buildroot + A/B 升级 + 公网 JetKVM

> 没有 6.3GB 官方包也能重建：见 [bsp/README.md](bsp/README.md)（公开基线 + 三层 patch + blobs，fetch→apply→编译）。

下次从零开始，只认这一份。官方包在下面「基线」。本目录是相对那份包的全部改动：补丁、新配置、根文件系统里要放进去的程序。没有整份 SDK，也没有 `update.img`。

2026-11-18 板上跑的就是按这个做出来的系统：Buildroot，A/B 两套根文件系统，电视有画面，公网入口是 `https://app.jetkvm.com`。

## 从官方包到现在这块板子

1. 拿到基线包，解压，确认 git 是 `a11afccc2`。
2. 在 SDK 根目录打 `patches/` 里的两个补丁，再把 `sdk/` 按相对路径拷进去。
3. 把 `overlay/` 同步到 Buildroot 配置里写的那个目录。WiFi 用 `wpa_supplicant-nl80211-wlan0.conf.example` 填好再改名，不要把填好的文件提交。自己的 SSH 公钥放到 `overlay/root/.ssh/authorized_keys`。
4. `fakevo` 必须用本目录这份源码重编（里面同时往 `127.0.0.1:5004` 和 `:5005` 发）。只发 5004 的旧二进制公网没有画面。编译命令见下面「重编 fakevo」。编完的二进制覆盖 `overlay/opt/k11c-kvm/vo/fakevo`。仓库里这份二进制是 2026-11-18 用 Buildroot 工具链编的，工具链没变可以先用。
5. 选 `rockchip_rk3566_kickpi_k11c_v12_buildroot_ab_defconfig`，依次 `./build.sh uboot`、`rootfs`、`firmware`、`updateimg`。`firmware` 必须在 `updateimg` 前面，否则会把旧分区表打进去。
6. 第一次分区表从单槽换成 A/B，用 RKDevTool **Upgrade Firmware** 整包烧。之后不要再用 `update ota` 或 `k11c-upgrade.sh`，这张表没有 recovery。
7. 烧完从 A 槽起来。电视出画、`k11c-fakevo` 日志是 `flips=60`。同一 WiFi 的手机开 `http://<板子IP>:8000`。
8. 公网要再认领一次。旧 Ubuntu 上的 `/etc/k11c/cloud.json` 换系统时没了，备份镜像里也没有。认领步骤见「公网」。认领得到的令牌只留在板子上，不进 git。
9. 以后升级：把新的 rootfs 镜像写进**没在跑**的那一槽（A 在跑就写 `system_b` / `mmcblk0p7`，B 在跑就写 `system_a` / `mmcblk0p6`），`resize2fs`，把 misc 里空闲槽的优先级调高，重启。新镜像里要带上同一份 `/etc/k11c/cloud.json`，公网才不会断。2026-11-18 用这个方法从 `kvm` 升到 `kvm2`，重启后设备号 `598b4eba996bfdf6` 重新 `connected`，并且有 `rtp #` 日志。

## 不要放进仓库的

- `/etc/k11c/cloud.json`（公网长期令牌）
- 填好的 WiFi 配置
- `authorized_keys`
- `update.img` / `rootfs.ext2`

SKU 必须是 `k11c-rk3566`。不要写成 `jetkvm-v2`，云会按那个型号下发 RV1106 的系统镜像。

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

公网和画面还要这些文件，都在 `overlay/`：

| 文件 | 作用 |
|---|---|
| `opt/k11c-kvm/k11c-gw` | 静态 Go 二进制。局域网页面的 WebRTC，收 fakevo 的 UDP `:5004` |
| `opt/k11c-kvm/k11c-cloud` | 静态 Go 二进制。主动连 `wss://api.jetkvm.com`，收 fakevo 的 UDP `:5005` |
| `opt/k11c-kvm/kvm_server.py`、`www/` | 页面和键鼠。局域网是 `:8000`，云客户端把键鼠也打到这个口 |
| `opt/k11c-kvm/vo/fakevo.c` | 必须同时有 `udpsink` 到 5004 和 5005。旧快照只有 5004，公网能连上但没有画面 |
| `opt/k11c-kvm/vo/bars_nv12.yuv`、`glyphs.gray` | fakevo 的彩条和码表 |
| `etc/systemd/system/k11c-fakevo.service`、`k11c-gw.service`、`k11c-kvm.service`、`k11c-cloud.service` | 开机拉起。云服务用 `SSL_CERT_FILE` 指向下面的证书包，并等 `network.target`，不要等 `network-online.target`（这版 Buildroot 上后者会让服务一直不启动） |
| `etc/ssl/certs/ca-certificates.crt` | 从编译机 `/etc/ssl/certs/ca-certificates.crt` 拷的。没有它，Go 连 `api.jetkvm.com` 会报证书不受信任 |
| `usr/local/sbin/device_cloud.py` | 只在第一次认领时用，见「公网」 |

## 重编 fakevo

SDK 里 Buildroot 编完之后：

```sh
O=$SDK/buildroot/output/rockchip_rk3566_kickpi_k11c_v12_buildroot/rockchip_rk3566_k11c_kvm
cd /tmp/fakevo-br   # 把 overlay/opt/k11c-kvm/vo/fakevo.c 放进来
$O/host/bin/aarch64-buildroot-linux-gnu-gcc -O2 -Wall -Wextra -o fakevo fakevo.c \
  $($O/host/bin/pkg-config --cflags --libs libdrm gstreamer-1.0 gstreamer-app-1.0 gstreamer-video-1.0 gstreamer-allocators-1.0)
```

`file fakevo` 应是 ARM aarch64、动态链接、解释器 `/lib/ld-linux-aarch64.so.1`。`strings fakevo | grep 5005` 至少有一行。

## 公网认领

Buildroot 的 Python 没有 `_ssl`，板子自己访问不了 `https://`。`device_cloud.py` 的 `/adopt` 只把一次性的 `tempToken` 写到 `/tmp/k11c-adopt.json`。换长期令牌要在一台能开 HTTPS 的电脑上做。

1. 板子和浏览器在同一个 WiFi。`K11C_STATE=/etc/k11c/cloud.json python3 /opt/k11c-kvm/device_cloud.py serve`，听 `0.0.0.0:8010`。
2. 浏览器打开 `http://<板子IP>:8010`，点 Google 登录。全程同一个浏览器。Google 若问是不是本人，在手机上确认。
3. 跳回板子后，页面写「已收到」。电脑执行 `POST https://api.jetkvm.com/devices/token`，正文 `{"tempToken":"..."}`。把返回的 `secretToken` 写成 `/etc/k11c/cloud.json`，权限 `0600`，内容是 `deviceId`、`sku`（`k11c-rk3566`）、`secretToken`。不要把这个文件提交。
4. `systemctl enable --now k11c-cloud`。日志里应有 `connected`，之后有人从 `https://app.jetkvm.com` 点连接时出现 `rtp #`。

外面的手机开 **https://app.jetkvm.com**，用认领时的那个 Google 账号。同一 WiFi 的页面仍是 `http://<板子IP>:8000`。

## 换槽升级（保住公网）

正在跑的槽不要写。先看 `/proc/cmdline` 里的 `android_slotsufix`。

- `_a`：运行的是 `system_a`（`mmcblk0p6`）。新镜像写到 `system_b`（`mmcblk0p7`）。
- `_b`：反过来。

```sh
dd if=/userdata/rootfs-kvm.img of=/dev/mmcblk0p7 bs=1M    # 例子：当前在 A
resize2fs /dev/mmcblk0p7
```

写之前确认目标分区不是当前 `root=` 那块。新镜像里要已经放好 `/etc/k11c/cloud.json` 和 `ca-certificates.crt`。

然后改 misc 偏移 2048 字节的 `AvbABData`：空闲槽 priority 调成 15、tries 调成 7、successful 调成 0；正在用的槽 priority 调成 14、保持 successful=1。CRC32 是前 28 字节的标准 CRC，按大端写在最后 4 字节。重启。

起来后 `/etc/k11c-release` 应是新版本，`android_slotsufix` 换成另一槽，`journalctl -u k11c-cloud` 里有 `connected`。电视仍是 `flips=60`。旧槽还在，新槽起不来会回到旧槽。

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
