#!/bin/sh
# 在板子 HDMI OUT（接电视）上全屏放 /stream.mjpg。
# 必须以 kickpi 身份在 X 里跑：root 起的 X 程序在电视上显示不出来（文档坑 9）。
DISPLAY=${DISPLAY:-:0}
XAUTHORITY=${XAUTHORITY:-/home/kickpi/.Xauthority}
export DISPLAY XAUTHORITY

xrandr --output HDMI-1 --auto
xset s off -dpms s noblank
pkill xfce4-screensaver

# 服务没起来就先等，否则 ffplay 一直连不上白耗一个进程
until curl -s -o /dev/null --max-time 2 http://127.0.0.1:8000/state; do
  echo "waiting for kvm_server on :8000"
  sleep 1
done

while true; do
  ffplay -fs -an -noborder -fflags nobuffer -flags low_delay -framedrop \
    -f mpjpeg http://127.0.0.1:8000/stream.mjpg
  echo "ffplay exited rc=$?, restart in 2s"
  sleep 2
done
