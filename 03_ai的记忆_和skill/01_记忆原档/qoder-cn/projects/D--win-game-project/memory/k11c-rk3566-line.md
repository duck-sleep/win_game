---
name: k11c-rk3566-line
description: KICKPI K11C(RK3566) Linux SDK 线：选6.1、rootfs走官方overlay(从成品img拆)、K11C无buildroot变体、官方apt清单有硬伤漏gettext、10-15已编译成功并烧板验证
metadata:
  type: project
---

2026-10-15 起，本工作区除 SNM970 掌机外另开一条线：给 **KICKPI K11C（RK3566）** 编译官方 Linux SDK 并刷进板子。
执行步骤与命令清单见 `D:\win_game_project\12_win_上机跑\13_KICKPI_K11C_RK3566_编译烧录.md`。
编译机见 [[rk-vm-k11c]]。

## 硬件事实（用户 2026-10-15 口述）

- 主板是 **V1.2**（丝印确认）→ defconfig 用 `..._k11c_v12_...`，成品镜像选 `K11C_V1.2\`
- **没有屏，走 HDMI** → 不用碰 MIPI/LVDS 的 dts 注释，不需要 `all_multi_dtb`；
  刷官方成品镜像时选 **`multi`**（不接屏默认 HDMI），**不要选 `edp`**
- V1.2 相对 V1.1 只是把扩展引脚电源域优化成 3.3V，但 defconfig / 设备树 / 镜像是两套，混用会刷失败

## 非显然事实（2026-10-15 已实机跑通，不再是推测）

1. **选 `linux-kernel-6.1` 线**，5.10 线官方已停维护。6.1 线配对系统是 **Ubuntu 24.04 / Debian 12**。
2. **SDK 里完全不含 rootfs**（`*rootfs*.img`、`ubuntu-base*.tar.gz`、`linaro-bookworm*.tar.gz` 全 0 命中，
   被 `.gitignore` 排除）。手上 `D:\02_baidu\linux\rootfs\` 与 `rootfs\` 那两份是 **5.10 线**的
   （Debian 那份更新日志写死 `/lib/modules/5.10.160/`），配 6.1 内核 ko 不匹配，**不能用**。
3. **K11C 只有 4 个 defconfig，全是 `_{ubuntu,debian}_`，没有 buildroot 变体**（已展开 SDK 确认）。
   `buildroot/configs/` 里只有通用 `rockchip_rk3566_defconfig` → Buildroot 对 K11C 属于"自己接线"，不是官方路线。
   ⚠️ 我 10-15 上午曾判断"Buildroot 是零下载路径"，**是错的**，别照那个结论规划。
4. **官方文档写的 rootfs 路线 = overlay 模式**（不是联网造 base）：文档要你放一个
   `ubuntu/ubuntu-rootfs.img`，而 SDK 的 `build_ubuntu()` 正是 `[ -f ubuntu-rootfs.img ]` → 走 overlay 分支，
   跳过 `mk-base-ubuntu.sh` 那一大坨 ubuntu-base + apt 装 xfce 桌面的下载。
   我们的 `ubuntu-rootfs.img` 是**用 SDK 自带的 `rkImageMaker -unpack` + `afptool -unpack`
   从官方成品 `update-...ubuntu2404-multi-*.img` 里拆出来的**（7,056,916,480 B）。
   `mk-base-ubuntu.sh` 那条联网路线**官方全站 0 命中**，只是脚本里的备用分支。
5. **官方 Linux_SDK 文档页整篇是给 5.10 `rk356x-linux` 写的**：defconfig 表里没有 K11C；
   页里的 `all_multi_dtb` / `kernel_multi_dtb` 在 6.1 SDK 的 `--help` 中**根本不存在**。
6. **官方 apt 清单在 Ubuntu 22.04 上有硬伤**（逐个 apt-cache 实测 64 个包名 + 一轮失败）：
   - 3 个名字源里不存在：`ncurses-dev`→`libncurses-dev`；`lib32ncurses5-dev`→`libncurses-dev:i386`；`expect-dev`→`tcl8.6-dev`
   - **`python3-pip` 与 `python-pip` 互斥（Breaks）**：清单里只要有一个坏名/冲突，
     整条 `apt-get install -y a b c ...` **一个都不装**，脚本退出码还可能照样 0（别只看 rc）
   - **清单漏了 `gettext`**，而 recovery 走的 buildroot 第一句就要 `msgmerge` → 首轮编译 27 分钟后卡在这
   - 没有叫 `pip` 的包、也没有 `pip` 命令；官方还自相矛盾（既装 `python-is-python3` 又 `ln -s python2→python`）
7. **`./build.sh` 必须先选芯片再选 defconfig**，否则报 `No available defconfigs for: ...`
   （脚本按 `device/rockchip/.chip` 软链 glob）。`chip:` 那步会顺带抛一个无害的 init_hook 错，别被劝退。
8. 🔴 **改内核 config 改 `.config` 是没用的** —— `device/rockchip/common/scripts/mk-kernel.sh` 的
   `do_make_kernel_config()` 每次构建都跑 `make $RK_KERNEL_CFG`（本机 = `kernel-6.1/arch/arm64/configs/rockchip_linux_defconfig`）
   **重新生成 .config**，手改会被无声覆盖。要改就改 defconfig 文件。
   板级 `device/rockchip/.chips/rk3566_rk3568/rockchip_rk3566_kickpi_k11c_v12_ubuntu_defconfig` 只管 DTS/rootfs/parameter，**不含内核 config**。
9. **`./build.sh xxx` 在非交互 ssh 里会直接失败**：它有一段 `read -s -p "[sudo] password"`（给 mount/losetup 缓存口令），
   没 tty 就 exit 1。绕法 = 自己先导出 `SUDO_ASKPASS` + 一个 `sudo -A` 的 PATH 包装（见 [[vm-ssh-sudo-exec]]），
   让它 `if [ -z "$SUDO_ASKPASS" ]` 那个分支整个跳过。
10. **增量重编很快**：只改 defconfig/dts 时 `./build.sh kernel` 约 1 分钟、`updateimg` 约 1 分钟。
    ⚠️ **别拿 update.img 大小当"改到位"的证据**（分区对齐，可能一字节不差）—— 要看 md5 + 直接 `dtc -I dtb -O dts` 查 DTB 内容。

## 当前进度（2026-10-15 更新：已烧板并验证）

`./build.sh` **全量成功**（rc=0，0 个 ERROR，13 阶段 succeeded）。产物 `rockdev/update.img` = 7,172,475,466 B，
除 `boot.img`（自编内核）外每个分区都与官方成品拆出来的**逐字节同大小**。
**已烧进板子并串口登录验证**：`uname -v` = `#2 SMP Thu Oct 15 14:18:30 EDT 2026`、
`/proc/device-tree/model` = `Rockchip RK3566 KICKPI K11C Board` → 跑的确实是我们编的内核和 V1.2 DTS。
凭据：`kickpi`/`kickpi`（sudo 可用，`sudo:x:27:kickpi`）、`root`/`root`。
**遗留**：板上 `rockchip.service` / `networking.service` / `apport` 三个单元 failed（`rockchip.service` 最该查）；
`card0-HDMI-A-1=status disconnected` → **HDMI 出图至今没验**（没插显示器）；`iw` 未装；
`/lib/modules` 只有 10 个厂商 .ko、无 `6.1.141/` 模块树（我们编的 156 个 .ko 没进 rootfs）。
内核里 `CONFIG_MODULE_FORCE_LOAD=y` → vermagic 不匹配也照样加载，**不报错≠没问题**。

**Why:** 10-14 遗留过"缺 rootfs 就去下预置 img"的错判，10-15 翻完官网 124 页 + 展开 SDK + 一轮静默失败的
apt 安装才纠正。事实证明 KICKPI 官方文档存在版本滞后（整页写给 5.10 线）和包清单硬伤，照抄必翻车。

**How to apply:** 涉及 K11C 先读这两份（旧的 14 回归记录已并入 13，不要再找）：
- `12_win_上机跑\13_KICKPI_K11C_RK3566_编译烧录.md` = 从干净系统到固件上板（命令序列、校验表、坑速查、调试串口）
- `12_win_上机跑\14_K11C做JetKVM式IP-KVM_方案.md` = 用这块板做 IP-KVM 的可行性与分阶段计划
  （那条线自己的已定决策与硬件结论另存 [[k11c-ip-kvm-line]]，别在这份里找）
官方文档一律当"可能有版本滞后"处理，包名 / defconfig / build 目标一律以 SDK 源码和 VM 实测为准。
批量 apt 前先筛包名，装完必须跑二进制存在性自检；`build.sh` 取 `PIPESTATUS[0]` 并翻产物清单，别信"没报错"。