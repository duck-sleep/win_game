#!/bin/sh
# 假源：把彩条 + 码表连续编码成 JPEG 帧写到标准输出。
# 码表用 %{pts:hms} = 从流开始的经过时间，不依赖板子时钟（板子时钟是错的）。
exec ffmpeg -nostdin -hide_banner -loglevel warning -re \
  -f lavfi -i smptehdbars=s=1280x720:r=30 \
  -vf "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf:text='%{pts\:hms}':fontsize=64:fontcolor=white:box=1:boxcolor=black:x=(w-tw)/2:y=h-th-40" \
  -c:v mjpeg -q:v 6 -f image2pipe -
