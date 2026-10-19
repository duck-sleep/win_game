#!/bin/sh
# 起/重启 kvm_server（root，因为 /dev/hidg* 是 crw------- root）。口令走环境变量，不落盘。
# 用法: ssh k11c 'K11C_SUDO=<口令> sh /opt/k11c-kvm/run.sh'
#
# 为什么用 systemd-run 而不是 setsid nohup：从 ssh 会话里起的进程会留在
# user-1000.scope 里，会话一登出 logind 就把它整组杀掉（10-18 实测服务无声消失）。
# 临时系统单元挂在 system.slice 下，跟登录会话无关，日志进 journal。
pkill -f 'kvm_server[.]py' 2>/dev/null || true
printf '%s\n' "$K11C_SUDO" | sudo -S systemctl stop k11c-kvm-run.service 2>/dev/null || true
printf '%s\n' "$K11C_SUDO" | sudo -S systemd-run --unit=k11c-kvm-run --collect \
  python3 /opt/k11c-kvm/kvm_server.py --host 0.0.0.0 --port 8000
