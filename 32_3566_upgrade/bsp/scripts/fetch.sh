#!/bin/bash
# fetch.sh — 按 versions.lock 拉取各组件公开基线到 <工作目录>/baselines/<组件>。
# 用法: ./fetch.sh <工作目录>
# 需要 git、curl、tar、sha256sum。下载支持断点续传与重试。
set -euo pipefail
W=${1:?用法: fetch.sh <工作目录>}
BSP=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$W/baselines"

while IFS=$'\t' read -r comp method url ref commit sha || [ -n "$comp" ]; do
  case "$comp" in \#*|"") continue;; esac
  dest=$W/baselines/$comp
  case "$method" in
    git)
      if [ ! -d "$dest/.git" ]; then
        echo "== fetch $comp ($ref) =="
        ok=0
        # 快路径：直接按 commit 浅取（GitHub/GitLab 多数允许）
        mkdir -p "$dest"
        git -C "$dest" init -q
        git -C "$dest" remote add origin "$url" 2>/dev/null || true
        if git -C "$dest" fetch --depth 1 origin "$commit" 2>/dev/null; then
          git -C "$dest" checkout -q FETCH_HEAD; ok=1
        fi
        if [ $ok -eq 0 ]; then
          rm -rf "$dest"
          for i in 1 2 3 4 5; do
            git clone --single-branch -b "$ref" "$url" "$dest" && { ok=1; break; }
            echo "clone 重试 $i $comp"; rm -rf "$dest"; sleep 5
          done
          [ $ok -eq 1 ] || { echo "FETCH_FAIL $comp"; exit 1; }
          git -C "$dest" checkout -q "$commit" 2>/dev/null || {
            git -C "$dest" fetch --unshallow origin "$ref" 2>/dev/null || git -C "$dest" fetch origin "$ref"
            git -C "$dest" checkout -q "$commit"
          }
        fi
      fi
      git -C "$dest" checkout -q "$commit"
      echo "$comp $(git -C "$dest" rev-parse HEAD)"
      ;;
    tarball)
      case "$url" in
        *.tar.xz) f=$W/baselines/$comp.tar.xz; xt=J;;
        *.tar.bz2) f=$W/baselines/$comp.tar.bz2; xt=j;;
        *) f=$W/baselines/$comp.tar.gz; xt=z;;
      esac
      for i in $(seq 1 10); do
        curl -L -C - --speed-time 60 --speed-limit 20000 --connect-timeout 30 -o "$f" "$url" && break
        echo "下载重试 $i $comp"; sleep 5
      done
      echo "$sha  $f" | sha256sum -c -
      rm -rf "$dest"; mkdir -p "$dest"
      tar -x"$xt"f "$f" -C "$dest" --strip-components=1
      echo "$comp tarball OK"
      ;;
    empty)
      echo "$comp 基线为空（A 层全量新增）"
      ;;
    *) echo "未知 method: $method"; exit 1;;
  esac
done < "$BSP/versions.lock"
echo FETCH_OK