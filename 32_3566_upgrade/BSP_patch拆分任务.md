# 任务：把 K11C 固件改成「公开源码 + 拆好的 patch + 少量二进制」就能编

给接手的 AI。只看这一份就能做完。做完的东西放在本目录下的 `bsp/`。

## 一句话目标

现在编 K11C 的 Buildroot A/B 固件，要先拿到 KickPI 那个 6.3GB 的 SDK 包（`rk-linux6.1-2026091606.tar.gz`）。要做成的样子是：同事只 clone 本仓库，脚本自己从网上拉公开源码，按顺序打上本仓库里**拆好的、一个个小的** patch，再拷进几个启动用的二进制，就能编出和现在**一样**的固件。

「一样」的判断标准见下面「验收」。主要看重建出来的源码树和参考树逐文件相同。

## 背景（已查实的事实）

### 现在怎么编的

本目录 [`README.md`](README.md) 写的是现行做法：解官方 SDK 包，打 `patches/` 两个补丁，拷 `sdk/`，同步 `overlay/`，然后

```sh
./build.sh rk3566_rk3568:rockchip_rk3566_kickpi_k11c_v12_buildroot_ab_defconfig
./build.sh uboot
./build.sh rootfs
./build.sh firmware
./build.sh updateimg
```

四条要分开跑。`firmware` 必须在 `updateimg` 前面。编译机是 Ubuntu x86_64，现有工作树在 `~/k11c/rk-linux6.1-2026091606`。**不要动这棵树**，它是用户正在用的。

### 官方 SDK 包里有什么

| 项 | 值 |
|---|---|
| 包 | `rk-linux6.1-2026091606.tar.gz`，md5 `1d2c7c9480bbb48eedb91dab9ae0bb0f`。Windows 侧在 `D:\02_baidu\linux-kernel-6.1\rk-linux6.1-2026091606\` |
| 形态 | 整个包就是**一个** git 仓库（根目录 `.git`，对象包约 6.3GB，不是 shallow）。解压后要 `git reset --hard`（包里的 `release_sdk.sh` 就是这么做的）才有工作区 |
| HEAD | `a11afccc2bd1504e6c17a8cd5f056dd6cece11a0` `feat(build): add K1Mini dual-lvds and K8C to batch build` |
| 根提交 | `1f9d3a81314c9c3f0e182643f646d88b580a0fe1` `feat: init linux6.1 sdk on 202603024`。这是瑞芯微 SDK 一次性导入，**没有**写来自哪个上游提交 |
| 历史 | 共 112 个提交。根提交之后 111 个是 KickPI 自己的改动 |
| 顶层目录 | `app batch_build.sh build.sh buildroot common debian device docs external hal kernel kernel-6.1 prebuilts rkbin rkflash.sh rtos tools u-boot ubuntu yocto` |
| 内核 | `kernel-6.1/`，Makefile 是 **6.1.141** |
| U-Boot | `u-boot/`，Makefile 是 **2017.09**（瑞芯微的 next-dev 系） |
| Buildroot | `buildroot/`，`BR2_VERSION := 2024.02`（瑞芯微的 `rockchip/2024.02` 系） |

KickPI 在根提交之后改了哪些目录（`git diff --name-only 1f9d3a8 a11afccc2` 按顶层统计）：`external` 909 个文件、`ubuntu` 440、`kernel-6.1` 229、`device` 163、`debian` 58、`u-boot` 5、`buildroot` 2，另有 `.gitignore`、`common`、`batch_build.sh` 各 1。`ubuntu`、`debian` 里大量是 `.deb`，和 Buildroot 固件无关。

### 启动用的二进制

`rkbin/RKBOOT/RK3566MINIALL.ini` 和 `rkbin/RKTRUST/RK3568TRUST.ini` 用到的是：

| 文件 | 大小 |
|---|---|
| `rkbin/bin/rk35/rk3566_ddr_1056MHz_v1.25.bin` | 59392 |
| `rkbin/bin/rk35/rk356x_usbplug_v1.17.bin` | 98708 |
| `rkbin/bin/rk35/rk356x_spl_v1.14.bin` | 256718 |
| `rkbin/bin/rk35/rk3568_bl31_v1.46.elf` | 402376 |
| `rkbin/bin/rk35/rk3568_bl32_v2.16.bin` | 473528 |

加起来 1.3MB 左右，没有源码，只能原样带。GitHub 单文件 100MB 硬限、50MB 警告，这些都远远够不着。

### 已知的公开基线候选

- 内核：`https://github.com/rockchip-linux/kernel` 分支 `develop-6.1`。其中 `cb2c6fee8a36d85b5ead8f246bbc035259b14b2a` 是 `Merge tag 'v6.1.141'`（2025-07-07），从这附近找起。另有 GitLab 镜像组 `https://gitlab.com/rockchip_linux_sdk_6.1/linux/`，带 `linux-6.1-stan-rkr4.2`、`rkr4.1`、`rkr4` 等标签。
- U-Boot：`https://github.com/rockchip-linux/u-boot` 分支 `next-dev`；GitLab 镜像组里同名仓库。
- Buildroot：`https://gitlab.com/rockchip_linux_sdk_6.1/linux/buildroot` 分支 `rockchip/2024.02`，标签同上；`https://github.com/radxa/buildroot` 分支 `rockchip/2024.02`。
- rkbin：`https://github.com/rockchip-linux/rkbin`。
- `device/rockchip`、`external/*`、`tools`：先在 GitLab 镜像组里找同名仓库（Radxa 文档里 `device/rockchip` 用的是 `https://github.com/radxa/device-rockchip`，`external/rkwifibt` 用的是 `https://github.com/radxa/rkwifibt`）。

