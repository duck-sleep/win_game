# 24 · 机械师 G6 V2（NS 模式）唱小星星 + 音频转振动

工单在 `D:\win_game_project\12_win_上机跑\16_机械师唱小星星.md`。这份 README 只写**怎么用**和**现在到底证到哪一步**。

## 这是什么

这只手柄切到 NS 模式、USB 直连时，在 Windows 眼里就是一只**任天堂 Pro Controller**
（`057E:2009`，厂商串 `Nintendo Co., Ltd.`）。所以走的是任天堂的 HD 振动协议：
每只手两个振荡器（高频 + 低频），每个振荡器给 **频率 + 振幅**，主机每 20 ms 发一个 64 字节输出报告。

唱歌 = 按音符换频率；音频转振动 = 复用 `25_xbox_control` 里那套**和雷云 DLL 逐帧对过**的编码器，
把它每 20 ms 吐出的两条曲线（力度, Hz）塞进这两个振荡器。

## 怎么跑（全部双击，不用记命令）

| 双击这个 | 干什么 | 要不要手柄在手上 |
|---|---|---|
| `启动.bat` | **主程序**（N8，照抄雷蛇那版的版式，绿→蓝）：动态触觉 / 配置文件 / 设备 / 设置 四页 | 要 |
| `实时振动.bat` | 命令行版实时转振动，每 10 块打一行左右字节（N7） | 要 |
| `唱小星星.bat` | 命令行版唱歌；想唱音阶就在命令行后面加 `--scale`，换八度加 `--octave 3`（N4） | 要 |
| `测试振动.bat` | 四组手感题（频率/左右/强弱/持续）+ 第 6 项**左右隔离矩阵**（N1/N3） | 要 |
| `听音频探针.bat` | 只查「电脑声音环回抓不抓得到」，**不碰手柄** | 不要 |

## 桌面上现在有两个 HapticX，怎么分

| | 雷蛇版 | 机械师版（这里） |
|---|---|---|
| 目录 | `D:\win_game_project\25_xbox_control` | `D:\win_game_project\24_machine_teacher_control` |
| 入口 | `启动HapticX.bat` | `启动.bat` |
| 窗口标题 | `HapticX — SENSA HD 触觉反馈` | `HapticX · 机械师 G6 V2（NS HD 振动）` |
| 点缀色 | **雷蛇绿** `#44d62c` | **机械师蓝** `#2f7bff`（背景也冷一档） |
| 出口 | 雷云 SENSA 比特流（Feature 4 / `HidD_SetFeature`）或 XInput | 任天堂 `0x10` 振动报告（每只手高频+低频振荡器） |
| 编码器 | 可选「自制 A2H」/「按供应商抄」（会 LoadLibrary 雷云 DLL） | **只有「对齐雷云」这一种，不加载任何供应商 DLL** |
| 设备页 | 从雷云 4 日志提取情报 | HID 枚举 + 抢手柄软件检测（不读雷云日志） |
| 配置文件 | `hapticx\config.json` | `hapticx_ns\config.json`（互不干扰） |

**移植时四处有意偏离**（不是漏了，是刻意的，代码里都留了注释）：

1. **不 LoadLibrary 雷云/Interhaptics DLL，也不发 SENSA 比特流** —— 本手柄不需要那套固件合成层；
2. **不用 `haptic_mixer` / `har_engine`** —— 那是雷蛇多部位马达的混音层，本手柄只有左右两只；
3. **UI 的「模式」和「频段增益编辑」驱动不了对齐配方**（配方写死在 `SYNAPSE_PROFILE`），
   这两个控件在这里**不生效**，频段图固定按 SENSA 的两条 band 显示；
4. **「游戏内触觉（Sensa HD）」那张卡诚实置灰** —— NS 协议没有这套 API，
   文案写的是「真不支持，不是开关没打开」。

**GUI 跑通的证据**（2026-11-04，程序自己开起来截图）：底部状态栏
`NS 0x10 已连接 · 捕获 运行 · 已发 362 包`；仪表板「音频源」那行是
`扬声器 (Realtek(R) Audio) 48000 Hz/2ch  00 01 40 40 | 00 01 40 40`
—— 末尾那 8 字节就是**最近真正发出去的一包**（没放音乐时是静止包），
说明 采集 → 编码 → 映射 → HID 写出 这条链在图形界面里是通的。

跑之前先关 **Steam / BetterJoy / DS4Windows / yuzu / Ryujinx**，它们会抢这只 Pro 手柄。

命令行方式（PowerShell）：

```powershell
cd D:\win_game_project\24_machine_teacher_control
$PY = "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"
& $PY live_a2h.py --gain 0.67 --print        # 实时转振动
& $PY sing_star.py --scale                   # 唱音阶
& $PY -m unittest discover -s tests -v       # 全部对拍
```

## 现在证到哪一步（2026-11-04）

**已证**（有本机输出或用户原话）：

