---
name: machenike-g6v2-hd-rumble-line
description: 机械师 G6 V2（NS 模式）HD 振动 / 唱小星星线：协议、已证结论、量化对比、待拍板项与工具清单
metadata:
  type: project
---

# 机械师 G6 V2（NS 模式）HD 振动线

工程：`D:\win_game_project\24_machine_teacher_control\`；工单文档：`12_win_上机跑\16_机械师唱小星星.md`（N0–N9 编号，用户开新对话只贴「开场白 + 工单号」，**一次一号，做完就停**）。
**Why**：用户买了这只手柄（双 HD 音圈马达 + 三模），想要一个和 `25_xbox_control`（雷蛇 Sage T1 的 HapticX）**同级但专给它用**的程序，还要能"唱歌"。
**How to apply**：动这条线之前先读 16_ 的「全局禁令」9 条（不改 25、不 LoadLibrary 供应商 DLL、振幅档 ≤100、不发 `80 06`/`80 92`、只走 USB HID、跑前关 Steam/BetterJoy/DS4Windows、"已证实"必须有本机输出或用户手感、不 `git add -A`）。

## 一句话本质

**这只手柄切 NS 模式 + USB 直连，在 Windows 眼里就是任天堂 Pro Controller（`057E:2009`，厂商串 `Nintendo Co., Ltd.`，序列号 `000000000001`）。**
HD 振动 = 每只手两个振荡器（高频 81.75–1252.57 Hz、低频 40.88–626.29 Hz），主机每 ~20 ms 发一个 64 字节输出报告 `0x10`，前 4 字节左、后 4 字节右。唱歌 = 按音符换频率。

## 已证（都有本机输出）

- 握手：`80 02 → 81 02`、`80 03 → 81 03`、`80 02`、`80 04`（不等）、子命令 `48 01` ACK；之后约 8 ms 一个 `0x30` 输入报告。重跑不用拔线。
- **频率真有效（N1 闸门过了）**：160/320/640 Hz 三段用户分得出 ⇒ 不属于 SDL 警告的那种「非零就当开关」的兼容手柄。
- 强弱分得出（0.2/0.5/0.8）；320 Hz 连续 8 秒不断 ⇒ **发包间隔定 20 ms**，不用退到 SDL 的 30 ms。
- 编码/映射对拍全过：`tests/` 共 **11 个测试**（标准值表 13 行逐字节、amp_index 10 行、雷云曲线两个 golden 用例、映射 3 个字节例、瞬态去重 32 次 + 前 5 次时刻）。
- 音频环回：边放歌采 8 秒 `400 块 / 空块 0 / 峰值 1.0000`。
- 真实音频喂整条链：`test_50hz.wav` 200 块**全部非静止**、6 种字节组合。
- GUI 跑通：`hapticx_ns/app.py` 起来后状态栏 `NS 0x10 已连接 · 捕获 运行 · 已发 362 包`，仪表板显示最近一包 `00 01 40 40 | 00 01 40 40`。
- **小星星认得出旋律**：用户原话「虽然真的是在唱歌了…小星星唱的很好听」（2026-11-04）。

## 和雷蛇版的算法一致性（2026-11-04 实测，`tools\compare_algorithms.py`）

- **来源层相同**：同一份音频，25 的 `a2h_encoder` 与 24 用的那份逐块比，`来源曲线相同：True`，力度/Hz 差 `0.00e+00`。
- **量化层不同，而且反直觉**：落到设备的音高误差 —— 30–60 Hz 段**雷蛇 81–82 音分 vs NS 10–20 音分**；60–120 Hz 雷蛇 54.9 vs NS 6.3；120–250 Hz 雷蛇 18.6 vs NS 6.6。
  原因：雷蛇 `q7_hz` 是 **30–400 Hz 等分 128 格（每格 2.91 Hz）**，越低越不准；NS 是 **1/32 八度等比（±18.75 音分恒定）**，但有两个硬下限（高频 81.75 / 低频 40.88）。振幅误差两边都 ≈0.004。
- **模式/频段编辑在两边都是摆设**：`A2HEncoder.set_band_gains()/set_band_edges()` 就是 `return None`，`reconfigure()` 只认 gain/profile ⇒ 走「对齐雷云」路径时 dynamic/balanced 不生效。**这不是 24 的缺陷，别当成 bug 去修。**
- 用户同时跑两边说"唱的不太一样"，实测有一部分只是**旋钮差**：雷蛇 `gain=0.85 mode=dynamic`，机械师 `gain=0.931 mode=balanced`。

## 🔴 待拍板 / 待测（别自己定）

1. **低频内容把高频振荡器夹歪**：40→900 Hz 扫频里 **54/300 块** 想发的 Hz < 81.75 被夹，最大偏 **759 音分** ⇒ 低音重的歌会有个固定高音垫着。三选一：① 并进低频振荡器 ② `hf_amp` 归零 ③ 保持现状。**手感取向，只有耳朵能判。**
2. **单侧不震**：只发左（右=NEUTRAL）或只发右，用户都感觉不到；两侧都发才震 ⇒ **不是左右反**（`SWAP_LR` 保持 False）。四种可能没排除，用 `tools\rumble_test.py --lr-matrix` 八段定性。**若结论是"混成一路"，立体声分离做不了，N7 第 4 条判据注定失败。**
3. N8 验收：四个按钮点一遍 + 关窗后确认不再震。
4. N7 四条手感（停音乐立刻停 / 低音更强 / 鼓点敲击感 / 左右分得出）；瞬态与包络仍是**设计未校准**（`TRANSIENT_HZ=160`、`TRANSIENT_PACKETS=2`）。

## 交付形态（用户明确要的）

**桌面上两个可执行入口，靠颜色区分**：绿 = 雷蛇 `25_xbox_control\启动HapticX.bat`；蓝 = 机械师 `24_machine_teacher_control\启动.bat`。
`hapticx_ns/` 是**整套照抄 25 版式**（四页 UI + 卡片/胶囊/滑条/频谱/频段编辑器），只换三层：出口=NS `0x10`、编码器只剩「对齐雷云」（不 LoadLibrary DLL）、设备页=HID 枚举 + 抢手柄软件检测。
色板 `ui\theme.py`：`#44d62c` 雷蛇绿 → `#2f7bff` 机械师蓝，**标识符一并改名**（`GREEN→BLUE`，原来的 Sensa 青 `BLUE→CYAN`），不留"名字叫绿其实是蓝"。
四处有意偏离都写在代码注释和 README：不加载 DLL / 不用 haptic_mixer+har_engine（雷蛇多部位混音层）/ 模式与频段不生效 / 「游戏内触觉」诚实置灰。
**编码器只存一份**：`hapticx_ns\a2h_encoder|har_pack|wasapi_loopback.py` 是名称转发（`sys.modules[__name__] = ns_rumble.vendor.对应模块`），真身在 `ns_rumble\vendor\`。

## 工具清单（都可复跑）

`tools\probe_ns_usb.py`（握手探针）、`probe_audio.py`（环回，不碰手柄）、`rumble_test.py`（四组手感题 + `--lr-matrix` + `--selftest`）、`offline_wav_check.py`（真实 wav 喂整条链）、`compare_two_apps.py`（两边编码器逐块 + 量化反解）、`compare_algorithms.py`（来源/量化/旋钮三层对比）；
CLI：`live_a2h.py`、`sing_star.py`（`--scale/--octave/--bpm/--legato`）、`tone.py`（`--hz/--amp/--sec/--side/--send-ms`）；
四个双击入口：`启动.bat`、`测试振动.bat`、`唱小星星.bat`、`实时振动.bat`、`听音频探针.bat`。

相关：[[k11c-ip-kvm-line]]（同项目的另一条线）、[[feedback-follow-reference-implementation]]（这条线的做法被它纠正过一次）
