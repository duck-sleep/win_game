---
name: Long-term memory
description: Lessons learned from past tasks
metadata:
  type: feedback
---

# SNM970 项目长期笔记（WorkBuddy）—— 指针文件

> ⚠️ **本文件只做指针，不写正文。所有 AI 共用这套目录约定。**
> 用户约定（2026-09-02 起，2026-09-12、2026-10-15 两次重申，对象是**每一个**接手的 AI）：
> - **AI 的记忆与 skill** → `D:\win_game_project\03_ai的记忆_和skill\`
>   其中 WorkBuddy/Qoder 侧正文放 `04_workbuddy_记忆与skill\`（`MEMORY.md` + `日志\YYYY-MM-DD.md` + `skills\<名>\SKILL.md`）
> - **给人看的文档** → `D:\win_game_project\12_win_上机跑\`（Markdown，编号命名 `01_`…`12_`，结论先行）
> - 旧 `04_ai和运行资料\` 已在 09-04 并入 `12_win_上机跑\`，**不要再往那里写**

## 恢复流程（新会话照这个走）
1. 读 `00_START_新会话入口.md`（约 20 行，状态快照 + 1 分钟阅读路线）
2. 读 `...\04_workbuddy_记忆与skill\MEMORY.md`（永久事实：技术结论/坑/命令）
3. 读 `...\日志\` 里最近 1~2 天的日志（详细进展）
4. 需要细节时翻 `...\01_记忆原档\` 里对应日期的 jsonl/topics

> 也可直接调用 skill `snm970-context-recover`（位于 `...\skills\`）。

## 快照（2026-09-12 深夜更新；详见 00_START_新会话入口.md）
- HapticX Android 板上现役 **0.1.17**：真采（AudioPlaybackCapture）+ 四档 + 悬浮马达条，DSP 已对齐 Windows analyzer.py（只看 30–130Hz，CAPTURE_SCALE=2.5）。动态档放 SSD 歌已实震
- 采集-FF 链路全通：xone + eventN + root ff_bridge 读 HapticXOut 实震。停震=强度0+EV_FF。板载 hv-haptics 也有 FF_RUMBLE 别发错节点
- 固件源已齐（**尚未 inc 出包**）：QSSI 预装 0.1.17 APK + kalama.mk A2DP offload 属性 + 两份策略 XML + hapticx_ff/ 开机桥 + appops。刷完仍要点一次「开始捕获」
- ⚠️ Git 仓 App 源码仍 0.1.0，0.1.17 只在板子/VM/本地工程，未 commit
- OTG 供电：VBUS=0 由带电 hub 反向供电板子（11.87V），方案成立；USB peripheral 传文件 33.5MB/s ≫ WiFi 10 倍
- SSD 已收官；AetherSX2 已装回 v1.5-3668（OnionKnight 看不到 sideload 图标，用 am start）
