#!/bin/bash
# check-l0.sh — L0 静态验收：patch 规格 / Origin / series / blobs / 秘密 / 体积。
# 用法: ./check-l0.sh <bsp目录>
set -uo pipefail
BSP=${1:?用法: check-l0.sh <bsp目录>}
fail=0
cd "$BSP"

# 例外清单（单文件>1MB 的源文件，来自 assemble-report.json）
python3 -c "
import json
d = json.load(open('assemble-report.json'))
for e in d.get('exceptions', []):
    print(e['path'])
" > /tmp/l0-exceptions.txt 2>/dev/null || : > /tmp/l0-exceptions.txt

total_patches=0
while IFS=$'\t' read -r comp path kind subset || [ -n "$comp" ]; do
  case "$comp" in \#*|"") continue;; esac
  s=patches/$comp/series
  [ -f "$s" ] || { echo "[L0] $comp 无 series（0 patch 组件可缺省）"; continue; }
  # series 与文件 1:1
  if diff -u <(grep -v '^#' "$s" | sort) <(ls patches/$comp/*.patch 2>/dev/null | xargs -r -n1 basename | sort) > /tmp/l0-series.diff; then
    :
  else
    echo "[L0] FAIL $comp series 与文件不一致:"; head -10 /tmp/l0-series.diff; fail=1
  fi
  while read -r f; do
    case "$f" in \#*|"") continue;; esac
    p=patches/$comp/$f
    total_patches=$((total_patches+1))
    grep -q "^Origin:" "$p" || { echo "[L0] FAIL 缺 Origin: $p"; fail=1; }
    if grep -q "^GIT binary patch" "$p"; then echo "[L0] FAIL 含二进制 patch: $p"; fail=1; fi
    nf=$(git apply --numstat "$p" 2>/dev/null | wc -l)
    if [ "$nf" -gt 100 ]; then echo "[L0] FAIL >100 文件($nf): $p"; fail=1; fi
    sz=$(stat -c %s "$p")
    if [ "$sz" -gt 1000000 ]; then
      # 超限例外：仅单文件且该文件在例外清单
      if [ "$nf" -eq 1 ]; then
        fp=$(git apply --numstat "$p" | awk '{print $3}')
        full="$path/$fp"; [ "$path" = "." ] && full=$fp
        if grep -qxF "$full" /tmp/l0-exceptions.txt; then
          echo "[L0] 例外(单文件>1MB, ${sz}B): $p"
        else
          echo "[L0] FAIL >1MB 且非已记录例外: $p ($fp)"; fail=1
        fi
      else
        echo "[L0] FAIL >1MB($sz): $p"; fail=1
      fi
    fi
  done < "$s"
done < components.tsv
echo "[L0] patch 总数: $total_patches"

# blobs：单文件 ≤50MB + sha256
if [ -f blobs/SHA256SUMS ] && [ -s blobs/SHA256SUMS ]; then
  big=$(find blobs -type f ! -name SHA256SUMS ! -name manifest.tsv -size +50M)
  [ -n "$big" ] && { echo "[L0] FAIL blob >50MB: $big"; fail=1; }
  (cd blobs && sha256sum -c SHA256SUMS --quiet) || { echo "[L0] FAIL blob sha256"; fail=1; }
  echo "[L0] blobs sha256 OK ($(wc -l < blobs/SHA256SUMS) 个)"
fi

# 秘密扫描。白名单写死三要素（相对路径|行号|该行含前导+不含换行的 sha256），
# 三样全对上才放过；其余任何命中一律 FAIL。不按关键词/目录整片忽略。
# 这 2 行是 Realtek 驱动调试格式串，已验证 ref-clean 同内容存在（REPORT.md §4）。
cat > /tmp/l0-whitelist.txt <<WL
patches/external-rkwifibt/0052-b-feat-wifi-add-rtl88x2CS-driver-part-51-53.patch|18303|bacf1c0b4a5e423629ae359c54e88c140a08e6033fdb190c53f3b22afbba924d
patches/external-rkwifibt/0004-b-feat-wifi-add-rtl88x2CS-driver-part-3-53.patch|4866|8e480391756639ac89b5d3516bd6f01a08b38b28842f272a0028f9dbf4cfd736
WL
wl_used=0
while IFS= read -r hit; do
  [ -n "$hit" ] || continue
  hp=${hit%%:*}; r=${hit#*:}; ln=${r%%:*}; content=${r#*:}
  hp=${hp#./}
  h=$(printf %s "$content" | sha256sum | cut -d" " -f1)
  if grep -qxF "$hp|$ln|$h" /tmp/l0-whitelist.txt; then
    echo "[L0] 白名单命中(驱动调试串,非秘密): $hp:$ln"
    wl_used=$((wl_used+1))
  else
    echo "$hit"
    echo "[L0] FAIL 疑似秘密(白名单外): $hp:$ln"; fail=1
  fi
done < <(grep -rnI "secretToke[n]\|psk[=]\|BEGIN OPENSSH PRIVATE KE[Y]" . 2>/dev/null)
echo "[L0] 秘密扫描: 白名单命中 $wl_used/2, 白名单外命中见上(无输出=0)"

sz=$(du -sb . | cut -f1)
echo "[L0] bsp 总体积: $((sz/1000000)) MB"
if [ $fail -eq 0 ]; then echo L0_PASS; else echo L0_FAIL; exit 1; fi