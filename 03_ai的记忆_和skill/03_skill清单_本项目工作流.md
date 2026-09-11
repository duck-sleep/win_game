# 本项目工作流 Skill 清单（TRAE 环境）

> 整理日期：2026-08-27
> 说明：TRAE 里可用的 skill 列表（`/skill名` 或自动触发）。这里只整理**本项目实际会用到**的，按场景分类，附使用要点。

---

## 一、核心日常场景

### SSH 进虚拟机干活（最高频）

没有专门的"SSH skill"——直接用 **Shell 工具**执行 `ssh laide@192.168.64.130 "命令"`。
要点：
- 非交互执行，**sudo 带密码的命令跑不了**（需用户手动）
- 远端命令里的 `$`、引号会被本地 PowerShell 吃掉：awk/复杂管道易翻车，优先用简单命令或写脚本文件再执行
- 后台长任务（find 全盘等）用 run_in_background，结果写 output.log

### 长时间编译

**永远不进 TRAE 沙盒终端跑编译**（约 6-8 小时）。流程：
1. AI 改完代码 → 告诉用户指令
2. 用户自己 `tmux attach -t build` → 跑 `./SNM970_A15_build.sh ...`
3. 编译完 AI 进去验证产物（dtbo 6 处检查等）

**改动内核/DT/.ko 后的编译铁律（★★★ 最容易翻车）**：
- **必须先删** `rm -f device/qcom/kalama-kernel/Image` 再跑，否则 prepare_vendor 的 COPY_NEEDED 门控不触发，新改的东西根本进不了刷机包（表现为"编译 DONE 了板子上却没有"）。
- `inc`/`full` 都跑同样步骤，`full` 只多 OTA 包，**都不删 Image** —— 这条必须手动做。
- 验证产物别信 build 日志，用 `debugfs/vendor_dlkm.img` 或 `dtbo.img` 实测。详见 `12_win_上机跑/04_快速编译指令.md`「假成功根因」。此坑 09-11 反复踩过 2 次。

### 浏览器自动化（查 Gitea / 在线资料）

**TRAE-browseruse**：登录 http://106.52.24.80:3005 查同事提交、发 PR 等网页操作。
- 需要 登录/验证码/人工判断 时会交接浏览器给用户（browser_waiting_for_user_interaction）
- 登录 Gitea 用账号 981637988

## 二、文档写作场景

| Skill | 用途 | 本项目典型用法 |
|---|---|---|
| **doc-writing-guide** | 结构化文档总纲（PRD/报告/方案） | 写部署分析、提交流程文档 |
| **html-report** | 自包含 HTML 交付物（报告/白皮书） | 阶段性成果汇报 |
| **docx / pptx / pdf / xlsx** | 对应格式文件生成 | 用户明确要 Word/PPT/PDF 时才用 |

项目现有文档惯例（见 `12_win_上机跑/`）：**Markdown 为主**，编号命名（01_、02_…），结论先行。

## 三、研究查资料场景

| Skill | 用途 |
|---|---|
| **research-guide** | 搜索/调研/竞品分析/研究报告总纲 |
| WebSearch / WebFetch | 直接用工具查高通文档、内核文档等 |

## 四、代码相关场景

| Skill | 用途 |
|---|---|
| **skill-creator** | 想把重复流程固化成新 skill 时用（创建 SKILL.md） |
| lark-skill-maker | 飞书 API 封装成 skill（本项目暂用不到） |

## 五、飞书 / Lark 全家桶（如需协同）

trae-remote-official:lark:lark-im 发消息、lark-doc 文档、lark-drive 云盘、lark-sheets 表格、lark-task 待办等。首次使用需 RequestAuthorization 授权。**当前项目主要靠 git + 本地文档，暂未用到。**

## 六、其他工具型

| Skill | 用途 |
|---|---|
| xlsx | 处理 .xlsx/.csv（进度表、测试记录表） |
| dynamic-ui | 对话里内嵌图表/流程图（讲解设备树选择逻辑时挺好用） |
| feedback | 向 TRAE 官方提反馈 |
| TRAE-product-knowledge | TRAE 产品本身的问题 |

## 七、MCP 工具

当前启用 **integrated_code_mode**（Exec）：在隔离 JS 运行时里编排工具调用。适合把"多步固定流程"写成一段脚本一次跑完（比如：SSH 查状态 → 比对 → 出结论）。用前必须先 Read 对应 tool 的 JSON descriptor（`c:\Users\123456\.trae-cn\mcps\...\tools\`）。

## 八、经验教训（skill 使用层面）

- skill 是**按意图自动触发**的：用户说"写个报告"→ doc-writing-guide；说"打开网站看看"→ TRAE-browseruse
- 不要为了用 skill 而用 skill；简单问答/文件读写直接用基础工具
- 生成图片走 GenerateImage / Seedream；生成视频走 GenerateVideo / Seedance（本项目基本用不到）
