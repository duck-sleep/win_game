# REPORT.md — BSP patch 拆分：基线选择、拆分明细与验收记录

参考树 = KickPI SDK HEAD `a11afccc2`（root 提交 `1f9d3a8`，2026-03-24 导入）+ 本目录 patches/sdk/overlay 改动（C 层，提交 `a51b80e0b`，10 文件 147 行）。
所有拆分在编译机 `~/k11c/bsp-work/` 完成；用户现用树 `~/k11c/rk-linux6.1-2026091606` 未动。

## 1. 基线打分（git archive 候选 vs SDK root 提交目录，diff --shortstat，改动行最少者胜）

| 组件 | 胜出基线 | 改动规模 | 落选候选 |
|---|---|---|---|
| external-rkwifibt | gitlab rockchip_linux_sdk_6.1/linux/external/rkwifibt master `a62092c02fce`（2025-11-03） | 6 文件 69+（仅 debian/ 包装目录，SDK 删掉） | radxa develop HEAD=2128 文件 2.2M 行；gitlab master HEAD=2789 文件；master@ab050ac6=270 文件 35k 行 |
| external-rktoolkit | gitlab linux/external/rktoolkit main `bc1d85d6`（2022-08-23） | **完全相同**（A 层空） | — |
| external-rkupdate | gitlab linux/external/rkupdate main `bf7b5fa4`（2023-07-05） | 4 文件 81+ 717- | — |
| external-recovery | gitlab linux/recovery main `dde564dd`（2023-11-09） | 8 文件 22+ 124- | — |
| external-gstreamer-rockchip | gitlab linux/gstreamer-rockchip main `ed9f8286`（2023-12-20） | 21 文件 272+ 550- | — |
| external-mpp | github rockchip-linux/mpp develop `958803d7` | 10 文件 770+ 12- | — |
| external-linux-rga | gitlab linux/linux-rga multi_rga_im2d_api `4c7a04b3`（2026-03-23，导入前最后提交） | 98 文件 4134+ 310- | multi HEAD aa2a0f90=67 文件 5781+ 1225-；develop_c=93 文件 7.8k；main=204 文件 30k |
| tools（仅 Linux_Pack_Firmware） | gitlab linux/tools main `972d879d`（唯一分支，2021 冻结） | 子集内仅新增芯片打包文件 + afptool/rkImageMaker 二进制不同 | GitHub 无 rockchip-linux/tools 仓库 |
| sdk-top（根文件） | **empty**（KickPI 私有根文件，无公开对应；全为软链+.gitignore，A 层 1 patch） | 全量新增 | — |
| kernel-6.1 | gitlab rk/kernel-stable linux-6.1-stan-rkr7 `b4ef083d`（2025-12-26，分支 HEAD 即导入前最后提交） | 48 文件 1343+ 2- | rkr7.1 HEAD=51 文件 1566+ 310-；rkr6.2=547 文件 8120+ 84870-；gh develop-6.1 HEAD=5127 文件 156k+ 77k-；不用 kernel.org 6.1.141（任务书禁止） |
| u-boot | gitlab android/rk/u-boot next-dev `b028de20`（2026-03-24 导入前最后提交） | 133 文件 4049+ 16810- | github next-dev HEAD=387 文件 34269+ 35836-；gitlab main=778 文件 272k- |
| buildroot | gitlab linux/buildroot rockchip/2024.02 `d92da2a3`（导入前最后提交） | 153 文件 2495+ 2307- | radxa rockchip/2024.02 HEAD=738 文件 29k 行；gitlab main=14879 文件 380k 行（错分支） |
| device-rockchip | gitlab linux/device/rockchip rk3566_rk3568 `a6ba9949`（导入前最后提交） | 136 文件 823+ 2195- | master@import=481 文件 12187+ 435-；gitlab main=1132 文件 67k 行；radxa rk3588-linux-6.1=946 文件 4847+ 74618- |
| rkbin（9 文件子集） | github rockchip-linux/rkbin master `8adadbca`（2026-03-16，bl32 v2.16 被 v2.17 替换前最后提交） | 子集 7/9 完全相同；A 层 1 行 ini 改动 + boot_merger 二进制不同（进 blob） | master@015f185f（导入日）=3/8 不同（bl32 已升 v2.17）；master HEAD=4/8 不同（打分按当时 8 文件子集） |
| prebuilts（仅 gcc-arm-10.3-2021.07 aarch64-none-linux-gnu） | 官方 ARM tarball（developer.arm.com，sha256 `1e33d53d…`，116,348,148 B） | 官方文件 0 改动；差异=纯新增（34 个 rockchip 别名软链 + 2 脚本 + runtime_lib/） | Buildroot 用内部工具链（BR2_TOOLCHAIN_EXTERNAL 未开），其余 prebuilts 不在范围 |

