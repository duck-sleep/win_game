#!/bin/sh
# 把 Qoder 的自动记忆镜像进仓库 —— 用户 2026-10-21 要求"大家用一份"。
#
# 真实记忆目录（Qoder 自动读写，不能挪走，挪了下次会话就"失忆"）：
#   C:\Users\123456\.qoder-cn\memory\                                  用户级（跨项目）
#   C:\Users\123456\.qoder-cn\projects\D--win-game-project\memory\     项目级
# 镜像到：01_记忆原档\qoder-cn\...（保持和真实目录一样的结构）
#
# 🔴 自动脱敏：编译 VM 的 sudo 口令绝不进仓库（用户 2026-10-15 明确定过这条，
#    那份记忆自己写着"绝不写进仓库文件/技术文档"）。所以凡是含"口令/password"的行里的 123 一律替换掉。
#
# 用法：sh sync_qoder_memory.sh        （每次存了新记忆后跑一遍，然后 git commit）
set -e
SRC_USER="/c/Users/123456/.qoder-cn/memory"
SRC_PROJ="/c/Users/123456/.qoder-cn/projects/D--win-game-project/memory"
HERE=$(cd "$(dirname "$0")" && pwd)
DST="$HERE/01_记忆原档/qoder-cn"

[ -d "$SRC_USER" ] || { echo "找不到 $SRC_USER"; exit 1; }

# 只清内容、不删目录本身：Windows 上索引器/杀软会短暂占住目录句柄，
# 直接 rm -rf 整个目录会报 "Device or resource busy"（踩过）。
mkdir -p "$DST"
find "$DST" -mindepth 1 -delete 2>/dev/null || true
mkdir -p "$DST/memory" "$DST/projects/D--win-game-project/memory"
cp -a "$SRC_USER/." "$DST/memory/"
cp -a "$SRC_PROJ/." "$DST/projects/D--win-game-project/memory/"

# 脱敏（只动"口令/password"所在行，别的地方不碰）
hit=0
for f in $(grep -rl "口令\|password" "$DST" 2>/dev/null); do
  if sed -nE '/口令|password/p' "$f" | grep -q "123"; then
    sed -i -E '/口令|password/s/`123`/<已脱敏>/g; /口令|password/s/[^0-9A-Za-z]123([^0-9])/ <已脱敏>\1/g' "$f"
    hit=$((hit + 1))
  fi
done

echo "镜像完成：$DST"
echo "  用户级 $(find "$DST/memory" -type f | wc -l) 个文件，项目级 $(find "$DST/projects" -type f | wc -l) 个文件"
echo "  脱敏改过的文件：$hit 个"
left=$(grep -rn "sudo 口令 = \`123\`\|输入123就行" "$DST" 2>/dev/null | wc -l)
echo "  残留明文 VM 口令检查：$left 处（必须是 0）"
[ "$left" = 0 ] || { echo "🔴 还有明文口令，别提交！"; exit 1; }
