package com.meig.hapticx.audio

import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioPlaybackCaptureConfiguration
import android.media.AudioRecord
import android.media.projection.MediaProjection
import android.util.Log

/**
 * PlaybackCaptureEngine — 安卓侧的"WASAPI loopback 等价物"。
 *
 * 用 AudioPlaybackCapture(API 29+)监控设备当前正在播放的媒体/游戏声音,
 * 以 20ms 块(960 samples @48kHz mono)回调给 DSP——与 Windows 版 HapticX
 * 的 soundcard loopback 块节奏完全一致。
 *
 * 已知限制(见 10_安卓雷云技术.md §捕获):
 *  - 用户每次授权 MediaProjection 会弹窗(可申请"始终允许"减少打扰)
 *  - 目标 app 可 opt-out(USAGE 媒体默认可采;GAME 可采;通话/DRM 永不可采)
 */
class PlaybackCaptureEngine(
    private val projection: MediaProjection,
    private val onBlock: (DoubleArray) -> Unit,
    private val onError: (String) -> Unit,
) {
    companion object {
        const val TAG = "HapticXCapture"
        const val SAMPLE_RATE = 48000
        const val BLOCK = 960          // 20ms,与 FFT_HOP 一致
        const val CHANNELS = 1
    }

    private var record: AudioRecord? = null
    @Volatile private var running = false
    private var thread: Thread? = null

    /** 音量监测回调(0-1,用于 UI 显示输入电平,可选)。 */
    @Volatile var onLevel: ((Double) -> Unit)? = null

    fun start() {
        if (running) return
        running = true
        // AudioRecord 创建涉及 audioserver binder 往返,必须在工作线程做,
        // 否则 audioserver 打嗝时会卡住主线程造成 ANR(2026-09-03 真机踩坑)
        thread = Thread({
            try {
                initAndLoop()
            } catch (e: Exception) {
                onError("捕获线程异常: ${e.message}")
            }
        }, "hapticx-capture").apply { start() }
    }

    private fun initAndLoop() {
        val captureConfig = AudioPlaybackCaptureConfiguration.Builder(projection)
            .addMatchingUsage(AudioAttributes.USAGE_MEDIA)
            .addMatchingUsage(AudioAttributes.USAGE_GAME)
            .addMatchingUsage(AudioAttributes.USAGE_UNKNOWN)
            .build()

        val format = AudioFormat.Builder()
            .setEncoding(AudioFormat.ENCODING_PCM_FLOAT)
            .setSampleRate(SAMPLE_RATE)
            .setChannelMask(AudioFormat.CHANNEL_IN_MONO)
            .build()

        val minBuf = AudioRecord.getMinBufferSize(
            SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_FLOAT)
        if (minBuf < 0) { onError("AudioRecord.getMinBufferSize 失败: $minBuf"); return }

        val rec = AudioRecord.Builder()
            .setAudioFormat(format)
            .setBufferSizeInBytes(maxOf(minBuf, BLOCK * 4 * 4))
            .setAudioPlaybackCaptureConfig(captureConfig)
            .build()
        if (rec.state != AudioRecord.STATE_INITIALIZED) {
            rec.release()
            onError("AudioRecord 初始化失败(state!=INITIALIZED)——检查 MediaProjection 授权")
            return
        }
        record = rec
        rec.startRecording()
        Log.i(TAG, "捕获已启动: ${SAMPLE_RATE}Hz mono float, ${BLOCK} samples/块")
        captureLoop(rec)
    }

    private fun captureLoop(rec: AudioRecord) {
        val chunk = FloatArray(BLOCK)
        var blockCount = 0
        var windowPeak = 0.0
        while (running) {
            val n = rec.read(chunk, 0, BLOCK, AudioRecord.READ_BLOCKING)
            if (n < 0) { onError("AudioRecord.read 错误: $n"); break }
            if (n == 0) continue
            val block = DoubleArray(n)
            var peak = 0.0
            for (i in 0 until n) {
                block[i] = chunk[i].toDouble()
                val a = kotlin.math.abs(block[i])
                if (a > peak) peak = a
            }
            windowPeak = maxOf(windowPeak, peak)
            if (++blockCount % 50 == 0) {   // 每 ~1s 打印输入电平,诊断采集链路
                Log.i(TAG, "输入电平 peak=%.4f (块%d)".format(windowPeak, blockCount))
                windowPeak = 0.0
            }
            onLevel?.invoke(peak)
            onBlock(block)
        }
    }

    fun stop() {
        running = false
        thread?.join(500)
        thread = null
        record?.apply {
            try { stop() } catch (_: Exception) {}
            release()
        }
        record = null
        Log.i(TAG, "捕获已停止")
    }
}
