---
name: 2026-10-13 工作日志
description: Review project progress
metadata:
  type: project
---

# 2026-10-13 工作日志

## VM 安卓工程状态核实（记忆快照已过时）

VM `ssh laide@192.168.64.130`（up 13 天），源码 `~/Desktop/10_code/`。

**重大更正**：`00_START` 快照停在 09-12「固件源未 inc 出包」，实际另一个 AI 在 **09-13/09-14 已完成提交并出包**：

| 仓库 | 分支 | HEAD commit | 日期 | 内容 |
|------|------|-------------|------|------|
| QSSI | hapticx-preinstall | `359f69d454e` | 09-13 10:47 | 预装 HapticX 0.1.17（priv-app + platform 签名 + 权限白名单），qssi.mk:310 inherit |
| VENDOR | hapticx-a2dp-ff-xone | `aea9219c7a0` | 09-14 20:33 | 4 个 commit：A2DP offload 属性、ff_bridge 预置、xone GIP 移植、删 xone 嵌套副本 |

**刷机包已存在**（VENDOR 树根）：最新 `SNM970_EQ000_2774.C89630E57CC.359F69D454E.91E892303_260913_100_V01_T01.zip`（09-13 12:04，3.7G），另有 260904/05/10/11 共 5 个包。

**⚠️ 未收官项**：`hapticx_ff.rc` + `run_ff_bridge.sh` mtime = 09-14 20:30（修开机桥 restarting 死循环 + 去 logcat -c + sh 循环保活），**晚于 260913 包打包时刻**，即**任何包里都没有这个修复**。要收口需再跑一次 inc。

## 磁盘体检（清理决策依据）

- 磁盘：1.3T 总 / 782G 已用 / 488G 空闲
- **编译中间件**：VENDOR `out/` 144G + QSSI `out/` 166G + `kernel_platform/out` 6.7G = **≈317G**
- 最终产物：`vendor/vendorcode/build/` 36G、根目录 5 包 19G、modem 0.6G（均**不在** out/，删除不受影响）
- Windows `12_win_上机跑` 目录仅 3.9M（纯文档）

## AOSP 清理指令调研结论

- `SNM970_A15_build.sh`：**无任何 clean 逻辑**（inc/full 都不删 out/）
- AOSP build 系统：该树只有 `clean-dex-files`，**无标准 clean/installclean 目标**
- **Soong 时代官方清理方式 = `rm -rf out/`**，文档先例：`03_22.04环境操作清单.md` §3.3「删除旧 VM 的编译产物 out/（可选但推荐）」
- 雷云这批**不要删 `device/qcom/kalama-kernel/Image`**（未改内核；见 11_安卓雷云技术 §6）

## 待用户决策

删 out/（回收 317G，回编需全量 6~8h）之前，是否先跑一次 inc 把 09-14 修复打进最终包。

## 文档路径笔误（待修，会影响后续查找）

`12_win_上机跑\10_动态触觉反馈技术.md`、`10a_频率工单_给执行模型.md`、`01_记忆原档\projects\...\project_memory.md`
多处把活跃抓包目录写成 **`D:\win_game_project\13_win_cap\captures\`**，**漏了 `25_xbox_control\` 前缀**。

- 实际位置：`D:\win_game_project\25_xbox_control\13_win_cap\captures\`（107 个文件 / 4.7M，09-07 → 09-17，含 AB 对照 pcap、_out.txt 协议分析、协议候选模型.md）
- `13_win_cap\README.md` 于 2026-10-13 23:35 更新（另一个 AI 收口时写的），明确本目录用途

## `12_win_上机跑` 下两个 captures 目录定性

| 目录 | 时间 | 内容 | 定性 |
|------|------|------|------|
| `12_win_上机跑\captures\` | 2026-09-07 23:26 | pcap_setup.ps1 / pcap_run.ps1（3KB） | 早期副本，正式抓包已迁 `25_xbox_control\13_win_cap\captures\` |
| `12_win_上机跑\captures_freq\` | 2026-09-15 00:20（两份 md 当天 16:12 补） | razer_probe_raw.txt、雷云马达能力.md、听诊记录.md、公开接口调查.md（11KB） | 频率工单 W0.2/W0.3/W3A 的**产物落点**，被 10 / 10a 文档引用，非废料 |

合计仅 14KB，删除无收益。