不要用 kernel.org 的 6.1.141 当内核基线。瑞芯微的改动会全部压进 patch，大到没法维护。

## 三层差异

参考树 = 官方 SDK HEAD 再套上本目录现有改动。从公开基线到参考树，差异分三层，**每层单独出 patch，顺序打**：

```mermaid
flowchart LR
  pub["公开基线 commit"] -->|"A 层: 瑞芯微发布 vs 公开"| init["SDK 根提交 1f9d3a8"]
  init -->|"B 层: KickPI 111 个提交"| head["SDK HEAD a11afccc2"]
  head -->|"C 层: 本目录 patches/ sdk/"| ref["参考树"]
```

- **A 层**：公开基线和 SDK 根提交之间的差。基线选得越近，这层越小。
- **B 层**：KickPI 的 git 历史。按提交原样导出，一个提交一个 patch，可以追溯。
- **C 层**：本目录 `patches/01-kernel-hid-and-peripheral.patch`、`patches/02-libxcrypt-host.patch`，以及 `sdk/` 下的新文件。

`overlay/` 不算 patch。它照现在的方式在编译时放进根文件系统。

## 拆分规则（硬性）

不要搞一个大 patch。下面每条都要满足，不满足就是没完成。

1. **一个 patch 只讲一件事。** A 层按目录拆；B 层一个 KickPI 提交一个 patch；C 层按改动拆（现有的 `01-kernel-hid-and-peripheral.patch` 要拆成两个：内核 defconfig 打开 `CONFIG_USB_CONFIGFS_F_HID`，以及 dtsi 里 `dr_mode = "peripheral"`）。
2. **单个 patch 文件不超过 1MB，改动文件不超过 100 个。** 超了就按子目录继续往下拆。拆到单个目录还超，就按文件名排序切成连续几段，标题写 `(part 2/5)`。只有**单个源文件本身**超过 1MB 时才允许一个 patch 超限，而且这个 patch 里只能有这一个文件，要写进 `REPORT.md`。
3. **patch 里不能有二进制。** `git diff` 显示 `Binary files differ` 的文件，不进 patch。放到 `bsp/blobs/<组件>/<原相对路径>`，在 `bsp/blobs/SHA256SUMS` 里记 sha256，由 `apply.sh` 拷过去。
4. **用 `git format-patch` 格式**，`git am` 能直接打。每个组件一个 `series` 文件，列出顺序。
5. **文件名** `NNNN-<层>-<主题>.patch`，层是 `a` / `b` / `c`。例如 `0003-a-drivers-video-rockchip.patch`、`0120-b-k11c-fix-lcd-gpio.patch`、`0200-c-usb-hid-gadget.patch`。编号按组件分别从 0001 开始，A 层在前，B 层，C 层在后。
6. **每个 patch 的提交说明里写出处**：
   - A 层：`Origin: rockchip sdk import 1f9d3a8 vs <基线 url>@<commit>, path <目录>`
   - B 层：`Origin: kickpi <原提交 hash>`，标题保留原提交标题
   - C 层：`Origin: 32_3566_upgrade/<原文件>`