## 2. 拆分明细（最终组装 assemble-bsp.py，2026-11-19）

共 **220 个 patch + 25 个 blob**（另有 7 条 blob 删除记录），bsp/ 总体积 **79 MB**（其中 rkwifibt 的 Realtek 驱动 B 层占 41 MB）。

| 组件 | A | B | C | blobs | patches 体积 | blobs 体积 |
|---|---|---|---|---|---|---|
| kernel-6.1 | 1 | 50 | 2 | 1 | 3.0 MB | 0.3 MB |
| u-boot | 1 | 5 | 1 | 1 | 0.47 MB | 4 KB |
| buildroot | 19 | 2 | 2 | 0 | 0.41 MB | — |
| device-rockchip | 8 | 34 | 2 | 8 | 0.38 MB | 0.84 MB |
| sdk-top | 1 | 7 | 0 | 0 | 12 KB | — |
| external-mpp | 1 | 0 | 1 | 1 | 39 KB | 0.76 MB |
| external-linux-rga | 1 | 0 | 0 | 0 | 0.23 MB | — |
| external-gstreamer-rockchip | 1 | 0 | 0 | 0 | 70 KB | — |
| external-rktoolkit | 0 | 0 | 0 | 0 | 基线完全相同 | — |
| external-rkwifibt | 1 | 73 | 0 | 17 | 41 MB | 1.15 MB |
| external-recovery | 1 | 2 | 0 | 0 | 21 KB | — |
| external-rkupdate | 1 | 0 | 0 | 0 | 43 KB | — |
| rkbin（9 文件子集） | 1 | 0 | 0 | 1 | 5 KB | 2.4 MB（boot_merger） |
| tools（Linux_Pack_Firmware） | 1 | 0 | 0 | 2 | 31 KB | 4.0 MB |
| prebuilts（gcc-arm-10.3） | 1 | 0 | 0 | 1 | 25 KB | 23 MB（lib.tar.bz2） |

已知例外（单文件 >1MB，单独成 patch，任务书允许）：external-rkwifibt 9 个 Realtek 头文件/固件源码
（halmac_bit2.h 3.0MB、halmac_bit_8814b.h 1.38MB、halhwimg8822c_rf.c 1.42MB、hal8822c_fw.c 3.7MB、
hal8821c_fw.c 3.57MB 等，完整清单见 bsp/assemble-report.json）。
rkwifibt B 层 41MB 为 KickPI 一次性导入 rtl88x2CS 驱动的原始提交拆分，按「不改内容」硬规则无法再压缩；
A 层均 <20MB，无需换更近基线。

## 3. 参考固件（第 1 步，ref/ 树，2026-11-19）

