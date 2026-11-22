#!/bin/bash
# verify-tree.sh — L1 验收：重建树 vs 参考树，逐组件比内容 + 权限/类型/软链。
# 用法: ./verify-tree.sh <重建树目录> <参考树目录>
# 两项都比较：diff -r --no-dereference --exclude=.git 和 find 清单（%m %y %l %P）。
# 子集组件（rkbin）只比清单内文件。全部一致输出 L1_PASS，否则 L1_FAIL 并列出差异。
# 注意：在编译之前跑（编译产物不在比较范围内）。
set -uo pipefail
TREE=${1:?用法: verify-tree.sh <重建树> <参考树>}
REF=${2:?}
BSP=$(cd "$(dirname "$0")/.." && pwd)
MAP=$BSP/components.tsv
fail=0

manifest() {
  (cd "$1" && find . -path ./.git -prune -o ! -type d -printf '%m %y %l %P\n' | sort)
}

while IFS=$'\t' read -r comp path kind subset || [ -n "$comp" ]; do
  case "$comp" in \#*|"") continue;; esac
  t=$TREE/$path; r=$REF/$path
  if [ "$path" = "." ]; then t=$TREE; r=$REF; fi
  if [ ! -d "$r" ]; then echo "[$comp] 参考树缺 $r"; fail=1; continue; fi
  if [ ! -d "$t" ]; then echo "[$comp] 重建树缺 $t"; fail=1; continue; fi
  if [ "$subset" != "-" ] && [ -f "$BSP/$subset" ]; then
    while read -r f; do
      case "$f" in \#*|"") continue;; esac
      if ! cmp -s "$t/$f" "$r/$f"; then echo "[$comp] 内容不同: $f"; fail=1; fi
      tm=$(stat -c '%a' "$t/$f" 2>/dev/null); rm_=$(stat -c '%a' "$r/$f" 2>/dev/null)
      if [ "$tm" != "$rm_" ]; then echo "[$comp] 权限不同: $f ($tm vs $rm_)"; fail=1; fi
    done < "$BSP/$subset"
    echo "[$comp] 子集比对完成"
    continue
  fi
  if [ "$path" = "." ]; then
    for f in .gitignore Makefile build.sh rkflash.sh kernel Copyright_Statement.md common; do
      [ -e "$r/$f" ] || [ -L "$r/$f" ] || continue
      if [ -L "$r/$f" ] || [ -L "$t/$f" ]; then
        tl=$(readlink "$t/$f" 2>/dev/null); rl=$(readlink "$r/$f" 2>/dev/null)
        [ "$tl" = "$rl" ] || { echo "[$comp] 软链不同: $f ($tl vs $rl)"; fail=1; }
      elif ! cmp -s "$t/$f" "$r/$f"; then echo "[$comp] 内容不同: $f"; fail=1; fi
    done
    echo "[$comp] 根文件比对完成"
    continue
  fi
  d=$(diff -r --no-dereference --exclude=.git "$t" "$r" 2>&1)
  if [ -n "$d" ]; then echo "[$comp] 内容差异:"; echo "$d" | head -20; fail=1; fi
  mt=$(manifest "$t"); mr=$(manifest "$r")
  if [ "$mt" != "$mr" ]; then
    echo "[$comp] 清单差异（权限/类型/软链）:"
    diff <(echo "$mt") <(echo "$mr") | head -20
    fail=1
  fi
  if [ -z "$d" ] && [ "$mt" = "$mr" ]; then echo "[$comp] OK"; fi
done < "$MAP"

if [ $fail -eq 0 ]; then echo L1_PASS; else echo L1_FAIL; exit 1; fi