7. **B 层空提交不导出。** 某个 KickPI 提交没碰这个组件，就不出现在这个组件的 series 里。B 层不合并提交、不改写内容；单个提交超限时按规则 2 切段。
8. **不放秘密。** 不带 `/etc/k11c/cloud.json`、填好的 WiFi 配置、`authorized_keys`、`update.img`、`rootfs.img`、`buildroot/dl`、编译产物。
9. **整个 `bsp/` 目录的体积要写进报告。** 目标是几十 MB 以内。任一组件的 A 层合计超过 20MB，先回去换更近的基线；换完仍超，照做，但在 `REPORT.md` 里标出来。

## 要交付的目录

```text
32_3566_upgrade/bsp/
├── README.md              给同事看：环境、fetch、apply、build、烧录，十几步以内
├── REPORT.md              这次做的记录：基线选择打分表、每个组件 patch 数和大小、验收输出
├── versions.lock          每个组件：上游 url、commit、（下载包的）sha256
├── scope.txt              参与重建的目录；被裁掉的目录和裁掉的依据
├── patches/
│   ├── kernel-6.1/series + 0001-a-*.patch ...
│   ├── u-boot/series + ...
│   ├── buildroot/series + ...
│   ├── device-rockchip/series + ...
│   ├── sdk-top/series + ...          build.sh、common/ 等 SDK 顶层零散文件
│   └── external-<名字>/series + ...   每个被用到的 external 包一个
├── blobs/
│   ├── SHA256SUMS
│   └── <组件>/<相对路径>              rkbin 里用到的、patch 里放不了的二进制
└── scripts/
    ├── fetch.sh            按 versions.lock 拉基线到工作目录（含工具链下载和 sha256 校验）
    ├── apply.sh            对每个组件 git am series，再拷 blobs，最后拼成 SDK 目录布局
    ├── split-tree-diff.py  A 层用：两棵树的差按规则 2 自动拆成多个提交
    ├── verify-tree.sh      L1 验收：重建树 vs 参考树逐文件比对
    └── compare-build.sh    L2 验收：两边编译产物比对
```

`scripts/` 必须能重复跑：从空目录 `fetch.sh && apply.sh` 两次，结果相同。

## 怎么做

所有活在编译机上做，工作目录 `~/k11c/bsp-work/`。磁盘至少留 150GB（参考树、重建树、各组件临时仓库、两次全量编译）。做完再把 `bsp/` 拷回 Windows 的本目录。

### 第 1 步：建参考树，编一次参考固件

1. 新解一份 SDK 包到 `~/k11c/bsp-work/ref/`，校验 md5，`git reset --hard`，确认 `git rev-parse HEAD` 是 `a11afccc2bd1504e6c17a8cd5f056dd6cece11a0`。
2. 按 [`README.md`](README.md)「套进去」一节套上 C 层：`git apply` 两个补丁，`cp -a sdk/. .`，同步 overlay（WiFi 用 `.example` 填个假的就行，不提交）。
3. 在参考树里 `git checkout -b k11c-target && git add -A && git commit -m "C layer"`。以后用 `k11c-target` 这个提交当「参考树」。再 `git worktree add ~/k11c/bsp-work/ref-clean k11c-target` 留一份不编译的干净树，L1 只和它比（`ref/` 编译后会多出一堆产物）。
4. 按 README「编译」一节编一次。保存 `rockdev/`、`output/firmware/`、内核 `.config`、U-Boot `.config`、Buildroot `.config`、Buildroot `output/.../target/` 的清单（见第 7 步），放到 `~/k11c/bsp-work/ref-out/`。
5. 记下 Buildroot 实际编了哪些包：`ls output/.../build/`。

### 第 2 步：定范围（哪些目录要重建）

