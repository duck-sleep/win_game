---
name: k11c-bsp-split-line
description: K11C BSP patch 拆分任务（32_3566_upgrade/BSP_patch拆分任务.md）：公开基线+三层patch重建SDK；2026-11-19 环境已实测核实（rk-vm 在线、325G 空闲、GitHub/GitLab 通、原料齐）
metadata:
  type: project
---

任务书：`D:\win_game_project\32_3566_upgrade\BSP_patch拆分任务.md`（2026-11-19 用户问"看得懂吗"，已通读并核对配套文件）。
目标：不依赖 KickPI 6.3GB 私有 SDK 包，clone 仓库 → fetch 公开源码 → git am 三层小 patch（A 瑞芯微导入差 / B KickPI 111 提交 / C 本目录改动）→ 拷 blobs → 编出与参考树逐文件一致的 Buildroot A/B 固件。交付 `32_3566_upgrade/bsp/`。验收 L0 合规 / L1 树一致（主判据）/ L2 产物一致 / L3 上板归用户。

## 环境基线（2026-11-19 实测，只读探测）

- 编译机 = **rk-vm**（`rk@rk-vmachine`，NAT 192.168.234.141，Ubuntu 22.04.5，SSH 别名已配）。**在线**。
- 磁盘 `/dev/sda3` 491G 总 / 141G 用 / **325G 空闲** ≥ 任务要求 150G ✅
- 用户在用的树 `~/k11c/rk-linux6.1-2026091606` HEAD = `a11afccc2bd1504e6c17a8cd5f056dd6cece11a0` ✅ **不许动**
- 原料齐：`~/k11c/rk-linux6.1-2026091606.tar.gz`（5.9G，md5 1d2c7c94…）+ `buildroot-dl-rk-linux6.1-20260801.tar.gz`（260M）都在 VM，参考树可本地重解，不用重传
- 外网：github.com 200 / gitlab.com 301 / codeload 301；`git ls-remote https://github.com/rockchip-linux/kernel` 成功 ✅
- 已知网络坑（17 号文档）：Buildroot 下载偶发 SSL 被掐（libxcrypt/dhcpcd 踩过），重跑续编即可；Go 模块当时只有 mirrors.aliyun.com 通（本任务用不到 Go）

## 从 12/26/32 文档继承的操作约束

- `build.sh` 非交互 ssh 要 sudo：SUDO_ASKPASS + sudo→sudo -A 包装（skill `vm-ssh-sudo-exec`）；口令只在记忆里，不进任何 md/仓库
- 选配置非交互写法 `./build.sh rk3566_rk3568:<defconfig>`；单独 `chip:` 会卡菜单
- 四条编译命令分开跑；`firmware` 必须在 `updateimg` 前
- 长编译 nohup 后台 + 轮询日志；scp 不接 `| tail`（吞错误码）
- 安卓 VM 与 rk-vm 不同时开（宿主机 64G 内存）
- Windows→VM 文本去 CRLF；755/软链只在 Linux 侧设；二进制不过 CRLF 处理
- 用户树上禁 `./build.sh clean`、禁删 `buildroot/output/..._ubuntu`（recovery+回退在里面）——bsp-work 是独立新树，不受此限但别碰用户树
- Buildroot defconfig 写死 `/home/rk/k11c/k11c-br-overlay` 等绝对路径 → 同事换机器要改（bsp/README 必须交代；L1 要求与参考树一致，不能擅自改 patch 内容）
- 板子现状：A/B Buildroot（11-18 起 kvm 版在 A 槽），无 recovery，禁 `update ota`/`k11c-upgrade.sh`/裸 `update`
- GPL 注意（26_k11c_kvm/port/PORTING.md）：jetkvm 衍生代码 GPL-2.0，公开分发有义务；overlay 里的 Go 二进制属此类，bsp 推 GitHub 前问用户（任务书本身也要求推送前问）