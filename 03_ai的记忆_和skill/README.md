# 03_ai的记忆_和skill — 说明

> 这是 TRAE AI 记忆与 skill 的**项目内备份/整理区**。
> 目的：会话上下文断了、记忆丢了，都能从这里快速恢复。

## 文件结构
```
03_ai的记忆_和skill\
├── 00_START_新会话入口.md        ← ★★ 新会话第一读：1 分钟入口卡（状态快照 + 阅读路线）
├── README.md                      ← 本文件（目录说明）
├── 02_知识库_整理版.md            ← 通用项目背景（环境/编译/SSD/提交），入口卡不够时再读
├── 03_skill清单_本项目工作流.md   ← TRAE skill 清单（已过时，WorkBuddy 只看 skill 目录）
├── 01_记忆原档\                   ← TRAE 原始记忆冷档（按日期归档），日常勿读
└── 04_workbuddy_记忆与skill\      ← WorkBuddy（当前 AI）记忆区
    ├── MEMORY.md                  ← 长期记忆（只存永久事实：技术结论/坑/命令/时间线）
    ├── 日志\YYYY-MM-DD.md         ← 每日工作日志（只读最近 1~2 天）
    └── skills\snm970-context-recover\  ← 上下文恢复 skill（入口指向 00_START）
```

## 使用方式

- **上下文断了/换新会话**：先读 `00_START_新会话入口.md`（约 20 行，含当前状态表 + 阅读路线），需要更深背景再按入口卡指引读 `02_知识库_整理版.md` 或最近日志
- **想查细节**（某天具体聊了啥）：翻 `01_记忆原档\` 里对应日期的 jsonl/topics
- **原始记忆来源**：`c:\Users\123456\.trae-cn\memory\`（TRAE 自动维护，本目录是快照）

## 更新约定

- **每日收尾**：把当天进展写进 `04_workbuddy_记忆与skill\日志\YYYY-MM-DD.md`，并更新 `00_START_新会话入口.md` 的状态快照（保持"新会话读它就知道现在到哪了"）
- **重大进展**（编译通过、刷机验证、代码提交）后：更新 `00_START` 状态表 + `MEMORY.md` 时间线；`02_知识库_整理版.md` 只改长期有效的通用背景
- **原则**：`00_START` 和 `MEMORY.md` 里不堆过时细节——"当前状态"只活在入口卡里，MEMORY.md 只存永久事实
- **记忆同步（用户明确要求，必须执行）**：会话中存了新记忆后，AI 需把 `c:\Users\123456\.trae-cn\memory\` 下的 `projects\-d-win-game-project--p2-ea3144bba63d4aa9444e\project_memory.md`、按日期文件夹（含当天新增的 topics/会话jsonl）、`user_profile.md` 镜像拷贝到 `01_记忆原档\` 对应位置，保持两边一致
- 原档目录结构 = 真实记忆目录结构：project_memory.md 平铺、会话记忆放 `按日期\YYYYMMDD\`、不再保留旧平铺快照
