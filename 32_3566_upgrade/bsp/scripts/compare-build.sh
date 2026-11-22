#!/bin/bash
# compare-build.sh — L2 验收：参考产物（ref-out/）vs 重建树。
# 豁免走窄规则（l2-rules.py），不按文件名单；任何套不进规则的差异 = FAIL。
# 用法: ./compare-build.sh <ref-out目录> <重建树根目录>
# ref-out 布局（第1步收集）：
#   rockdev/parameter.txt  rockdev/MiniLoaderAll.bin
#   config/kernel.config  config/uboot.config  config/buildroot.config
#   config/buildroot.outrel  config/reftarget.path
#   dtb/rk3566-kickpi-k11c-v12-linux.dtb
#   lists/build-packages.txt  lists/target-manifest.txt  lists/package-file.txt
# 整镜像 md5 不要求（任务书明确）。
set -uo pipefail
R=${1:?用法: compare-build.sh <ref-out> <重建树>}
N=${2:?}
HERE=$(cd "$(dirname "$0")" && pwd)
PY=python3
fail=0
ck() { # 描述, 文件1, 文件2
  if cmp -s "$2" "$3"; then echo "[L2] OK $1"; else echo "[L2] FAIL $1"; fail=1; fi
}

ck "parameter.txt" "$R/rockdev/parameter.txt" "$N/rockdev/parameter.txt"

# MiniLoaderAll：仅 0x0E-0x14 打包时间(7字节) + 末尾4字节校验和 可不同（用户已批准）
$PY "$HERE/l2-rules.py" miniloader "$R/rockdev/MiniLoaderAll.bin" "$N/rockdev/MiniLoaderAll.bin" || fail=1

ck "kernel .config"   "$R/config/kernel.config"   "$N/kernel-6.1/.config"
ck "u-boot .config"   "$R/config/uboot.config"    "$N/u-boot/.config"
OUTREL=$(cat "$R/config/buildroot.outrel")
# buildroot .config：仅 "# Buildroot -g<哈希> Configuration" 注释行可不同
$PY "$HERE/l2-rules.py" brconfig "$R/config/buildroot.config" "$N/$OUTREL/.config" || fail=1

ck "dtb" "$R/dtb/rk3566-kickpi-k11c-v12-linux.dtb" \
   "$N/kernel-6.1/arch/arm64/boot/dts/rockchip/rk3566-kickpi-k11c-v12-linux.dtb"

# Buildroot build/ 包名+版本列表
if diff -u "$R/lists/build-packages.txt" <(ls "$N/$OUTREL/build" | sort) > /tmp/l2-pkgs.diff; then
  echo "[L2] OK build/ 包列表 ($(wc -l < "$R/lists/build-packages.txt") 个)"
else
  echo "[L2] FAIL build/ 包列表:"; head -20 /tmp/l2-pkgs.diff; fail=1
fi

# target/ 清单：严格一致（无排除名单）
TGT="$N/$OUTREL/target"
mf() { (cd "$TGT" && find . ! -type d -printf '%P\n' | sort); }
if diff -u "$R/lists/target-manifest.txt" <(mf) > /tmp/l2-target.diff; then
  echo "[L2] OK target/ 清单"
else
  echo "[L2] FAIL target/ 清单:"; head -30 /tmp/l2-target.diff; fail=1
fi

# target/ 内容：逐文件窄规则判定（pyc/gz/os-release/shadow/ELF），打印规则命中数+无法解释数
REFTGT=$(cat "$R/config/reftarget.path")
PASSWD=$(grep "^BR2_TARGET_GENERIC_ROOT_PASSWD=" "$N/$OUTREL/.config" | cut -d'"' -f2)
$PY "$HERE/l2-rules.py" target "$REFTGT" "$TGT" "$R/lists/target-manifest.txt" "$PASSWD" || fail=1

# update.img 分区表 = README 8 行
PF=$(find "$N/output" -name package-file -path "*Image*" | head -1)
if [ -n "$PF" ] && diff -u "$R/lists/package-file.txt" "$PF" > /tmp/l2-pf.diff; then
  echo "[L2] OK package-file 分区表"
else
  echo "[L2] FAIL package-file:"; head -15 /tmp/l2-pf.diff 2>/dev/null; fail=1
fi

if [ $fail -eq 0 ]; then echo L2_PASS; else echo L2_FAIL; exit 1; fi