- 4 个目标全部 rc=0：uboot(10:19) rootfs(11:46) firmware(11:46) updateimg(11:46)。
- update.img：281,674,314 B，md5 `ebc005b0f379da63a5acea1f55c3cee1`（整镜像 md5 不作为验收项，仅记录）。
- package-file 分区表 = README 8 行（uboot/boot_a/boot_b/oem/system_a/system_b/userdata + misc 见 parameter）。
- ref-out/ 已收集：parameter.txt、MiniLoaderAll.bin、三个 .config、dtb、build/ 包列表（129 个）、target/ 清单（4049 文件）。

## 4. 验收输出

**最终三关原始输出（第 8 轮，2026-11-21~22，同路径重编树）**

L0（`check-l0.sh bsp`，bsp-accept 权威树）：

```text
[L0] 例外(单文件>1MB, 3017342B): patches/external-rkwifibt/0019-b-feat-wifi-add-rtl88x2CS-driver-part-18-53.patch
[L0] 例外(单文件>1MB, 1162446B): patches/external-rkwifibt/0021-b-feat-wifi-add-rtl88x2CS-driver-part-20-53.patch
[L0] 例外(单文件>1MB, 1383706B): patches/external-rkwifibt/0022-b-feat-wifi-add-rtl88x2CS-driver-part-21-53.patch
[L0] 例外(单文件>1MB, 1024191B): patches/external-rkwifibt/0023-b-feat-wifi-add-rtl88x2CS-driver-part-22-53.patch
[L0] 例外(单文件>1MB, 1152168B): patches/external-rkwifibt/0025-b-feat-wifi-add-rtl88x2CS-driver-part-24-53.patch
[L0] 例外(单文件>1MB, 1164806B): patches/external-rkwifibt/0026-b-feat-wifi-add-rtl88x2CS-driver-part-25-53.patch
[L0] 例外(单文件>1MB, 1422039B): patches/external-rkwifibt/0035-b-feat-wifi-add-rtl88x2CS-driver-part-34-53.patch
[L0] 例外(单文件>1MB, 3699969B): patches/external-rkwifibt/0039-b-feat-wifi-add-rtl88x2CS-driver-part-38-53.patch
[L0] 例外(单文件>1MB, 3568322B): patches/external-rkwifibt/0041-b-feat-wifi-add-rtl88x2CS-driver-part-40-53.patch
[L0] patch 总数: 220
[L0] blobs sha256 OK (25 个)
[L0] 白名单命中(驱动调试串,非秘密): patches/external-rkwifibt/0052-b-feat-wifi-add-rtl88x2CS-driver-part-51-53.patch:18303
[L0] 白名单命中(驱动调试串,非秘密): patches/external-rkwifibt/0004-b-feat-wifi-add-rtl88x2CS-driver-part-3-53.patch:4866
[L0] 秘密扫描: 白名单命中 2/2, 白名单外命中见上(无输出=0)
[L0] bsp 总体积: 79 MB
L0_PASS
```

L1（`apply.sh`×2 → `verify-tree.sh`×2 对 ref-clean，15 组件全点名 OK）：

```text
verify1 rc=0
verify2 rc=0
L1_PASS_IDEMPOTENT
```

同路径重编各目标与逐字节核对（samepath2-run.log）：

```text
select rc=0 / uboot rc=0 / rootfs rc=0
chrony-dirclean rc=0 / chrony-epoch rc=0 / rootfs2 rc=0
CHRONYC_BYTE_SAME
CHRONYD_BYTE_SAME
SYSTEMMAP_BYTE_SAME
firmware rc=0 / updateimg rc=0
```

L2（`compare-build.sh` 全量，末行 **L2_PASS**）：

