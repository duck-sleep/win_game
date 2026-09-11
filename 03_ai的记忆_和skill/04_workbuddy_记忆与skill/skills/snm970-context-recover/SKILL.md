---
name: snm970-context-recover
description: SNM970/OK700 掌机项目的新会话上下文恢复。当会话开始、上下文丢失、用户说"重新开始/上下文断了/你看看我们的资料"时使用。按顺序读取项目记忆文件，恢复项目背景、环境拓扑、当前主战场与工作约定。
agent_created: true
---

# SNM970 上下文恢复

新会话或上下文断裂时，按下面顺序执行，能在 1~2 分钟内把项目背景全部拉回来。

## 第一步：必读一份（光速启动）
| 文件 | 作用 |
|---|---|
| `D:\win_game_project\03_ai的记忆_和skill\00_START_新会话入口.md` | ✅ 20 行状态卡 + 阅读路线 + 环境速查；**新会话首选** |

## 第二步：按需深读（90% 场景不需要）
| 顺序 | 文件 | 作用 |
|---|---|---|
| 1 | `D:\win_game_project\03_ai的记忆_和skill\02_知识库_整理版.md` | 核心恢复手册：项目、环境拓扑、编译流程、三大坑、SSD 修复、提交流程 |
| 2 | `D:\win_game_project\03_ai的记忆_和skill\04_workbuddy_记忆与skill\MEMORY.md` | 永久有效事实：编译渊坑、日常指令、高频坑 Top 10 |
| 3 | `D:\win_game_project\03_ai的记忆_和skill\04_workbuddy_记忆与skill\日志\` 里**最近 1~2 天**日志 | 昨天/今天具体到哪一步 |

> 资料补充源（已并入 `12_win_上机跑\`）：01 工程说明、02 安卓工程教程、03 环境操作清单、04 快速编译指令、05 代码更新与提交、06 烧录说明、07/08 SSD、09 USB 排查、10 动态触觉反馈、11 安卓雷云技术、12 虚拟机联网。旧 `04_ai和运行资料` 已并入此目录。用户约定：记忆与 skill 放 `03_ai的记忆_和skill`，文档资料放 `12_win_上机跑`。

细节回溯再翻：`03_ai的记忆_和skill\01_记忆原档\当前项目_SNM970\按日期\YYYYMMDD\topics.md`（TRAE 时期原档）。

## 第三步：确认当前主战场

开工前先向用户确认"接着做哪块"，不要凭记忆自作主张。已知方向：

1. **HapticX 动态触觉反馈**——当前最活跃
   - Windows 端：Python/tkinter UI（profiles/config 页面、band audio range slider）`D:\win_game_project\25_xbox_control\hapticx\`
   - Android 端：采集已通（BT A2DP offload 修复），FF 驱动移植（xone GIP 驱动已搬入 kernel，待编译验证）
2. **BSP 编译/验证**（VM 内 6~8h，用户自己跑）
3. **掌机 OTG 手柄**（卡在 VBUS 输出，需带供电 Hub 复测）

## 第三步：遵守工作约定（用户明确要求过）

- 中文沟通
- **VM 配置修改用户自己动手**，AI 只给建议
- **6 小时以上的长编译用户自己跑**（VM 里 tmux），AI 不碰；改完代码发指令即可
- **刷机 / adb 验证用户在 Windows 端做**，adb 路径 `C:\platform-tools\adb.exe`（不在 PATH）
- 绝不 `git add -A`（本地有几百个编译副产物）；提交信息格式 `[SNM970_A15][TaskID]编号 [Description]... [Solution]... [Owner]...`
- 改内核 DT 或 .ko 后增量编译前必须 `rm -f device/qcom/kalama-kernel/Image`

## 环境速查

```
Windows 主机 → SSH laide@192.168.64.130 → Ubuntu 22.04 VM（6 vCPU / 43G / 1.3T）
代码：/home/laide/Desktop/10_code/{LA.VENDOR.15.4.3, LA.QSSI.15.0, qcm8550-...-modem_sign}
      （编译走不带 -irix 后缀的符号链接路径）
git：origin 指向不可达的群晖，一律用 gitea remote；网页 http://106.52.24.80:3005（981637988）
编译：cd LA.VENDOR.15.4.3 && ./SNM970_A15_build.sh userdebug kalama 01 2>&1 | tee build.log
产物：vendor/vendorcode/build/SNM970_userdebug_01.zip
```

## 记忆与 skill 存放约定

- 长期记忆：`03_ai的记忆_和skill\04_workbuddy_记忆与skill\MEMORY.md`
- 每日工作日志：`03_ai的记忆_和skill\04_workbuddy_记忆与skill\日志\YYYY-MM-DD.md`（追加，不覆盖）
- 本项目 skill：`03_ai的记忆_和skill\04_workbuddy_记忆与skill\skills\<名称>\SKILL.md`
- 重大进展（编译通过、刷机验证、PR、根因定位）后：当天日志追加 + 必要时更新 `MEMORY.md`
- 3 步以上、下次还会用到的流程，固化成新 skill
