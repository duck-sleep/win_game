---
name: 2026-10-14 工作日志
description: Review project progress
metadata:
  type: project
---

# 2026-10-14 工作日志

## 目录清理复核（承接 10-13 的“哪些目录过期/可删”审查）

### `12_win_上机跑\porting\` 审查结论：**保留，是有效资产；但需加 README 标注**

- 性质：**2026-09-10 一天**的 xone(Xbox GIP) 驱动移植现场 —— 脚本 + 编译样本，共 19 文件 / 274KB
- 目标已达成，但**最终落地走的不是脚本里的路线**：
  - 实际落地 commit：VENDOR `e123d9d9f4b`「移植 xone GIP 驱动并打开 JOYSTICK_XONE_WIRED=m」
  - 最终形态：xone 源码在 `kernel_platform/{common,msm-kernel}/drivers/input/joystick/xone/`（已 commit），`kalama_GKI.config:579-580` 为 **=m**，模块进 `vendor_dlkm_staging/.../modules.load:124-126`
  - 脚本 `sync_xone.sh` 写的是 **=y（built-in）** → 与最终不符
  - 脚本 `defconfig_patch.sh` 会**关掉 XPAD** → 最终未采用，XPAD 保持 =y
- **重要发现：xpad 让路补丁最终未采用**（树里 xpad.c 干净、`xone_claim_needed` 已不存在）。
  原因：xpad 的设备表里只有 0x0a00/0x0a03/0x0a29 等雷蛇 PID，**根本没有 0x0a3f（Wolverine V3 Pro）**，
  xpad 压根不会 bind 它 → 无需让路。`patch_xpad.py` / `fix_xpad_order.py` / `xpad_letyou.patch` 属**历史探索**。
- 路径未失效：脚本里的 `LA.VENDOR.15.4.3` 是软链 → `LA.VENDOR.15.4.3-irix`（8月16 建链），可直接跑
- VM 侧 `/tmp` 还留着一批临时现场（xone_ko.tgz / patch_xpad.py / xone_Kconfig 等），属可清临时料

### 可复用 vs 已过期（porting 目录内）

- **可复用**：`insmod_xone_test.sh` / `run_xone_test.sh`（板子侧落盘 + panic 降级 + hello.ko 对照组 = 抗 adb 抖动的调试范式）；
  `build_xone_ko.sh` / `make_xone_ko.sh`（独立 O 目录只编 .ko 不碰主编译 out/）；`xone_Kconfig` / `xone_Makefile`（树内那份的备份）
- **已过期**：`sync_xone.sh` 的 =y 路线、`defconfig_patch.sh` 的关XPAD 路线、xpad 让路三件套、`xone_ko/` 里 4 个 09-10 的 .ko 样本
- **无关**：`_perm_check.py`（当时排查记忆文件可写性的小工具）；`_board_altmode.ko`（从板子拷回的第三方 ko，OTG/altmode 分析用）

## 咨询：同一台 VM 再编 RK356x/RK3588 Linux SDK，会不会把安卓环境搞坏？

用户给了 KICKPI 的 RK Linux SDK 编译文档（doc.kickpi.cn）。实测 VM 环境 + 读安卓构建脚本后结论：**不会互相破坏**。

VM 环境实测（10-14）：
- Ubuntu **22.04.5 LTS** / 内核 6.8.0-138 HWE / x86_64 / GNOME / `laide-virtual-machine` / 6核 43G / 1.3T 剩 **488G**
- ⚠️ `/usr/bin/python` **已 → python2**（手工链 `/usr/local/python2.7/bin/python2.7`，dpkg 不管；python2 与 python-is-python3 包都没装）
- 系统**无 java**（JAVA_HOME 空）；安卓自带 `prebuilts/jdk/{8,9,11,17}` → 装 openjdk-8 不影响安卓
- i386 架构**已启用**；**ccache 未装**

RK 文档风险点核对：
1. `sudo ln -s /usr/bin/python2 /usr/bin/python` → **VM 上已是该状态**，无需再动
2. 文档同时让装 `python-is-python3`（与上条矛盾）→ **建议跳过**；实测 `build_image_standalone.py`（安卓脚本第184/190行裸调 `python`）py2/py3 **双兼容**，但没必要引变量
3. `openjdk-8-jdk` → 安卓不用系统 java，无影响；22.04 源里未必有，装不上也无所谓
4. RK SDK **自包含工具链**（`prebuilts/gcc/`），`./build.sh` 在 SDK 根目录内跑，**不需要全局 export PATH/CROSS_COMPILE/ARCH** → 不会污染安卓
5. `sudo pip install pyelftools` → 22.04 会报 externally-managed，改 `pip3 install --user`

**唯一真实约束 = 磁盘**：RK 文档要求虚拟机磁盘 ≥200G；现在剩 488G（安卓 `out/` 还占 317G）。两工程并存会紧。→ 呼应之前"删 out/ 回收 317G"的决策。

**建议**：RK SDK 放独立目录（如 `~/Desktop/10_code/rk356x-linux`，别塞进 LA.VENDOR/LA.QSSI 内）；**绝不往 `~/.bashrc` 写 RK 的 export**；保持 `/usr/bin/python` 现状。

