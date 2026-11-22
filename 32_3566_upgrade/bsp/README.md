# bsp/ — K11C (RK3566) Buildroot A/B 固件重建包

不依赖 6.3GB 私有 KickPI SDK 包：公开上游基线 + 三层小 patch（git am）+ 少量二进制 blob，
重建出与参考 SDK 完全一致的源码树，编出同样的固件。

- 三层 patch：**A** = 公开基线 → SDK 导入态（按目录拆）；**B** = KickPI 的 111 个提交（一提交一 patch）；**C** = 本目录 `patches/`、`sdk/` 的改动（按主题拆）。
- 二进制不进 patch，放 `blobs/`，由 apply.sh 校验 sha256 后拷入。
- 组件范围与裁剪理由见 `scope.txt`；基线选择与验收记录见 `REPORT.md`；基线锁定见 `versions.lock`。

## 前提

- Linux x86_64 编译机，≥150GB 空闲磁盘；git、curl、tar、python3、bash。
- RK Buildroot 编译依赖（参考 KickPI 文档「SDK 编译」章节装 host 依赖）。
- 编译机可访问 github.com / gitlab.com / developer.arm.com（fetch 约 1~2GB 下载）。
- 本仓库的 `overlay/`、`patches/` 原目录保持不动；本包只新增 `bsp/`。

## 步骤（fetch → update.img）

```bash
# 1. 克隆本仓库，进入目录
git clone <本仓库URL> && cd 32_3566_upgrade

# 2. 选一个工作目录（不要放在本仓库内）
W=~/k11c-rebuild

# 3. 拉公开基线（断点续传+重试；git 组件按 versions.lock 的 commit 精确取）
bash bsp/scripts/fetch.sh "$W"

# 4. 组装源码树：基线 + A/B/C patch + blobs → "$W/tree"
bash bsp/scripts/apply.sh "$W"

# 5. 同步 overlay（照原 README.md 的「overlay 同步」节）：
#    - overlay/ 拷到编译机；WiFi 配置用 .example 填假值，不提交
#    - 注意 buildroot defconfig 里硬编码了
#      BR2_ROOTFS_OVERLAY="/home/rk/k11c/k11c-br-overlay" 与
#      BR2_ROOTFS_USERS_TABLES="/home/rk/k11c/k11c-br-users.txt"：
#      要么把 overlay 放到这两个路径，要么改 tree/buildroot/configs/rockchip_rk3566_k11c_kvm_defconfig

# 6. 选 defconfig
cd "$W/tree"
./build.sh rk3566_rk3568:rockchip_rk3566_kickpi_k11c_v12_buildroot_ab_defconfig

# 7~10. 四个目标分开编（firmware 必须在 updateimg 之前）
./build.sh uboot
./build.sh rootfs

# 8.5 chrony 时间锚定 —— 仅「产物与参考固件逐字节一致」需要；正常出可用固件可跳过。
# chrony 的 configure 把「configure 时刻 unix 秒 - 18250 天」算成 NTP_ERA_SPLIT 编进代码，
# 只包 chrony 的 configure 用参考那次 configure 的时刻（SOURCE_DATE_EPOCH 是 chrony
# configure 原生支持的输入，不改源码/patch）。重建后须再走一遍增量 rootfs：
# strip 与镜像打包在 target-finalize 里做，缺这步二进制未 strip。
BO="$W/tree/buildroot/output/rockchip_rk3566_kickpi_k11c_v12_buildroot_ab/rockchip_rk3566_k11c_kvm"
make -C "$W/tree/buildroot" O="$BO" chrony-dirclean
make -C "$W/tree/buildroot" O="$BO" -j"$(nproc)" \
  "CHRONY_CONFIGURE_CMDS=cd $BO/build/chrony-4.6.1 && \$(TARGET_CONFIGURE_OPTS) SOURCE_DATE_EPOCH=1795104796 ./configure \$(CHRONY_CONF_OPTS)" \
  chrony
rm -f "$BO"/images/rootfs.*
./build.sh rootfs

./build.sh firmware
./build.sh updateimg

# 11. 产物：rockdev/ 下各分区 img；整包在 output/update-ab/Image/update.img
#     （rockdev/update.img 是指向 update-ab.img 的软链，实际文件以上面路径为准）
```

烧录与上板验证（串口、A/B 切换等）照原 `README.md`，由使用者执行。

## 验收（可选，需要参考产物时）

```bash
bash bsp/scripts/verify-tree.sh "$W/tree" <参考树>        # L1：源码树逐字节+权限/软链
bash bsp/scripts/compare-build.sh <ref-out> "$W/tree"     # L2：编译产物一致性
bash bsp/scripts/check-l0.sh bsp                          # L0：patch 规格/秘密扫描
```

## 注意

- patch 均为组件相对路径，apply.sh 用 `git am --directory=<组件>` 套用；
  SDK 含 CRLF 源文件，apply.sh 已设 `am.keepcr=true`（手工 git am 时也要设）。
- 权限口径：参考树全树只有 664（非执行）/775（执行）两种文件权限。git 检出和 tarball 解压的权限随
  编译机 umask 变，apply.sh 末尾统一归一到这个口径，任何机器重建结果一致（L1 权限清单据此比对）。
- `fetch.sh && apply.sh` 幂等：apply 每次清空 tree/ 重建；重复跑结果一致。
- apply.sh 在 tree 仓库设 `core.abbrev=9`，baselines 提交按 SDK 根提交原署名/日期/说明提交：
  内核 mpp 驱动把 `git log -1` 的结果编进 .rodata、Buildroot gcc 把短哈希编进版本串，
  哈希长度或署名长度差会改变二进制布局（System.map 地址平移等）。
- 不放秘密：无 cloud.json、无填好的 WiFi、无 authorized_keys、无镜像/dl/编译产物。
- 单文件 >1MB 的 patch 例外（Realtek 驱动大头文件等）逐条列在 REPORT.md。