package com.meig.hapticx.audio

import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioTrack
import android.util.Log

/**
 * TonePlayer — 自播自采测试用:播一段 USAGE_MEDIA 正弦波。
 * 用途:验证播放采集链路(自身音频必可被采集,排除第三方客户端因素)。
 */
class TonePlayer(
    private val durationSec: Int = 10,
    private val freqHz: Int = 440,
    private val sampleRate: Int = 48000
) {
    private var track: AudioTrack? = null
    @Volatile private var playing = false
    private var thread: Thread? = null

    fun start() {
        if (playing) return
        playing = true
        thread = Thread({
            try {
                val totalFrames = sampleRate * durationSec
                val attrs = AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                    .build()
                val format = AudioFormat.Builder()
                    .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                    .setSampleRate(sampleRate)
                    .setChannelMask(AudioFormat.CHANNEL_OUT_STEREO)
                    .build()
                // MODE_STREAM:流式写入,走 MIXER 线程(与真实游戏 OpenSL/普通 AudioTrack 一致),
                // 才会触发播放采集的 secondary outputs 影子轨机制。MODE_STATIC 会被路由成 DIRECT 直通轨绕过 mixer。
                // 注意:mono 会被路由到 DIRECT 输出(绕过 mixer),必须用 stereo 模拟真实游戏。
                val minBuf = AudioTrack.getMinBufferSize(sampleRate,
                    AudioFormat.CHANNEL_OUT_STEREO, AudioFormat.ENCODING_PCM_16BIT)
                track = AudioTrack(attrs, format, maxOf(minBuf, 4096),
                    AudioTrack.MODE_STREAM, AudioManager.AUDIO_SESSION_ID_GENERATE)
                Log.i("HapticXTone", "测试音开始: ${freqHz}Hz ${durationSec}s USAGE_MEDIA (MODE_STREAM stereo)")
                track?.play()
                val buf = ShortArray(2048)
                var written = 0L
                val total = sampleRate.toLong() * durationSec
                while (playing && written < total) {
                    for (i in buf.indices) {
                        val s = (12000 * Math.sin(2.0 * Math.PI * freqHz * (written + i / 2) / sampleRate)).toInt().toShort()
                        buf[i] = s
                    }
                    val n = track?.write(buf, 0, buf.size) ?: 0
                    if (n <= 0) break
                    written += n / 2
                }
                Thread.sleep(500)
                Log.i("HapticXTone", "测试音结束")
            } catch (e: Exception) {
                Log.e("HapticXTone", "测试音异常: ${e.message}")
            } finally {
                stop()
            }
        }, "HapticXTone").also { it.start() }
    }

    fun stop() {
        playing = false
        try { track?.stop() } catch (_: Exception) {}
        try { track?.release() } catch (_: Exception) {}
        track = null
    }
}