## 删 `out/` 前的安全审计（只读，脚本 `/tmp/audit_out.sh`）——结论：**可安全删除**

三棵树实测：

| 树 | out/ 体积 | out/ 内 git 跟踪文件 | git status | 结论 |
|----|----------|---------------------|-----------|------|
| VENDOR | 144G | **0** | 仅 `?? out/` | ✅ 安全 |
| QSSI | 166G | **0** | 仅 `?? out/` | ✅ 安全 |
| kernel_platform | 6.7G | **0** | 仅 `?? out/` | ✅ 安全 |

**不在 out/ 内（删不掉）的关键资产**：
- 5 个刷机包 zip（3.7G×5）→ VENDOR **树根** `SNM970_EQ000_..._260904/05/10/11/13_*.zip`
- 最终产物 36G → `vendor/vendorcode/build/`（含 `sparseimage/` `otapackage/` `super13/`）
- 内核预编译缓存 775M → `device/qcom/kalama-kernel/`（★删 Image 门控依赖它）

**out/ 里的 zip/img 都是中间产物**：`kalama-symbols-eng.laide.zip`、`otatools.zip`、`kalama-target_files-eng.laide.zip`、`userdata.img/vendor.img/dtbo.img/init_boot.img` 等 —— 全部可再生，**不是** MKT 刷机包。

⚠️ **`out/` 未被 .gitignore 忽略**（所以 `git status` 里显示 `?? out/`）。含义：删掉**不会有任何 git 损失**（本就未跟踪）；反而**降低 `git add -A` 误提交风险**。建议顺手把 `out/` 写进 VENDOR/QSSI 的 `.gitignore`。

### 🔴 删除前唯一要拍板的事：ff_bridge 修复没进任何包（时间线已钉死）

- 修复 commit：`603dc1a6001` @ **2026-09-14 20:31:04**（vendor 预置 ff_bridge + 开机桥去 `logcat -c` + sh 保活）
- 该 commit 改了：`hapticx_ff/{Android.bp,ff_bridge,hapticx_ff.rc,run_ff_bridge.sh}` + `kalama.mk`
- 最新刷机包 `260913` 生成于 **2026-09-13 12:04:46** → **早了 1 天 8 小时，包里是修复前旧版**
- 5 个包（260904/05/10/11/13）**全部不含**该修复
- ⚠️ 修复的**源码在 git 里安全**；"回不去"的只是**快速出包能力**（删 out/ 后要全量 6~8h 才能再出包）

### 删除命令（删前删后对照；无 make clean，rm -rf out 即规范做法）
```bash
rm -rf /home/laide/Desktop/10_code/LA.VENDOR.15.4.3-irix/out            # 144G
rm -rf /home/laide/Desktop/10_code/LA.QSSI.15.0-irix/out                 # 166G
rm -rf /home/laide/Desktop/10_code/LA.VENDOR.15.4.3-irix/kernel_platform/out  # 6.7G（可选）
```
删后：空闲 488G → ≈805G。

## 新工程：KICKPI K11C（RK3566）Linux SDK —— `D:\02_baidu` 下载件分类（共 100G）

**背景**：用户在 KICKPI 网盘下了 K11C 全套资料（100G），目标是**编译 Linux SDK**。他怀疑 Debian 那些用不上。
**板子**：KICKPI K11C = **Rockchip RK3566**（4×A55 2.0GHz / Mali G52 2EE / 1Tops NPU / 2~4G RAM / 16~64G eMMC / 千兆网 / 双频 WiFi）。官方支持 Android13 + Debian11 + Ubuntu20.04。

**★ 关键认知：有两条并列的 Linux 线（二选一，不是互补）**
- `linux/` = **内核 5.10 + Ubuntu20.04**（`使用说明(必读).txt` 原文）
- `linux-kernel-6.1/` = **内核 6.1 + Ubuntu24.04**

