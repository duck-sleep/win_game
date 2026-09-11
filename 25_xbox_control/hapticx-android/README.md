# HapticX Android（安卓雷云）

Windows 版 HapticX 的安卓移植（阶段 1：DSP 移植 + 音频捕获）。
方案文档:`12_win_上机跑/10_安卓雷云技术.md`;算法底本:`25_xbox_control/hapticx/analyzer.py`。

## 当前状态(阶段 1)

- ✅ DSP 移植:`dsp/A2HAnalyzer.kt` 逐算法对齐 analyzer.py(四模式/EQ/门限/gamma/瞬态)
- ✅ FFT:`dsp/Fft.kt` 手写 radix-2 + Bluestein(2400 点窗非 2 次幂,与 numpy 对拍前提)
- ✅ **DSP 对拍**:`tools/crosscheck_gen.py`(Windows 基准) +
  `dsp/CompareMain.kt`(Kotlin 重放),60 块对拍
  **PASS**(马达偏差 ~5e-13,节拍序列逐块一致;2026-09-03)
  对拍抓出并修复 1 个移植 bug:Kotlin 版 FFT 忘了乘汉宁窗
- ✅ 音频捕获:`audio/PlaybackCaptureEngine.kt` MediaProjection + AudioPlaybackCapture,
  48kHz mono float、20ms 块,与 Windows 版块节奏一致
- ✅ 输出抽象:`haptics/HapticsOutput.kt`(手柄线挂起,先用 LogOutput 全链路验证)
- ✅ 调试 UI:启动/停止 + 四模式切换 + 实时频谱(16 对数频段)
- ⏳ 待办:频段增益编辑器 UI、真机验证

## DSP 对拍(改 DSP 后必跑)

```bash
# 1. Windows 基准(hapticx 目录,系统 Python 带 numpy)
cd /d/win_game_project/25_xbox_control/hapticx
python tools/crosscheck_gen.py        # → hapticx-android/tools/crosscheck_fixture.csv

# 2. Kotlin 重放(hapticx-android 目录)
export JAVA_HOME="D:\\android_build\\jdk"
export PATH="/d/android_build/jdk/bin:/d/android_build/gradle-8.7/bin:$PATH"
gradle :app:compileDebugKotlin --offline -q
"$JAVA_HOME/bin/java" -cp "app/build/tmp/kotlin-classes/debug;C:/Users/123456/.gradle/caches/modules-2/files-2.1/org.jetbrains.kotlin/kotlin-stdlib/2.0.0/b48df2c4aede9586cc931ead433bc02d6fd7879e/kotlin-stdlib-2.0.0.jar" \
  com.meig.hapticx.dsp.CompareMainKt tools/crosscheck_fixture.csv
# 末行 CROSSCHECK PASS = 两端数值一致
```

## 构建(本机工具链,已装好)

```
D:\android_build\jdk          Microsoft OpenJDK 17
D:\android_build\android-sdk  SDK(platform-34 + build-tools 34.0.0)
D:\android_build\gradle-8.7   Gradle
```

命令(Git Bash):

```bash
cd /d/win_game_project/25_xbox_control/hapticx-android
export JAVA_HOME="D:\\android_build\\jdk"
export PATH="/d/android_build/jdk/bin:/d/android_build/gradle-8.7/bin:$PATH"
gradle assembleDebug
# 产物: app/build/outputs/apk/debug/app-debug.apk
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

## 真机验证步骤(SNM970 掌机,Android 15)

1. `adb install` 后打开 HapticX
2. 点「开始捕获」→ 授权屏幕捕获弹窗(整页/媒体音量)
3. 播放音乐/游戏 → 频谱应跳动,马达读数变化
4. `adb logcat -s HapticXOut` 看左右马达强度序列(对拍数据源)

## 已知限制(与 Windows 版的差距)

- AudioPlaybackCapture 弹窗授权;游戏 opt-out 待真机实测(阶段 2 首要风险项)
- 输出暂为 LogOutput,手柄 FF(evdev/EVIOCSFF)等手柄到位后接
- config.json 导入、频段增益编辑器 UI 未做
