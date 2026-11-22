---
name: k11c-bsp-split-line
description: K11C BSP patch 拆分（32_3566_upgrade）：220 patch+25 blob 79MB；L0 白名单 2/2 PASS；第8轮=用户拍板三组处置（abbrev=9+SDK原署名/chrony SOURCE_DATE_EPOCH 锚定/build-id 窄规则），重编验收进行中
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

## 进度（2026-11-19 深夜~11-20，任务 1~6 全完成，7 进行中）

- **15/15 基线锁定**（权威文件 = Windows `bsp/versions.lock`，打分记录在 VM `bsp-work/scoring-results.txt` + REPORT.md §1）。
  关键胜者：kernel = gitlab rk/kernel-stable **linux-6.1-stan-rkr7** `b4ef083d`（48 文件差，远胜 rkr6.2/rkr7.1/gh）；
  u-boot = gitlab android/rk/u-boot next-dev `b028de20`；buildroot = gitlab rockchip/2024.02 `d92da2a3`；
  device = gitlab **rk3566_rk3568 分支** `a6ba9949`（136 文件，master 481 落选）；
  rkbin = github master `8adadbca`。**rkbin 选基线的窍门**：SDK 用的 bl32 v2.16 在 2026-03-16 被上游 v2.17 替换删除，
  取删除提交 `94a1b15` 的**父提交**即 7/8 子集全同（导入日 HEAD 反而 3/8 不同）——选"SDK 所用文件版本被替换前"的提交，不是机械取导入日。
- **三层拆完**：220 patch + 25 blob（+7 删除记录），bsp/ 共 79MB（rkwifibt Realtek 驱动 B 层占 41MB，9 个单文件 >1MB 例外已列 REPORT）。
  **全量 L0_PASS + L1_PASS**（15 组件内容+权限+软链 vs ref-clean 全一致；test-full）。
- bsp/ 已拷回 Windows（blob sha256 全过）；加了 `bsp/.gitattributes`（`* -text`）——**仓库 core.autocrlf=true，
  不加会把 patch 里故意保留的 CRLF 和 blob 搞坏**；原 README.md 顶部已加指针行（任务书唯一允许的原文改动）。
- **验收重建在 VM `~/k11c/bsp-accept/`**（全新目录真实网络 fetch→apply×2 幂等→编 4 目标→compare-build L2），
  脚本 accept-run.sh，日志 fetch.log/accept-run.log/build-*.log/l2.log。第一次跑 APPLY1_FAIL：
  **versions.lock 旧副本**——VM 上有四处副本（bsp-work 根 / deliver-scripts / bsp-final / bsp-accept/bsp），
  我只同步了 deliver-scripts。**教训：改权威清单后必须同步全部副本再跑**（已修，重跑中，挂了 Monitor 盯里程碑）。
- 口径备忘：① L0 秘密扫描 2 处驱动调试串命中 → **用户 11-20 批准算误报，但白名单写死三要素**（路径|行号|该行sha256，
  已验证 ref-clean 同内容；check-l0.sh 三样全对才放过，其余一律 FAIL，负向测试过；L0_PASS 2/2；REPORT §4 有表）。
  ② 仓库 overlay/ 只有 .example（干净），VM `~/k11c/k11c-br-overlay` 有用户填好的真实 WiFi conf（不进仓库）；
  验收编译用 VM overlay = 与参考编译同口径，L2 才能全同。
- ssh 启动 setsid 后台任务的命令常挂到超时被转后台（任务本体正常启动）；轮询类 ssh 正常。别误判为失败，pgrep 核实。
- **坑：tsv 末行无换行被 `while read` 吞掉**（11-20）——components.tsv/versions.lock 最后一行（prebuilts/sdk-top）无 \n，
  apply 漏铺 prebuilts、verify 漏检它 → **假 L1_PASS**，编译才炸（get_toolchain 找不到 aarch64 目录）。
  已双层修：文件补 \n + 所有 tsv read 循环加 `|| [ -n "$comp" ]`。教训：清单文件必须尾换行；read 循环要末行保护；
  L1 脚本自己也可能漏检，验收要看"每个组件都被点名"而不是只看 PASS。
