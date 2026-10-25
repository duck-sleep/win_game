# SDK 侧的两处改动（**重建编译环境后必须重打，否则板子不会变成键鼠**）

> **10-21 更新**：这份说明只覆盖内核 + 设备树两处。
> **完整清单在 `VM-STATE.md`**，**完整补丁是 `sdk-tracked.patch`（3 个文件，本文件那份的超集，提交后删掉 `k11c-kvm-kernel.patch`）**。
> 第三处改动是 `ubuntu/overlay/home/kickpi/.config/autostart/onboard.desktop` 改成 `Hidden=true`（官方开机自启的虚拟键盘会盖住画面）。

这两处改的是 **VM 里那份 RK SDK 的源码树**（`~/k11c/rk-linux6.1-2026091606/`），
不在我们自己的 `26_k11c_kvm/` 代码里，所以**重新下载 SDK / 重开虚拟机之后它们就没了**。
10-21 之前它们只存在于 VM 的工作目录里 —— 这份补丁就是为了补掉这个洞。

## 改了什么、为什么

| 改动 | 文件 | 不做会怎样 |
|---|---|---|
| `CONFIG_USB_CONFIGFS_F_HID=y` | `kernel-6.1/arch/arm64/configs/rockchip_linux_defconfig` | 内核里没有 configfs 的 HID 功能 ⇒ `functions/hid.usb0` 建不出来，**Windows 永远看不到键盘鼠标**。底座（`USB_GADGET` / `USB_CONFIGFS` / `ACM` / `MASS_STORAGE` / `F_UVC`）官方都开了，**唯独少 HID 这一个** |
| `&usbdrd_dwc3 { dr_mode = "peripheral"; }` | `kernel-6.1/arch/arm64/boot/dts/rockchip/rk3566-kickpi-k11c-v12.dtsi` | 本板 Type-C 的 CC/ID **没接角色控制器**（整个 DTB 里没有 `usb-role-switch` 也没有 extcon），默认 `"otg"` 只能靠 ID/VBUS 猜角色 ⇒ UDC 会不会出现**不确定**。KVM 要求板子**永远**是被控机的外设，所以写死 |

⚠️ 改内核配置**必须改这个 `rockchip_linux_defconfig` 文件**，改 `.config` 是没用的：
`device/rockchip/common/scripts/mk-kernel.sh` 每次构建都会 `make <defconfig>` **重新生成 `.config`**，手改会被无声覆盖。

## 怎么打

```sh
cd ~/k11c/rk-linux6.1-2026091606/kernel-6.1
git apply --check /path/to/k11c-kvm-kernel.patch && git apply /path/to/k11c-kvm-kernel.patch
cd .. && ./build.sh kernel && ./build.sh updateimg
```

打完自查这两条，**两条都要有输出**：

```sh
grep -n "CONFIG_USB_CONFIGFS_F_HID" kernel-6.1/arch/arm64/configs/rockchip_linux_defconfig
grep -n "dr_mode" kernel-6.1/arch/arm64/boot/dts/rockchip/rk3566-kickpi-k11c-v12.dtsi
```

## 板上验证（烧完之后）

```sh
ls /sys/class/udc/                 # 要有 fcc00000.usb
cat /sys/class/udc/fcc00000.usb/state   # 插上被控机后应是 configured
```