| 项 | 结论 | 证据 |
|---|---|---|
| 枚举/握手 | `80 02/03/02` 全回、子命令 `48` ACK | `tools\probe_ns_usb.out.txt` |
| **频率有效** | 160/320/640 Hz 三段用户分得出 ⇒ 不是「非零即震」的开关型 | 用户原话 + `rumble_test.py` 第 1 组 |
| 强弱、持续 | 0.2/0.5/0.8 分得出；连续 8 秒不断 ⇒ **发包间隔定 20 ms** | 同上，第 3、4 组 |
| 编码正确性 | 标准值表 13 行逐字节全对（含 C4/G4/A4） | `tests\test_codec.py`，`Ran 5 tests OK` |
| 复制的编码器没坏 | 60 Hz / 左右不同频 两个用例与雷云对齐值全对 | `tests\test_a2h_golden.py`，`Ran 2 tests OK` |
| 映射 + 瞬态去重 | 三个字节例全对；去重触发 32 次、时刻全对 | `tests\test_a2h_map.py`，`Ran 4 tests OK` |
| 音频环回 | 边放歌采 8 秒：400 块、空块 0、峰值 1.0 | `tools\probe_audio.out.txt` |
| 真实音频驱动得出变化的包 | 喂 `test_50hz.wav`：200 块**全部非静止**、6 种字节组合、音高落在 46.9/52.7 Hz | `tools\offline_wav_check.out.txt` |
| 全链路能跑 | `live_a2h.py --seconds 5` 不放歌：254 块 / 5.1 秒，静止包 `00 01 40 40`，退出干净 | 本机 2026-11-04 |

**未证 / 待你判**：

- 🔴 **单侧不震**：只发左（右=静止）或只发右（左=静止），用户都感觉不到；两侧一起发才震。
  **不是左右反**，所以 `device.SWAP_LR` 保持 `False`。四种可能还没排除，用
  `测试振动.bat` → 选 **6**（八段隔离矩阵）来定位。
  ⚠️ 如果结论是「固件把左右混成一路」，那**立体声分离在这只手柄上做不了**，N7 的第 4 条判据会注定失败 —— 这不是代码问题。
- 唱歌**认不认得出旋律**、哪个八度最好听（N4 的题）；
- 实时转振动的四条手感题（N7）：停音乐是否立刻停、低音是否更强、鼓点有没有敲击感、左右分不分得；
- 瞬态要不要开、默认增益是不是 0.67。

## 已知局限（照实说）

1. **频率有量化台阶**：编码是 1/32 八度一档，最大误差 ±18.75 音分。实测 C4 261.63→263.32、
   G4 392.00→388.88、A4 440.00→442.85 Hz。唱出来的音是**近似音高**，别按绝对音准验收。
2. **映射是设计，不是抄来的**：雷云那条线交给固件去合成，NS 这边是我们自己把「两条曲线 + 瞬态」
   摊到两个振荡器上（曲线0→低频振荡器、曲线1→高频振荡器、瞬态→高频临时 160 Hz 持续 2 个包）。
   对不对只由你的耳朵判。可调的只有 `TRANSIENT_HZ`、`TRANSIENT_PACKETS`、默认增益三个数。
3. **等响的连打最多晚约 100 ms**：编码器每只手只有 2 个瞬态槽，新的要比旧的更响才替换，
   后面的等响敲击要等前面的滑出 125 ms 窗口。这是雷云 DLL 本身的行为，不是我们的 bug。
4. **振幅档夹到 100**（`HA=0xC8`）：dekuNukem 表里更高的值原文标注会伤 LRA，任何路径都不给过去。
5. 只走 **USB 有线**。蓝牙、XInput、ViGEm、装驱动、改注册表这些都不碰。

## 文件地图

```
启动.bat                  双击开主程序（工作目录切进 hapticx_ns）
hapticx_ns/               **N8 主程序：照抄 25 的版式，绿→蓝，出口换 NS**
  app.py                    四页 UI（仪表板 / HD 振动·NS协议 / 设备 / 设置）
  pipeline.py               采集→编码→映射→NS 写出（类名和方法签名跟 25 一致）
  ns_probe.py               设备情报（HID 枚举 + 抢手柄软件检测）
  ui/theme.py               色板：机械师蓝 #2f7bff（雷云版这里是雷蛇绿 #44d62c）
  ui/widgets.py             卡片/胶囊/滑条/开关/电平条（原样）
  ui/spectrum_canvas.py     实时频谱（原样）
  ui/band_gain_canvas.py    频段增益编辑器（原样；本程序里不驱动配方）
  analyzer.py / audio_capture.py / config_store.py / capture_window.py（原样）
  a2h_encoder.py / har_pack.py / wasapi_loopback.py
                            **名称转发**：真身只在 ns_rumble\vendor\ 存一份，避免两处副本
live_a2h.py               N7 实时转振动（主线程，采集块 = 发包节拍）
sing_star.py              N4 唱小星星 / 音阶
tone.py                   N3 单音（--hz --amp --sec --side --send-ms）
ns_rumble/
  codec.py              协议编码：amp_index / freq_code / encode_side / NEUTRAL
  device.py             NSController：open / init_usb / enable_vibration / send / stop / close
  song.py               简谱 → Hz（十二平均律，A4=440）
  a2h_map.py            A2HToNS：两条曲线 + 瞬态 → 左右各 4 字节（含绝对样本号去重）
  vendor/               从 25_xbox_control 原样复制的编码器（改动只有 1 行相对导入，见 SOURCE.txt）
tests/                  三套对拍，共 11 个测试
tools/
  probe_ns_usb.py       最早那份握手探针（N0）
  probe_audio.py        听音频探针（不碰手柄）
  rumble_test.py        四组手感题 + 左右隔离矩阵
  offline_wav_check.py  真实 wav 喂整条链，看字节会不会变（无人可验收时用）
*.bat                   上面这些的双击入口
```
