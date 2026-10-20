#!/bin/sh
# T11：做两样素材 —— 彩条底图（只画一次）+ 码表字形表（每帧只贴数字块）。
# 在板子上跑：/opt/k11c-kvm/vo/mkassets.sh，输出到同目录。
set -e
cd "$(dirname "$0")"
FONT=/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf

# 1920x1080 NV12 = 1920*1080*1.5 = 3110400 字节
ffmpeg -nostdin -loglevel error -f lavfi -i smptehdbars=s=1920x1080 -frames:v 1 \
  -pix_fmt nv12 -f rawvideo -y bars_nv12.yuv

# 字形表：40x80 灰度，顺序 0123456789:.# 共 13 格 = 41600 字节
# textfile= 是为了绕开 drawtext 里 ":" 要转义的问题；
# y_align=font 让每个字按同一条基线摆，不加的话 ":" "." 会上下乱跳。
: > glyphs.gray
for c in 0 1 2 3 4 5 6 7 8 9 : . '#'; do
  printf '%s' "$c" > /tmp/glyph.txt
  ffmpeg -nostdin -loglevel error -f lavfi -i color=black:s=40x80 -frames:v 1 \
    -vf "drawtext=fontfile=$FONT:textfile=/tmp/glyph.txt:fontsize=64:fontcolor=white:x=(w-tw)/2:y=6:y_align=font" \
    -pix_fmt gray -f rawvideo -y /tmp/glyph.gray
  cat /tmp/glyph.gray >> glyphs.gray
done

ls -l bars_nv12.yuv glyphs.gray
