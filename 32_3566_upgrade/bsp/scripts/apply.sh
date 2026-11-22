#!/bin/bash
# apply.sh — 把基线 + A/B/C 三层 patch + blobs 组装成 SDK 布局的树。
# 用法: ./apply.sh <工作目录>
#   工作目录里须已有 baselines/<组件>/（fetch.sh 的产物）。
#   产出 <工作目录>/tree/（git 仓库，HEAD = 参考树内容）。
# 幂等：重复运行会先清空 tree/ 重建。
set -euo pipefail
W=${1:?用法: apply.sh <工作目录>}
BSP=$(cd "$(dirname "$0")/.." && pwd)
TREE=$W/tree
MAP=$BSP/components.tsv

[ -d "$W/baselines" ] || { echo "缺 $W/baselines，先跑 fetch.sh"; exit 1; }

rm -rf "$TREE"
mkdir -p "$TREE"
git -C "$TREE" init -q
git -C "$TREE" config user.name  >/dev/null 2>&1 || git -C "$TREE" config user.name  bsp-apply
git -C "$TREE" config user.email >/dev/null 2>&1 || git -C "$TREE" config user.email bsp-apply@local
# SDK 里有 CRLF 源文件（如 mpp version.in）；mailinfo 默认剥 CR 会导致 am 失败
git -C "$TREE" config am.keepcr true
# 关 auto gc：commit 触发的后台 repack 会和幂等重跑的 rm -rf 抢 .git/objects（Directory not empty）
git -C "$TREE" config gc.auto 0
# 短哈希固定 9 位 = 参考 SDK 仓库 git 自动缩写的长度。Buildroot gcc pkgversion、
# python.o .comment、os-release VERSION 等编译期嵌入点按长度排布，7/9 位差会改段/文件大小。
git -C "$TREE" config core.abbrev 9

export GIT_AUTHOR_NAME=bsp-apply GIT_AUTHOR_EMAIL=bsp-apply@local
export GIT_COMMITTER_NAME=bsp-apply GIT_COMMITTER_EMAIL=bsp-apply@local

# 1. 铺基线（empty 基线的组件跳过，由 A 层全量新增）
while IFS=$'\t' read -r comp path kind subset || [ -n "$comp" ]; do
  case "$comp" in \#*|"") continue;; esac
  [ "$kind" = empty ] && continue
  src=$W/baselines/$comp
  [ -d "$src" ] || { echo "缺基线 $src"; exit 1; }
  mkdir -p "$TREE/$path"
  if [ "$subset" != "-" ]; then
    if [ -d "$src/$subset" ]; then
      # 目录子集（如 tools/linux/Linux_Pack_Firmware）
      mkdir -p "$TREE/$path"
      (cd "$src/$subset" && tar -cf - --exclude=.git .) | tar -xf - -C "$TREE/$path"
    else
      # 文件清单子集（保留目录结构/权限/软链）
      (cd "$src" && tar -cf - -T "$BSP/$subset") | tar -xf - -C "$TREE/$path"
    fi
  else
    (cd "$src" && tar -cf - --exclude=.git .) | tar -xf - -C "$TREE/$path"
  fi
done < "$MAP"
git -C "$TREE" add -A -f
# baselines 提交的作者名/邮箱、作者日期、提交日期、说明取 SDK 根提交 1f9d3a8 的原值。
# 原因：kernel-6.1/drivers/video/rockchip/mpp/Makefile 用 `git log -1 -- <mpp目录>` 把
# 「%h author: %an %cd %s」编进内核 .rodata（MPP_VERSION 串）。该提交内容就是这份 SDK 基线，
# 署名沿用原作者；哈希值仍与参考不同（仅哈希内容差、长度同，由 L2 现有 GIT 哈希规则覆盖）。
GIT_AUTHOR_NAME=tanzh GIT_AUTHOR_EMAIL=981431410@qq.com \
GIT_AUTHOR_DATE='2026-03-24T13:02:55+08:00' \
GIT_COMMITTER_DATE='2026-03-24T13:02:55+08:00' \
git -C "$TREE" commit -q -m "feat: init linux6.1 sdk on 202603024"

# 2. 逐组件套 A/B/C patch，再放 blobs
while IFS=$'\t' read -r comp path kind subset || [ -n "$comp" ]; do
  case "$comp" in \#*|"") continue;; esac
  for layer in a b c; do
    s=$BSP/patches/$comp/series
    [ -f "$s" ] || continue
    # series 里按层过滤；文件名形如 NNNN-<layer>-<主题>.patch
    mapfile -t files < <(grep -E "^[0-9]+-$layer-" "$s" || true)
    [ ${#files[@]} -eq 0 ] && continue
    args=()
    for f in "${files[@]}"; do args+=("$BSP/patches/$comp/$f"); done
    if [ "$path" = "." ]; then
      git -C "$TREE" am --whitespace=nowarn "${args[@]}"
    else
      git -C "$TREE" am --whitespace=nowarn --directory="$path" "${args[@]}"
    fi
  done
  # blobs（二进制不进 patch；D=删除，A/M=拷入）
  meta=$BSP/blobs/$comp/manifest.tsv
  if [ -f "$meta" ]; then
    while IFS=$'\t' read -r status spath sha mode || [ -n "$status" ]; do
      case "$status" in \#*|"") continue;; esac
      if [ "$status" = D ]; then
        rm -f "$TREE/$spath"
      else
        rel=${spath#"$path"/}
        [ "$path" = "." ] && rel=$spath
        mkdir -p "$TREE/$(dirname "$spath")"
        cp "$BSP/blobs/$comp/$rel" "$TREE/$spath"
        chmod "$mode" "$TREE/$spath"
        echo "$sha  $TREE/$spath" | sha256sum -c - >/dev/null || { echo "blob sha256 不符: $spath"; exit 1; }
      fi
    done < "$meta"
    git -C "$TREE" add -A -f
    git -C "$TREE" diff --cached --quiet || git -C "$TREE" commit -q -m "blobs: $comp"
  fi
done < "$MAP"

# blob 删除可能留下空目录；git 树不跟踪空目录，参考树里也不会有
find "$TREE" -type d -empty ! -path "$TREE/.git" ! -path "$TREE/.git/*" -delete

# 权限归一：参考树口径 = 非执行 664 / 执行 775（全树只有这两种）。
# git 检出/tarball 解压的权限随 umask 变，这里统一，保证任何机器重建结果一致。
find "$TREE" -path "$TREE/.git" -prune -o -type f -perm /111 -exec chmod 775 {} +
find "$TREE" -path "$TREE/.git" -prune -o -type f ! -perm /111 -exec chmod 664 {} +

echo "APPLY_OK tree=$TREE"