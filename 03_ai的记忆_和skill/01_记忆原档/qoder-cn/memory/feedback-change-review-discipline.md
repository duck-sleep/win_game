---
name: feedback-change-review-discipline
description: 用户说"我看看/晚点提交"就只创建文件不要 commit；盘点"改了哪些"必须查四类改动，git diff 会漏掉最要命的那两类
metadata:
  type: feedback
---

**规则 1：他说"我看看""晚点我们提交"，就只把文件建出来，一条 `git commit` 都不要发。**

**Why:** 2026-10-21 我在他说这句话之前，已经把一份内核补丁 commit + push 了（内容是对的，时机不对）。
他要的是**先看到全貌再决定进不进仓**；我替他决定，等于把他的审查环节跳过了。
**How to apply:** 凡是"整理出来给我看"类的要求 → 产出文件 + 在聊天里贴出关键内容 + 明确说"没提交，等你点头"。
已经提交了要**主动认**（一句"那次内容对、时机不对"就够，别辩解）。

**规则 2：盘点"我们到底改了什么"，`git diff` 只覆盖四类里的第一类，会漏掉最要命的。**

四类都要查：
1. 已跟踪文件被改 → `git diff --stat`
2. **本地未推送的 commit** → `git log --branches --not --remotes`（这类 diff 看不见）
3. **被 `.gitignore` 挡住的"状态"** → `git status --porcelain --ignored`
   （RK SDK 的 `device/rockchip/.chip` 就是：芯片选择记在这条软链上，被 ignore ⇒ 重装 SDK 静默丢失）
4. **仓库目录之外、同一台机器上只有一份的文件** → 按 mtime 扫（`find ~ -newermt` 排除已知目录）

**Why:** 同一次盘点里，第 1 类查出 3 个文件；但真正"丢了要重新踩一天"的是第 3、4 类 ——
内核 `CONFIG_USB_CONFIGFS_F_HID=y` 那行只在 VM 工作区（第 1 类，运气好查到了）、
`.chip` 选择（第 3 类）、`setup_rk_env.sh` 依赖安装器（第 4 类）。
**只跑 `git diff` 就会得出"改动都备份好了"的错误结论。**

**How to apply:** 任何"备份审计 / 改动清单 / 换环境要带什么"类的活，按这四类逐项跑，
并明确区分**"丢了只是重做时间"**（可重建的产物）和**"丢了就是知识丢失"**（配置、脚本、环境状态）。