```text
[L2] OK parameter.txt
[L2] OK MiniLoaderAll 仅时间字段+校验和 (7 字节差异)
     0x0E-0x14 打包时间: ref=2026-11-19 10:19:23 new=2026-11-21 23:20:46
     末尾4字节校验和: ref=17e87153 new=54daf753
[L2] OK kernel .config
[L2] OK u-boot .config
[L2] buildroot .config 哈希注释行: # Buildroot -ga51b80e0b Configuration -> # Buildroot -g77d125acd Configuration
[L2] OK buildroot .config 仅哈希注释行
[L2] OK dtb
[L2] OK build/ 包列表 (129 个)
[L2] OK target/ 清单
[L2] target 逐字节相同: 2839, 软链相同: 643
[L2] target 规则命中: pyc-mtime=557 gz-mtime=0 os-release-meta=2 shadow-salt=1 elf-timestamp=4 elf-build-id=3
[L2] 无法解释: 0
[L2] OK package-file 分区表
L2_PASS
```

MiniLoaderAll 的 7 个字节（已批准豁免的明确口径）：偏移 0x0E–0x0F = 打包年份(LE)、0x10 = 月、
0x11 = 日、0x12 = 时、0x13 = 分、0x14 = 秒（本轮 ref=2026-11-19 10:19:23 vs new=2026-11-21 23:20:46，
差异落在其中 7 字节）；末尾 4 字节为整体校验和（17e87153 → 54daf753），随时间字段联动，同样属已批准范围。

**秘密扫描白名单（写死三要素，用户 2026-11-20 批准）**：任务书 L0 要求秘密关键词扫描为空。
Realtek rtl88x2CS 驱动源码自带 2 行调试打印格式串（RTW_INFO / RTW_PRINT_SEL，带 %x 占位符的模板，
B 层原样保留 KickPI 提交），会命中任务书的 WiFi 密码关键词。它不是填好的密码；按「不改参考内容」
硬规则保留原文。白名单**只认这 2 行**：路径 + 行号 + 该行 sha256（含前导 `+`、不含行尾换行）
三样全对上才放过，其余任何命中一律 FAIL，不按关键词/目录整片忽略。
已验证 ref-clean 对应位置存在同内容（patch 行去掉前导 `+` 后与源行逐字节一致）：

| patch 文件（bsp/ 相对） | 行号 | 该行 sha256 | ref-clean 对应位置 |
|---|---|---|---|
| patches/external-rkwifibt/0052-b-feat-wifi-add-rtl88x2CS-driver-part-51-53.patch | 18303 | bacf1c0b4a5e423629ae359c54e88c140a08e6033fdb190c53f3b22afbba924d | external/rkwifibt/drivers/rtl88x2CS/os_dep/linux/ioctl_linux.c:6185 |
| patches/external-rkwifibt/0004-b-feat-wifi-add-rtl88x2CS-driver-part-3-53.patch | 4866 | 8e480391756639ac89b5d3516bd6f01a08b38b28842f272a0028f9dbf4cfd736 | external/rkwifibt/drivers/rtl88x2CS/core/rtw_debug.c:4823 |

真正的秘密（cloud.json/填好的 WiFi/私钥）0 命中。

全量预验收（15 组件，test-full：基线取自打分仓库的 baseline 提交）：**L0_PASS + L1_PASS**。
- L0：220 patch 全部有 Origin、无二进制标记、series↔文件 1:1、≤100 文件/patch；25 blob sha256 全过；秘密扫描 0 真命中。
- L1：15 组件逐目录 `diff -r --no-dereference --exclude=.git` + 权限/类型/软链清单比对全空（rkbin/tools 按子集）。
期间修复：A patch 需组件相对路径重生成；CRLF 源文件需 am.keepcr=true；blob 删除后清空目录。

