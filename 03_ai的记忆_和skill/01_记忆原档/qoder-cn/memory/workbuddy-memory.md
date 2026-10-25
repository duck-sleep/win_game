---
name: Long-term memory
description: Lessons learned from past tasks
metadata:
  type: feedback
---

# WorkBuddy 用户级长期记忆

> 跨项目通用的环境事实与用户偏好。项目专属内容不写这里。

## Git / GitHub（2026-09-11 配置）

- **GitHub 账号**：`duck-sleep`
- **GitHub 邮箱**：`ltw18505222732@gmail.com`
- git 全局身份已配：`user.name=duck-sleep` / `user.email=ltw18505222732@gmail.com`
- **SSH key**：`~/.ssh/id_ed25519`（注释写的 "Gitee SSH Key"，同一把复用给 GitHub，已登记在 duck-sleep 账号下）
- **⚠️ github.com 固定走 443**（`~/.ssh/config` 里配了 `HostName ssh.github.com` + `Port 443`），原因：本机 FlClash fake-ip 会把 github.com 解析到 `198.18.0.x`，22 端口直接超时；443 通道是 GitHub 官方支持的备用方案
- 备份：`~/.ssh/config.bak-20260911`
- 另有 `~/.ssh/vm_temp_key`（RSA 4096）用于连 VM

## 本机环境

- Windows，用户目录 `C:\Users\123456`，主机名 `DESKTOP-5F9N3OP`
- WorkBuddy 沙箱 Bash 的 PATH 可能缺 coreutils，脚本里建议先 `export PATH="/usr/bin:/bin:$PATH"`
- adb 不在 PATH，在 `C:\platform-tools\adb.exe`
- 装了 FlClash（TUN + fake-ip），排查网络问题时注意它会改写 DNS 解析结果
