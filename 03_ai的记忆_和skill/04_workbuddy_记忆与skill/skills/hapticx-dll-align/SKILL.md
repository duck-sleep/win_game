---
name: hapticx-dll-align
description: Windows HapticX 对着雷云编码器 DLL 抄计算时使用。用户要改 25_xbox_control 的官方路径、对帧、查和雷云的差异、或说「按供应商抄」时加载。产品路径禁止加载 DLL；差异只认逐帧对照。
---

# HapticX 按 DLL 抄

代码在 `D:\win_game_project\25_xbox_control`。收口记录在 `03_ai的记忆_和skill\01_记忆原档\projects\25_xbox_control\project_memory.md`。给人看的流程是 `25_xbox_control\03_new_review\音频转触觉_流程图.html`。

2026-10-13 用户确认这件事做完。没有新的实测之前，不要把「整首歌已经和雷云一样」写进文档。

## 什么时候用

- 改 `hapticx/a2h_encoder.py`、`har_pack.py`、`pipeline.py`、`ihhe.py`、`sensa_out.py`
- 用户说手感和雷云不一样、要对照、要逆向某一帧

## 硬规则

- 产品路径不 `LoadLibrary` 雷云 DLL。对照脚本可以加载。
- 不凭听感改算法。先同一段 PCM 逐帧对 DLL，再改。
- 不发明「力度为 0 就把音高清掉」。DLL 没有这条。
- 不把曲线幅度塞进瞬态槽。不把 50 或 54 写成常数。`round(幅度 × 63)`：0.80 → 50，0.85 → 54。
- 滑条只乘力度一次。音高不乘。`config.json` 里的 `gain` 就是这一次，默认意图是 0.67。
- 马达要的是 91 字节 Feature 报告，报告号 4。组包在 `hapticx/ihhe.py` 的 `wrap_feature4`。
- 设备是 Sage T1：部位 216 / 116，频率 30–400 Hz。不要按 Esther T0 改。

## 产品路径

WASAPI 环回（`wasapi_loopback.py`，48 kHz 时 960 点）→ `A2HEncoder.process_block` → `frame_scaled(滑条)` → `wrap_feature4` → `HidD_SetFeature` 到 VID 1532 / PID 0A4C 的 COL04。

每 20 毫秒一块，计算和发包都在采集线程里，没有单独的发包定时器。

## 算法（SENSA HD，和 DLL 逐帧对过）

1. 左右各留 `round(采样率 × 0.125)` 个原始样本。每块从零状态重滤整段，不沿用上一块的 IIR 状态。
2. 带通：`FUN_180029aa0`，阶数写死 2。band 0 是 30–100 Hz 音量 0.3，band 1 是 100–200 Hz 音量 0.1。底层音量 6。
3. 力度：最后 30 毫秒 `(最大 − 最小) × 0.5`。门限 0.005。EQ 在压缩前（0/50 Hz=0.5，100/150=1，200=0.5）。压缩 amp_comp 0.25、ratio 0.3、上限 1，再 `ln(5y+1)`。带外 50 Hz 裙边。
4. 音高：6000 点补到 8192 做 FFT，Hz = 格子 × 采样率 / 8192。60 Hz → 58.59375 Hz → 音高码 9。每只手用自己那一路。
5. 瞬态：`FUN_18001f670`，扫原始波形。每个谷都更新参考值（`0x18001FCCA`）。prominence 1.4，时长 0.022 秒。每只手最多两条，只扫自己的声道。216 用左，116 用右。
6. 量化：力度 `round(x × 63)`，音高截断 `(clamp(Hz,30,400) − 30) × 127 / 370`。

## 重跑对照

```
py _tools\probe_lr.py
py _tools\probe_frames.py
py _tools\compare_grid.py
```

工作目录是 `25_xbox_control`。DLL 在 Razer AppEngine 的 `RzInterhapticsHapticEncoder_v2.0.1.11.dll`，反汇编用 `02_baidu\baidu_InterhapticsHapticEncoder_v2.0.1.11.dll`。进程退出 `-1073740940` 出现在打印之后，以打印为准。不要 `ReleaseEncoder`。

左右相同的纯音、敲击、扫频，以及左右不同的三段，2026-10-13 都是 0 帧不同。改完编码器必须把这三支再跑一遍。

## 不要重做的弯路

- 搜立即数 50，或用 0.79 对 0.81 当瞬态门限。门限是 prominence 1.4，0.70 的正弦才开始有瞬态，码是 44。
- 增量 IIR。声音离开窗口后音高还在，是因为状态没清。DLL 每次新建滤波器。
- 用最大绝对值当力度。DLL 是 `(最大 − 最小) × 0.5`。
- 把自制 `analyzer.py` 的 XInput 路径拿来和雷云比。那条没有频率。