**rkbin 子集修正（验收第 5→6 轮）**：第 5 轮真实 fetch→apply×2 已 L1_PASS_IDEMPOTENT，但编 uboot 时
`loader.sh: ./tools/boot_merger: No such file or directory`（rc=127）。根因：u-boot/make.sh 的
`pack_loader_image()` 先 `cd ${RKBIN}` 再调 loader.sh，所以 `./tools/boot_merger` 指的是
**rkbin/tools/boot_merger**（不是 u-boot/tools/，后者根本没有这个二进制，只有源码且 .gitignore 忽略）。
原子集只取了 tools/mkimage，漏了它。参考编译四目标日志证实 rkbin/tools 只被执行 mkimage（kernel boot.img FIT）
和 boot_merger（MiniLoaderAll）两个；trust_merger/loaderimage 仅非 FIT 流程用（本配置 FIT=y 不走），
rk_sign_tool/setting.ini 仅 security 流程（未开）。子集扩为 9 文件（+tools/boot_merger），
重拆 rkbin A 层（1 ini patch + 1 boot_merger blob，GitHub 基线的 boot_merger 与 SDK 内容不同），
scope.txt 依据节同步更新。教训：子集裁剪不能只看 ini 引用，要按编译日志里实际执行的工具核对；
L1 子集比对只比子集内的文件，子集外的缺失要靠真实编译（L2）才暴露。
全新目录真实 fetch→apply→build→L2 验收见 bsp-accept；最终三关原始输出见本节开头。

## 5. L2 豁免规则（窄规则判定，不按文件名单；用户 2026-11-20 批准）

**先消差异再豁免**：第 6 轮验收树在 `/home/rk/k11c/bsp-accept/tree`（与参考根差 3 字符），
路径差导致 .ko 大小、patchelf X 填充、sysconfigdata.pyc、BR2_DEFCONFIG 行等差异。
第 7 轮把参考树原样挪到 `ref-orig/`（内容不改），全新 apply×2 的树放进**同一绝对路径**
`/home/rk/k11c/bsp-work/ref` 重编四目标，路径衍生差异随之消失。消不掉的按下列窄规则判定，
`scripts/l2-rules.py` 逐文件套规则，套不进 = 无法解释 = L2_FAIL，不临时加规则。

| 规则 | 允许的差异 | 必须相同 |
|---|---|---|
| MiniLoaderAll | 0x0E–0x14 共 7 字节打包时间（0x0E-0x0F 年 LE、0x10 月、0x11 日、0x12 时、0x13 分、0x14 秒）+ 末尾 4 字节校验和 | 其余全部字节、magic "LDR "、文件大小 |
| buildroot .config | 仅 `# Buildroot -g<哈希> Configuration` 注释行（git HEAD 短哈希，apply 生成新提交故不同） | 其余所有行（含 BR2_DEFCONFIG，同路径后一致） |
| pyc | 仅头部第 8–12 字节（源文件 mtime） | magic、flags、源文件大小（头 0–8、12–16 字节）、第 16 字节起正文 |
| gz | 仅头部第 4–8 字节 mtime | 其余头部、压缩体；且两边解压后内容逐字节相同 |
| os-release | 仅 VERSION=-g<git短哈希> 行、RK_BUILD_INFO 行内时间戳 | 其余所有行 |
| shadow | 仅密码字段（$5$盐$哈希），且用同一密码（.config BR2_TARGET_GENERIC_ROOT_PASSWD）crypt 校验两边都通过 | 用户名、其余所有字段、其余行 |
| ELF / .ko | 差异字节只落在日期/时间/git哈希格式的 C 串内（串归一化后两边相同；串内允许 \t\n\r） | 文件大小、每个段大小、段名/类型、.text 逐字节 |
| .note.gnu.build-id（ELF 派生） | 仅 build-id 段 desc 的 20 字节（段偏移 16..35） | 段头 16 字节、desc 之后到段尾、文件大小、每个段大小、.text 逐字节；且其余差异字节必须已套进上面的 ELF 串规则（用户 2026-11-21 批准；不写成文件名单，任何 ELF 套不进即 FAIL） |