- 验收编译第二次失败 = build.sh 要 sudo 而后台无 tty：accept-build.sh 需 `export PATH=/tmp/.sudoexec/bin:$PATH SUDO_ASKPASS=/tmp/.sudoexec/ap.sh`（同 step1-build.sh）。
- **坑：文件权限口径**（11-20 第四/五轮）——参考树全树只有 664/775 两种（VM umask 002 的 git 检出）；
  tarball 原样权限、别的机器 umask 022 检出 644/755 都会让 L1 的 %m 清单 FAIL（diff -r 不比权限，只有清单比）。
  第一版修 fetch.sh 归一 644/755 方向反了。**最终修：apply.sh 末尾全树归一 664/775**（保留 x 位，软链不动），
  与 umask 无关、任何机器重建一致。教训：先 `find -printf %m | uniq -c` 看参考树真实口径再定归一目标。
- **坑：rkbin 子集太窄**（11-20 第五轮验收 uboot rc=127）——`loader.sh: ./tools/boot_merger` 找不到。
  根因：u-boot/make.sh `pack_loader_image()` 先 `cd ${RKBIN}` 再调 loader.sh，`./tools/` = **rkbin/tools/**，
  不是 u-boot/tools/（那里只有 boot_merger.c 源码，二进制被 .gitignore 忽略，从来不存在）。
  参考编译日志证实 rkbin/tools 只执行 mkimage + boot_merger 两个（trust_merger/loaderimage 仅非 FIT 流程，
  rk_sign_tool/setting.ini 仅 security）。子集 8→9 文件（+tools/boot_merger，GitHub 基线内容与 SDK 不同→blob 2.4MB）。
  教训：① 子集裁剪要按编译日志实际执行的工具核对，不能只看 ini 引用；② L1 子集比对只比子集内文件，
  子集外缺失只有真实编译才暴露；③ 脚本里的相对路径要先看调用者 cd 到了哪。
  修复后 L0_PASS（权威计数 **220 patch + 25 blob** + 7 删除记录，79MB；旧 REPORT 头行 219/24 是笔误，表格一直对）。
- **第 6 轮完成**（bsp-accept，异路径）：L1_PASS_IDEMPOTENT + 四目标 rc=0；L2 差异 617 文件全归类证认为编译元数据
  （556 pyc/gz 仅 mtime 头、55 ELF 归一化有序串序列全同、5 文本、1 sysconfigdata.pyc 反序列化字节码+行号全同；OTHER=0）。
  证据留档 `bsp/l2-excludes-evidence.md`（**脚本不准读它来豁免**，用户明令）。X 填充根因 = patchelf 0.13 清 RUNPATH
  时 memset 旧串为 'X'（patchelf.cc:1547），长度=原路径串长。
- **用户 11-20 拍板 L2 口径**（否掉文件名单豁免）：先同路径重编消差异，再按窄规则判（pyc/gz/os-release/shadow/ELF/.config/
  MiniLoaderAll 各有字节级规则，详见 REPORT §5 + scripts/l2-rules.py）；套不进=FAIL，加规则先问。通用规矩见 [[feedback-narrow-exemption-rules]]。
- **第 7 轮完成 + 8 个无法解释全部查实**（11-20~21）：L1_PASS_IDEMPOTENT、四目标 rc=0。同路径后规则命中
  pyc-mtime=557/os-release=2/shadow=1/elf-timestamp=3（libcrypto "built on" 补了 OpenSSL 日期格式进 PATS）。
  根因三组：①System.map+python.o=git 短哈希长度差（SDK 仓库对象多自动 9 位，apply 新仓库 7 位）+
  内核 mpp Makefile 把 `git log -1 -- <mpp目录>` 编进 .rodata（参考=SDK 提交 tanzh/原主题 71 字节×2，
  重建=baselines 提交 62 字节×2 → .rodata 差 32B → 地址平移）。②chronyc/chronyd=configure 把
  `NTP_ERA_SPLIT=(configure时刻-18250天)` 编成数值常数（非字符串）。③3 个 .ko 各 27 字节差=20 字节
  .note.gnu.build-id + 7 字节日期数字。
- **用户 11-21 拍板三组处置**："先做能消掉的，再加规则；加完之前不许报 L2_PASS；输出必须『无法解释: 0』"。
  ①组1 **消，不加规则**：apply.sh 设 `core.abbrev 9` + baselines 提交作者/邮箱/作者日期/提交日期/说明全用
  SDK 根提交 1f9d3a8 原值（tanzh|981431410@qq.com|2026-03-24T13:02:55+08:00|"feat: init linux6.1 sdk on 202603024"）。
  判据：System.map 逐字节相同；python.o 只剩哈希内容差且大小/.text 同（现有 ELF 规则覆盖）。②组2 **先消**：
  chrony configure 原生支持 `SOURCE_DATE_EPOCH`（=1795104796 参考 configure 时刻），make 命令行覆盖
  CHRONY_CONFIGURE_CMDS 只包它的 configure，不用 faketime、不改源码——**已在第 7 轮树实测 chronyc/chronyd
  与参考逐字节相同** → 不加规则。③组3 **加窄规则**（已实现 l2-rules.py，计数 elf-build-id）：只放行 build-id
  desc 20 字节；前提=大小/段大小/.text 全同、其余差异已套现有规则；负测试（段头/串外篡改）FAIL。
- **chrony 注入三个坑**（缺一不可，都踩过）：`chrony-rebuild` 不重跑 configure（要 dirclean+完整重建）；
  make **命令行变量里 `$(@D)` 不展开**（要写死构建目录字面路径）；`make chrony` 不触发 target-finalize
  （装的未 strip，须再 `./build.sh rootfs` 增量补 finalize+镜像）。README 步骤 8.5 已记录该命令（非默认流程，
  仅"与参考逐字节一致"需要）；REPORT §5 有工程注脚。
- **第 8 轮完成**（11-22 00:47，三关全绿）：L1_PASS_IDEMPOTENT；组1 机制实测生效——core.abbrev=9、
  HEAD 短哈希 9 位、mpp 串 78 字节与参考完全同长（tanzh/原日期/原主题）；select/uboot/rootfs/
  chrony-dirclean/chrony-epoch/rootfs2/firmware/updateimg 全 rc=0；**CHRONYC/CHRONYD/SYSTEMMAP
  与参考逐字节相同**（组1、组2 纯靠消，没加规则）。全量 compare-build：**L2_PASS，无法解释=0**；
  命中 pyc-mtime=557/gz=0/os-release=2/shadow=1/elf-timestamp=4（busybox/libpython/libcrypto/python.o）/
  elf-build-id=3；相同 2839+软链 643+差异 567=4049。L0 最终重跑 PASS（无扫描自命中）。
  三样交付数（剩余差异 567 / 每规则命中 / 三关原始输出）已进 REPORT §4+§5。
- **规则引擎两处实现修正**（11-21，不改规则语义只修误判）：①差异字节**按所属 C 串分组**判，不再按区域合并
  （相邻两串间的 \0 填充曾被当成"串内含非打印字节"误杀 libpython）；②串内允许 \t\n\r（bcmdhd 的
  "compiled on …\n" 尾换行）。差异字节仍必须落在日期/时间/git 格式串内。
- **坑：apply 幂等重跑 rm -rf 撞 git auto-gc**（11-20 APPLY2_FAIL："Directory not empty"）——commit 触发的后台 repack
  与 rm -rf 抢 .git/objects。修：apply.sh 加 `git config gc.auto 0`（不改树内容/L1 判据）。
- **待问用户**：（已解决，见上 11-21 拍板条）内核模块 .note.gnu.build-id → 批准了窄规则；git 元数据 → 消；chrony 常数 → 消成功。
- VM 工作目录布局（第 8 轮收尾后）：bsp-work/{ref(=第8轮验收树),ref-orig(=原参考树,勿动),ref-clean,ref-out,
  samepath,samepath2(全日志留档),bsp-final,deliver-scripts,test-settled,l0-final.log,l2-round8.log,
  classify-l2.py 探针脚本}；bsp-accept=全新目录验收树。ref-r7/chrony-proof//tmp 探针/**/tmp/.sudoexec 已删**
  （口令助手别留；下次要 sudo-over-ssh 按 skill vm-ssh-sudo-exec 重建）。
- **剩余**：本地提交（bsp/ 全套 + 记忆镜像）→ **推 GitHub 前问用户** → L3 上板由用户做。