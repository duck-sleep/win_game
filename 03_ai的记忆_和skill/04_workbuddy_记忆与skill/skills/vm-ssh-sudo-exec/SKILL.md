---
name: vm-ssh-sudo-exec
description: 从 Windows 非交互 SSH 进 Linux 编译 VM 并执行需要 sudo 的长命令（askpass 包装），以及 scp/tee/pipefail 三个会"假装成功"的坑。触发词：VM 上装包、编译、sudo 要密码、非交互执行、长任务后台跑。
---

# VM 非交互 sudo 执行 + 长任务

用户 2026-10-15 明确要求：**AI 直接上手执行，不要只贴命令让他代敲**。
Ubuntu 的 sudo 在非交互 SSH 里要密码、且没有 tty，所以要包装。VM 的 sudo 口令由用户当场给，
**不写进仓库、不写进长期文档**。

## sudo：askpass + PATH 包装（不要改脚本本身）

```bash
ssh -o BatchMode=yes <别名> bash -s <<'EOF'
rm -rf /tmp/.sudoexec; mkdir -p /tmp/.sudoexec/bin
printf '%s\n' '#!/bin/sh' 'echo <口令>' > /tmp/.sudoexec/ap.sh
printf '%s\n' '#!/bin/sh' 'exec /usr/bin/sudo -A "$@"' > /tmp/.sudoexec/bin/sudo
chmod 700 /tmp/.sudoexec /tmp/.sudoexec/ap.sh /tmp/.sudoexec/bin /tmp/.sudoexec/bin/sudo
export PATH=/tmp/.sudoexec/bin:$PATH SUDO_ASKPASS=/tmp/.sudoexec/ap.sh
sudo -A -v                      # 先验一次，失败立刻看出来
<要跑的活>
echo "=== rc=${PIPESTATUS[0]} ==="
rm -rf /tmp/.sudoexec           # 用完必须删掉含口令的文件
EOF
```

为什么这样而不是别几种：
- `echo 密码 | sudo -S` 只能救**一条**命令；脚本里几十处 `sudo` 就抓瞎。PATH 包装让
  脚本原封不动，每次 `sudo` 自动带 `-A` 走 askpass，缓存失效也能续上。
- 别去写 `/etc/sudoers.d/ NOPASSWD`——那是系统级改动，除非用户点名。
- 内层 heredoc 用 `<<'EOF'`（单引号）防本地 shell 先展开；外层写文件时同理。

## 三个"假装成功"的坑（都真的踩过）

1. **`scp ... | tail` 吃错误码**。管道退出码取最后一个命令，`scp` 失败被 `tail` 的 0 盖掉，
   后面的 `|| 兜底` 永远不触发，任务还报"completed exit code 0"。
   → 先 `set -o pipefail`，或干脆**先单独建目录再传**：
   ```bash
   ssh 别名 'mkdir -p /home/u/dir' && scp 文件 别名:/home/u/dir/名
   ```
2. **`apt-get install -y A B C` 只要有一个包有问题，整批一个都不装**。
   `python3-pip : Breaks: python-pip`（SNM970 RK 线实测）就属于这种。
   → 装完必须**跑一遍自检**确认真的装上了：
   ```bash
   for t in git make bison flex dtc java; do printf "%-8s " "$t"; command -v $t || echo 缺; done
   ```
   别信 apt 的输出结尾没报错。
3. **`./build.sh` / `make` 打印了东西不等于成功**。取 `PIPESTATUS[0]`，
   或去翻产物清单和 `debugfs`，别翻日志关键字。

## 长任务一律 run_in_background

几十分钟以上的编译/传输：`run_in_background: true`，日志**双写**（VM 上 `tee`，本地也留一份），
结束后再 `grep` 结果行，不要中途轮询。回来看：

```bash
grep -n "=== rc=\|BUILD_DONE" /tmp/xxx.log; tail -25 /tmp/xxx.log
grep -nE "ERROR:|E: |failed" /tmp/xxx.log | head    # 首个 ERROR 才是真凶，后面的都是级联
```

## 本机 VM 别名（`~/.ssh/config`）

| 别名 | 谁 | 用途 |
|---|---|---|
| `rk-vm` | `rk@192.168.234.141`（NAT，单网卡） | KICKPI K11C / RK Linux SDK 编译 |
| `vm-laide` | `laide@192.168.64.130` | SNM970 安卓 BSP 编译 |

**两台不要同时开机**（43G + 15.6G > 宿主机 64G）。两台的规矩不通用：
安卓那台"别动 `/usr/bin/python`、别装 `python-is-python3`"是红线；
RK 这台官方清单就要求装它，照做即可。