日期/时间/git 格式白名单（l2-rules.py PATS）：`20\d\d-\d\d-\d\d`、`\d\d:\d\d:\d\d`、
`[A-Z][a-z]{2} [A-Z][a-z]{2} +\d+ \d\d:\d\d:\d\d [A-Z]+ 20\d\d`、
`[A-Z][a-z]{2} [A-Z][a-z]{2} +\d+ \d\d:\d\d:\d\d 20\d\d [A-Z]+`（OpenSSL "built on" 格式，年在时区前）、
`[A-Z][a-z]{2} +\d+ 20\d\d at \d\d:\d\d:\d\d`、`[A-Z][a-z]{2} +\d+ 20\d\d`、`-g[0-9a-f]{7,40}`。

compare-build.sh 末尾打印每条规则命中数与「无法解释: N」。第 8 轮最终原始输出见 §4。

**第 7 轮同路径重编结果（2026-11-20）**：4049 个 target 文件中 2836 逐字节相同、643 软链相同；
规则命中 pyc-mtime=557、os-release-meta=2、shadow-salt=1、elf-timestamp=3（含 libcrypto，
其 "built on" 串属已批准的日期/时间串规则，仅格式表补了 OpenSSL 写法）；gz-mtime=0（同路径后全同）。
路径差消除后新增消失项：sysconfigdata.pyc（归入 pyc 规则）、BR2_DEFCONFIG 行、patchelf X 填充、
.ko 大小差（3 个 .ko 现在大小/段大小全同）。剩 7 个无法解释，根因全部查实，分 3 组：

| 组 | 文件 | 根因（已验证） | 处置（用户 2026-11-21 拍板：先消差异，加规则从严） |
|---|---|---|---|
| 1 git 元数据长度 | info/System.map-6.1、python.o | ① git 自动短哈希长度：参考 SDK 仓库对象多→9 位（a51b80e0b），apply 新仓库→7 位（5d46a0d）。Buildroot gcc 把 `-g<哈希>` 编进 pkgversion（gcc.mk --with-pkgversion="Buildroot $(BR2_VERSION_FULL)"，Makefile:149 setlocalversion→git rev-parse --short），python.o 未 strip，.comment 差 2 字符→文件差 8 字节。② 内核 mpp 驱动 Makefile 用 `git log -1 --pretty="%h author: %<\|(30)%an %cd %s" -- mpp目录` 把 git 信息编进 .rodata：参考=SDK 提交 1f9d3a813/tanzh/"feat: init linux6.1 sdk on 202603024"（71 字节×2 处），重建=baselines 提交 7957e5f/bsp-apply/"baselines (versions.lock)"（62 字节×2 处）→.rodata 差 32 字节→System.map 地址整体平移 | **消，不加规则**：apply.sh 设 `core.abbrev=9`；baselines 提交的作者名/邮箱、作者日期、提交日期、说明全用 SDK 根提交 1f9d3a8 原值（该提交内容就是这份基线）。判据：System.map-6.1 逐字节相同；python.o 只剩哈希内容差且大小/.text 相同（现有 ELF 规则覆盖）。对不上就停、贴剩余差异字节 |
| 2 chrony 编译期常数 | usr/bin/chronyc、usr/sbin/chronyd | chrony configure 把 `NTP_ERA_SPLIT=(configure时刻unix秒-18250天)` 写进 config.h（参考 1795104796、重建 1795154378，差 49582 秒=两次 configure 时刻差）。它是数值常数，编译器展开成 .text 的 MOVZ/MOVK 立即数和 .rodata 数值表，不是字符串，现有规则盖不住 | **先消**：chrony configure 原生支持 `SOURCE_DATE_EPOCH`（split_seconds 直接取该值），用它**只包 chrony 的 configure**（make 命令行覆盖 CHRONY_CONFIGURE_CMDS，不改源码/patch；等效且比 faketime 稳）。已在第 7 轮树实测：dirclean→注入重建→增量 rootfs（strip 在 target-finalize）后 chronyc/chronyd 与参考**逐字节相同**，则**不加规则**。压不住才允许一条只归这两个文件、只放行 NTP_ERA_SPLIT 立即数差的窄规则 |
| 3 内核模块 build-id | 88x2cs.ko、bcmdhd.ko、bcmdhd_pcie.ko | 各 27 字节差异 = 20 字节 .note.gnu.build-id（段首 off 0x40，desc@80..99，二进制内容哈希，随时间戳串而变）+ 7 字节日期/时间串数字（已属现有规则）。性质同已批准的 MiniLoaderAll 校验和 | **批准加窄规则**（已实现进 l2-rules.py，计数 elf-build-id）：只放行 build-id desc 20 字节；前提=文件大小相同、每个段大小相同、.text 逐字节相同、其余差异字节已套进现有日期/时间串规则。不写成「这三个 .ko 可以不同」。篡改负测试：改段头/串外字节→FAIL |

