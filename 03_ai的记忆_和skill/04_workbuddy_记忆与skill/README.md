# 04_workbuddy_记忆与skill — 说明

> 这是 WorkBuddy（当前 AI 助手）在本项目中的**记忆与 skill 存放区**。
> 用户约定（2026-09-02）：WorkBuddy 的记忆和 skill 统一放这里，与 TRAE 记忆区并列。

## 文件结构

```
04_workbuddy_记忆与skill\
├── README.md              ← 本文件
├── MEMORY.md              ← ★ 项目长期记忆（稳定事实、进展快照、踩坑）
├── 日志\YYYY-MM-DD.md      ← 每日工作日志（按天追加，不覆盖）
└── skills\<名称>\SKILL.md  ← 固化的项目工作流 skill
```

## skill 清单

| skill | 用途 | 何时用 |
|---|---|---|
| **snm970-context-recover** | ★ 新会话上下文恢复三步法 | 会话重开 / 上下文崩了，第一步就加载 |
| push-to-snm970-storage | 推 ROM/大文件到掌机 SSD（USB vs WiFi 通道、模式切换、md5 校验） | 传游戏、装 APK |
| api-endpoint-slow-diagnosis | API 端点慢/断连五步诊断（含无线侧最后一公里） | 模型回答慢、429/500/10054 |
| hapticx-png-guard | PNG 生成规范（大端 `>I`，坏图会报废会话） | 写截图/出图脚本 |
| snm970-aarch64-static-bin | 掌机端 aarch64 静态二进制编译 | 需要板子上跑的静态工具 |

## 恢复顺序（新会话 / 上下文断了）

1. `..\02_知识库_整理版.md` —— 通用项目背景
2. `MEMORY.md` —— WorkBuddy 侧增量与当前状态
3. `日志\` 最近 1~2 天 —— 昨天进行到哪一步

> 也可以直接调用 skill `snm970-context-recover`，里面写好了这三步。

## 维护约定

- 每次会话产生重大进展（编译、刷机验证、PR、新问题诊断）后：当天日志追加，必要时更新 `MEMORY.md`
- 重复性工作流程（3 步以上、下次还会用到）固化成 `skills\<名称>\SKILL.md`
- 通用项目背景以 `..\02_知识库_整理版.md` 为准，这里只记 WorkBuddy 侧的增量（工作习惯、踩坑、待办）
- `.workbuddy\memory\` 只保留指针，正文一律写在这里