1. 在 `ref` 的一份拷贝里删掉和 Buildroot 固件无关的目录：`debian ubuntu yocto rtos docs app hal`，以及 `batch_build.sh`。重新编一次。产物和第 1 步的比对通过（第 7 步的 L2 标准），就说明这些目录可以不要。比对不过，就把出问题的目录加回范围。
2. `kernel` 这个顶层项先看是不是指向 `kernel-6.1` 的软链。是就照样建软链，不是就当一个组件处理。
3. `external/` 只保留真正被编进去的。找法：`grep -rl 'TOPDIR)/../external' buildroot/package` 找出引用 external 的包，和第 1 步第 5 点的包名清单取交集。结果写进 `scope.txt`。
4. `prebuilts/` 只保留编译真正用到的工具链（看 `u-boot/make.sh`、`device/rockchip/common` 里的 `CROSS_COMPILE`）。工具链不做 patch，在 `fetch.sh` 里从官方地址下载并校验 sha256。下完和参考树里那份逐文件比 sha256，必须相同。
5. `tools/` 只保留打包用到的部分（`updateimg` 用的 `afptool`、`rkImageMaker` 等）。能在公开仓库找到同一版就当组件，找不到就整份放进 `blobs/`。
6. `rkbin/` 不整份重建。基线用公开 rkbin 的某个 commit，`blobs/` 只放和那个 commit 不一样、且被 RK3566 用到的文件（上面表里的 5 个，加上 `RKBOOT/RK3566MINIALL.ini`、`RKTRUST/RK3568TRUST.ini`、`tools/` 下被调用的工具）。

### 第 3 步：每个组件选公开基线

对每个组件（kernel-6.1、u-boot、buildroot、device/rockchip、各 external、sdk-top）：

1. 列候选：上面「已知的公开基线候选」里的仓库；GitLab 的 `linux-6.1-stan-rkr*` 标签；GitHub 分支上版本号对得上的一段提交（内核用 `git log -G'SUBLEVEL = 141' -- Makefile` 找范围）。
2. 打分：把 SDK 根提交 `1f9d3a8` 里这个组件的目录导出来（`git archive 1f9d3a8 <目录> | tar -x`），和每个候选比 `git diff --no-index --shortstat`。改动行数最少的赢。候选太多时先按 tag 粗筛，再在最好的 tag 前后几十个提交里细找。
3. 打分表写进 `REPORT.md`：候选、commit、改动文件数、增删行数。选中的写进 `versions.lock`。
4. 如果某个组件在公开仓库里找不到任何候选，这个组件的基线就是「空」，整份当新增文件按规则 2 拆。在 `REPORT.md` 标出来。

### 第 4 步：出 A 层 patch

对每个组件：

1. 新建临时仓库 `~/k11c/bsp-work/split/<组件>/`，检出选中的基线 commit。
2. 用 SDK 根提交 `1f9d3a8` 里的这个目录整份覆盖工作区（包括删除：先清空工作区除 `.git` 外的所有文件，再解进来），保持文件权限和软链。
3. 跑 `split-tree-diff.py`：把未提交的改动按目录分组，每组一个提交。分组算法：从顶层目录开始，某组生成的 diff 超过 1MB 或 100 个文件，就展开到下一级子目录；到了叶子目录还超，就按文件名排序切段。二进制文件不进提交，记到 blobs 清单。
4. `git format-patch -o ../patches-a <基线>..HEAD`，重命名成规则 5 的格式。

### 第 5 步：出 B 层 patch

在参考树（SDK 的 git）里：

```sh
git format-patch --relative=<目录> -o <输出目录> 1f9d3a8..a11afccc2 -- <目录>
```

`--relative` 让 patch 路径相对组件根，能直接在组件仓库里 `git am`。每个 KickPI 提交一个 patch。超限的按规则 2 切段（在临时仓库里 `git am` 后 `git reset HEAD~` 再分组提交）。二进制同样挪到 blobs。

### 第 6 步：出 C 层 patch

在参考树里：`git format-patch --relative=<目录> a11afccc2..k11c-target -- <目录>`，然后按规则 1 把 `01-kernel-hid-and-peripheral` 拆成两个，其余按文件主题拆。`merge_objects.cmake` 归 `external-mpp`，`k11c-ab.config` 归 `u-boot`，两个 `parameter-*.txt` 和两个板级 defconfig 归 `device-rockchip`，`rockchip_rk3566_k11c_kvm_defconfig` 和 `libxcrypt` 归 `buildroot`。

### 第 7 步：写脚本，跑验收

`fetch.sh` → `apply.sh` 在 `~/k11c/bsp-work/rebuilt/` 拼出一棵和 SDK 一样布局的树，然后跑下面的验收。

## 验收

### L0：拆分合规（脚本检查）