工程注脚（chrony 注入三步曲，缺一步都会假阴性）：`chrony-rebuild` 不重跑 configure；
make 命令行变量里 `$(@D)` 不展开（须写死构建目录路径）；`make chrony` 不触发 target-finalize，
装的二进制未 strip（须再走一遍 `./build.sh rootfs` 增量）。README 步骤 8.5 已记录该注入命令。

**第 8 轮最终结果（2026-11-22，同路径 + 组1消除 + 组2锚定 + 组3窄规则）**：4049 个 target 文件
2839 逐字节相同、643 软链相同；差异 567 个全部套进规则：pyc-mtime=557、os-release-meta=2、
shadow-salt=1、elf-timestamp=4（busybox、libpython、libcrypto、python.o——组1 生效后 python.o
只剩哈希内容差，大小/.text 全同）、elf-build-id=3（88x2cs.ko、bcmdhd.ko、bcmdhd_pcie.ko）；
**无法解释=0，L2_PASS**。chronyc/chronyd/System.map 三项与参考逐字节相同（消除，非豁免）。

**Clean-room 复现（11-22，参考树已按用户指令清理后）**：VM 全新目录 `git clone`（GitHub）→ `fetch.sh`
（真联网拉公开基线，11 分钟）→ `apply.sh`（2 分钟）→ select/uboot/rootfs/chrony 锚定/rootfs2/firmware/
updateimg 全 rc=0（约 1h43m，零手改）。对第 8 轮 target 基线（3406 个普通文件 sha256 清单，
`repro-baseline/target-sha-round8.txt`）做 `sha256sum -c`：2791 一致 + 615 不一致，逐类归因全为已知：
567 = 每次编译必然变化的时间戳/哈希/盐/build-id 类（即上面的规则命中集）；43 = **绝对路径内嵌类**
（40 个正是第 6 轮 bin-strings/bin-strseq 名单：__FILE__/调试串/patchelf 区随构建路径而变，
+ libstdc++-gdb.py 与 python config Makefile 两文本 + shadow 盐计数重叠）——本次复现故意用了不同目录
（`repro-work` vs `bsp-work`），差异按预期回归。**System.map-6.1、chronyc、chronyd 三个锚定文件逐字节一致**。
结论：同事在新机器全流程可复现出可烧写固件（L3 已验板）；若要产物与参考逐字节对照，须按 §5 口径
同绝对路径重编（路径内嵌类差异无法用规则外的手段消除，也不该为此改源码）。

## 6. 体积

check-l0 口径 bsp/ 总体积 **79 MB**（VM `du -sh` = 77 MiB），满足任务书「几十 MB」目标。
大头：patches/external-rkwifibt 40 MB（Realtek 驱动 B 层）、blobs/prebuilts 23 MB（工具链 runtime_lib）、
blobs/tools 3.9 MB（afptool/rkImageMaker）、patches/kernel-6.1 3.0 MB、blobs/rkbin 2.4 MB（boot_merger）。
各组件 patch/blobs 体积见 §2 表。blob 共 25 个文件（SHA256SUMS 全过）+ 7 条删除记录（manifest D 行）。