**分类结果**
| 类别 | 内容 | 大小 | 判定 |
|------|------|------|------|
| **编译必需（5.10 线）** | `linux/rk356x-linux-2026092909/`（tar.gz 12.7G + md5sum + release_sdk.sh） | 12.7G | ✅ 核心 |
| 编译必需（按需 rootfs） | `linux/rootfs/ubuntu-desktop/ubuntu-rootfs-kickpi-20260204.tar.gz`(1.33G) / `debian-desktop/linaro-rootfs-20251009.tar.gz`(1.38G) | 2.7G | ✅ 编哪个下哪个 |
| 另一条线（6.1） | `linux-kernel-6.1/rk-linux6.1-2026091606/` 6.0G + `buildroot-dl/` 260M | 6.3G | ⚠️ 只用 5.10 线则**可不下载** |
| **成品镜像（编译用不到）** | `Debian11`16G / `Debian12`19G / `Ubuntu2004`15G / `Ubuntu2404`27G | **77G** | ⚠️ 直接烧板用；每 OS 4 个 img，按 `V1.1/V1.2`（硬件版本）× `edp/multi`（屏幕）**最多只需 1 个** → 可省 ~58G |
| 烧录工具（Windows） | `DriverAssitant_v5.13`(9.3M 驱动) / `RKDevTool_v3.30`(45M 烧录) / `SDDiskTool_v1.78`(0.3M) / `balenaEtcher`(169M) | 0.2G | ✅ 留；SDDiskTool 与 Etcher 二选一 |
| 硬件文档 | `KICKPI-K11C（规格书+原理图+机械图）`36M / `RK3566-Datasheet` 5.7M | 0.04G | ✅ 留 |
| **冗余可删** | 根目录 `release_sdk_20260401.sh`（重复，每个 SDK 目录自带更新的 `release_sdk.sh` ver20260514；根目录无 tar.gz 跑了也无用） | 8K | ❌ |
| **冗余可删** | `linux/rootfs/ubuntu-desktop/历史版本/ubuntu-rootfs-kickpi-20251009.tar.gz` | 1.31G | ❌ 旧版 |
| **大概率无用** | `linux/rootfs/buildroot-dl/buildroot-dl_20250430.tar.gz` | 0.96G | ⚠️ 只编 buildroot 用（官方不维护） |
| **⚠️ 0 字节坏件** | 各 OS 目录里的 `根据主板上印刷的硬件版本选择镜像.txt*` | 0 | ⚠️ **空文件**，内容缺失需重下 |

**→ 只走 5.10 线的话：真正要留约 15G，其余 ~85G 可清**（但成品镜像重下受网盘限速，看用户取舍）

**编译流程要点**（据 doc.kickpi.cn）：
1. 把 `linux/rk356x-linux-2026092909/` 整个目录放到编译机同一级，`chmod +x release_sdk.sh && ./release_sdk.sh`
   → 脚本逻辑：**校验 md5 → 解压成同名目录 → 对解出的所有 git 仓 `git reset --hard`**
2. rootfs 严格命名：`rk356x-linux/debian/linaro-rootfs.img`、`rk356x-linux/ubuntu/ubuntu-rootfs.img`
3. `./build.sh lunch`（按实际列表选 K11C 的 defconfig）→ `./build.sh`
4. 镜像出在 `rockdev/`
5. 约束：**SDK 不能放共享目录**、**不能用 root 登录编译**、虚拟机磁盘 ≥200G

**与已有安卓工程的共存**：见本日志上一节 —— 不冲突，但**磁盘**是约束（VM 现剩 ~534G）。⚠️ 重申：**别装 `python-is-python3`、别动 `/usr/bin/python`**。

---

## 追加：官方文档关于「5.10 vs 6.1 是否维护」的实证（23:35）

**问题**：是不是必须走 6.1，因为只有 6.1 在维护？

**✅ 是。官方 Linux_SDK 文档原表（doc.kickpi.cn/Products/SDK-Compilation/RK356x-RK3588/Linux_SDK）**：

| SDK 版本 | 支持主板 | 是否维护 |
|---|---|---|
| Android 13 | RK356x-RK3588 全系列 | 否 |
| **Linux（=5.10 线）** | RK356x-RK3588 全系列 | **否** |
| Android 14 | 仅适配 K1 MINI / K11C / K8D / K8C | 是 |
| **linux-kernel-6.1** | 仅适配 K1 MINI / K11C / K8C / K8D | **是** |

**另一份官方页（Linux-Customization/Linux_Rootfs）给出系统配对表**（这条最关键）：

| SDK | 主板 | Debian | Ubuntu |
|---|---|---|---|
| `rk356x_linux`（5.10） | …K8D / **K11C** | Debian11 | Ubuntu20.04 |
| `rk-linux6.1` | K1MINI / K3B / K8D / **K11C** | **Debian12** | **Ubuntu24.04** |

→ 走 6.1 线 = 目标系统是 **Ubuntu24.04 或 Debian12**（这也解释了成品镜像 `Ubuntu2404/`、`Debian12/` 日期(20260731) 比 5.10 那批(20260730) 新）。

**6.1 SDK 包实测（tar 列举，非解压）**：
- 包内**只有一个 `.git/`，共 149 个条目**，无工作树文件 —— 是「裸仓 pack 投递」方式，靠 `release_sdk.sh` 里的 `git reset --hard` 展开工作树
- 主 pack：`pack-35648a81…pack` = **6,280,290,244 B（6.28G）**（源码全在里面）
- 单仓：`branch master` ← `origin/master`，remote = `ssh://gitea@192.168.199.226:2222/rockchip/rk-linux6.1.git`（Rockchip 内网，不可达，**别指望 fetch**）
- 标签：`rk-linux6.1-2026091606`（+ 旧 `rk-linux6.1-2026060914`）
- **md5 实测 `1d2c7c9480bbb48eedb91dab9ae0bb0f` = 官方 md5sum 一致 ✅**（下载完整，没被网盘截断）

**⚠️ 缺件风险**：6.1 线要配 **24.04 / Debian12 的 rootfs**；而现有 rootfs 都在 `

… （原文超出 WorkBuddy 读取上限 8000 字符，已按同一规则截断）