- 每个 patch ≤ 1MB、≤ 100 个文件，例外都在 `REPORT.md` 里且只含一个文件
- 没有任何 patch 里出现 `GIT binary patch` 或 `Binary files`
- 每个 patch 都有 `Origin:` 行
- 每个组件的 `series` 和目录里的 patch 一一对应
- 仓库里没有超过 50MB 的单文件；`bsp/` 总大小写进报告
- `git grep -n 'secretToken\|psk=\|BEGIN OPENSSH PRIVATE KEY' -- bsp/` 没有结果

### L1：源码树一致（必须过，这是主判据）

对 `scope.txt` 里的每个目录，`apply.sh` 刚跑完、还没编译的重建树，和干净参考树 `ref-clean` 逐文件相同，包括内容、可执行位、软链目标。git 不记空目录，所以只比文件和软链：

```sh
diff -r --no-dereference --exclude=.git ref-clean/<目录> rebuilt/<目录>
diff <(cd ref-clean/<目录> && find . -path ./.git -prune -o ! -type d -printf '%m %y %l %P\n' | sort) \
     <(cd rebuilt/<目录>   && find . -path ./.git -prune -o ! -type d -printf '%m %y %l %P\n' | sort)
```

输出必须为空。`rkbin` 只比第 2 步第 6 点那份清单；工具链比 sha256 清单。L1 过了，源码层面就是同一套。

### L2：编译产物一致

在重建树里按 README 同样的四条命令编一次，和 `ref-out/` 比：

| 比什么 | 要求 |
|---|---|
| `output/firmware/parameter.txt` | 字节相同 |
| `MiniLoaderAll.bin` | md5 相同 |
| 内核 `.config`、U-Boot `.config`、Buildroot `.config` | 字节相同 |
| `rk3566-kickpi-k11c-v12-linux.dtb` | 字节相同 |
| Buildroot `output/build/` 包名和版本清单 | 相同 |
| Buildroot `target/` 清单：每个文件的路径、权限、大小、sha256 | 相同。允许不同的只能是带编译时间的文件，逐个列进 `REPORT.md` 并说明原因 |
| `update.img` 的分区清单 | 和 README「编译」一节列的八行一致 |

`update.img`、`boot.img`、`uboot.img` 里有编译时间，不要求整包 md5 相同。

### L3：上板（交给用户做，不要自己烧）

在 `REPORT.md` 末尾写给用户的步骤：RKDevTool **Upgrade Firmware** 整包烧重建出来的 `update.img`，然后检查：

- 串口能登录，`/etc/k11c-release` 是 overlay 里那个版本
- `/proc/cmdline` 有 `android_slotsufix=_a`
- `journalctl -u k11c-fakevo` 有 `flips=60`，电视有画面
- 同一 WiFi 下 `http://<板子IP>:8000` 能看画面、键鼠能用
- 按 README「换槽升级」做一次 A→B 切换能起来
- 公网要重新认领（整包烧会丢 `/etc/k11c/cloud.json`），按 README「公网认领」做，这一项由用户决定做不做

## 做完的标准

- L0、L1、L2 全过，输出贴在 `REPORT.md`
- 在一个全新目录里只用 `bsp/README.md` 的步骤，从 `fetch.sh` 到 `updateimg` 跑通一遍
- `bsp/` 已拷回 `D:\win_game_project\32_3566_upgrade\bsp\`，提交到本仓库。推不推到 GitHub 问用户
- 本目录原有的 `README.md`、`patches/`、`sdk/`、`overlay/` 不删不改（它们是参考树的来源）。在原 `README.md` 开头加一行指向 `bsp/README.md` 即可

## 卡住时

- 某个组件找不到近的基线、A 层很大：照规则 2 拆完继续，在 `REPORT.md` 里写清楚是哪个组件、多大、试过哪些候选。不要为了凑小去改内容。
- L1 有差异：先看是不是权限、软链、行尾（CRLF）这类问题，再看是不是 blobs 漏了。不要靠改参考树来消差异。
- L2 有差异但 L1 已经过：查 `.config`、工具链 sha256、下载包 hash（Buildroot `dl/` 里的源码包要和参考编译用的是同一版）。
- 编译报错：先在参考树确认同一条命令能过。参考树也过不了，就是环境问题，不是 patch 问题。
- 有任何拿不准、会改变「和参考树一样」这个结论的取舍，停下来问用户。
