---
name: feedback-memory-mirrored-into-repo
description: Qoder 记忆必须镜像进仓库 03_ai的记忆_和skill 才算"存过"——本机那份别人看不到；跑 sync_qoder_memory.sh（自动脱敏 VM 口令）后提交
metadata:
  type: feedback
---

**存了记忆不等于记住了。** 用户 2026-10-21 说："这个记忆以后你都存在 `D:\win_game_project\03_ai的记忆_和skill`，
之前和你说过的，所以你现在把自己的揉进去，**大家用一份**。"

⇒ 每次写完 Qoder 自动记忆，**必须再跑一次同步**才算落盘到共享区：

```sh
sh "D:/win_game_project/03_ai的记忆_和skill/sync_qoder_memory.sh"
# 然后 git commit（用户偏好：改动攒着让他看过再提交，别自作主张推）
```

它把两处镜像到 `01_记忆原档\qoder-cn\`：
`C:\Users\123456\.qoder-cn\memory\`（用户级）+ `C:\Users\123456\.qoder-cn\projects\D--win-game-project\memory\`（项目级）。

**Why:** 这台机器上同时有 TRAE、WorkBuddy、Qoder 几套 AI 在接力同一条线。各家的自动记忆目录互不可见，
"我记下了"对别人等于没记。用户要的是**一份共享记忆**，不是每家一份私有笔记。
（对照 [[feedback-save-discussion-baselines]]：那条讲"咨询型讨论也要主动落盘"，这条讲落到**哪里**才算数。）

**How to apply:**
- ⚠️ **不要把 Qoder 的记忆目录挪走或删掉** —— 那是它自己读的路径，挪了下次会话直接失忆。仓库里那份是**镜像**，
  顺序永远是"写本机 → 跑同步 → 提交"。
- 🔴 同步脚本会自动把**编译 VM 的 sudo 口令**脱敏（那条规矩是"绝不写进仓库文件"，见 [[rk-vm-k11c]]），
  脚本末尾有自检、残留明文就报错退出。**别为了省事绕过它手工 `cp`。**
- 家里 WiFi 口令 `00000000` 和板子 sudo 口令**用户已明确同意进仓库**（"安全问题无所谓 就我用"），不用脱敏；
  但那前提是仓库 private —— 见 [[k11c-ip-kvm-line]] 里那条待确认项。
