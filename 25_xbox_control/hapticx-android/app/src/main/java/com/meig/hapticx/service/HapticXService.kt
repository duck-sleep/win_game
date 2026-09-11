package com.meig.hapticx.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationChannelGroup
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.util.Log
import com.meig.hapticx.audio.PlaybackCaptureEngine
import com.meig.hapticx.audio.TonePlayer
import com.meig.hapticx.dsp.A2HAnalyzer
import com.meig.hapticx.haptics.HapticsOutput
import com.meig.hapticx.haptics.LogOutput

/**
 * HapticXService — 前台服务:捕获→DSP→输出 的常驻管线。
 * 对标 Windows 版 pipeline.py;priv-app 化后此处可走特权捕获路径。
 */
class HapticXService : Service() {

    companion object {
        const val TAG = "HapticX"
        const val EXTRA_RESULT_DATA = "resultData"
        const val EXTRA_AUTO_TEST = "auto_test"
        const val CHANNEL_ID = "hapticx"
        private lateinit var instance: HapticXService
        fun isRunning(): Boolean = ::instance.isInitialized
        fun analyzer(): A2HAnalyzer? = if (isRunning()) instance.analyzer else null
        fun latestFrame(): Pair<Double, Double>? = if (isRunning()) instance.lastFrame else null
        fun vizSnapshot(): DoubleArray? = if (isRunning()) instance.analyzer?.viz else null
    }

    private var capture: PlaybackCaptureEngine? = null
    private var output: HapticsOutput? = null
    private var analyzer: A2HAnalyzer? = null
    private var lastFrame: Pair<Double, Double>? = null
    private var tone: com.meig.hapticx.audio.TonePlayer? = null

    // auto_test 统计(全变量在闭包里累计)
    private var statBlocks = 0
    private var statNonZero = 0
    private var statPeak = 0.0
    private var statMaxMotor = 0.0

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val resultData = intent?.getBundleExtra(EXTRA_RESULT_DATA)?.let { b ->
            b.getParcelable<Intent>(EXTRA_RESULT_DATA)?.let { d -> b.getInt("resultCode", -1) to d }
        }
        if (resultData == null) {
            Log.e(TAG, "缺 MediaProjection resultData")
            stopSelf()
            return START_NOT_STICKY
        }
        val autoTest = intent.getBooleanExtra(EXTRA_AUTO_TEST, false)
        startForegroundWithType()

        val projection = getSystemService(MediaProjectionManager::class.java)
            .getMediaProjection(resultData.first, resultData.second)
        projection.registerCallback(object : MediaProjection.Callback() {
            override fun onStop() { stopSelf() }
        }, Handler(Looper.getMainLooper()))

        analyzer = A2HAnalyzer(mode = "balanced")
        output = LogOutput().apply { open() }

        capture = PlaybackCaptureEngine(
            projection,
            onBlock = { block ->
                val a = analyzer ?: return@PlaybackCaptureEngine
                val f = a.processBlock(block)
                lastFrame = f.left to f.right
                output?.emit(f.left, f.right)
                if (autoTest) {
                    statBlocks++
                    var pk = 0.0
                    for (v in block) { val av = kotlin.math.abs(v); if (av > pk) pk = av }
                    if (pk > statPeak) statPeak = pk
                    if (pk > 0.001) statNonZero++
                    val m = maxOf(kotlin.math.abs(f.left), kotlin.math.abs(f.right))
                    if (m > statMaxMotor) statMaxMotor = m
                }
            },
            onError = { msg ->
                Log.e(TAG, "捕获错误: $msg")
                stopSelf()
            })
        capture?.start()
        if (autoTest) Log.i(TAG, "AUTO-TEST: 采集已启动, 2s 后自播测试音")

        // 自播自采测试:采集稳定后 2 秒,播 10 秒测试音(自身 USAGE_MEDIA 音频必可被采集)
        tone = TonePlayer(durationSec = 10)
        Handler(Looper.getMainLooper()).postDelayed({
            if (capture != null) tone?.start()
        }, 2000)

        // auto_test 收尾:14.5s(2s 延迟+10s 音+2.5s 余量)后打印总结并自停
        if (autoTest) {
            Handler(Looper.getMainLooper()).postDelayed({
                Log.i(TAG, "AUTOTEST SUMMARY: blocks=$statBlocks nonZero=$statNonZero peak=%.4f maxMotor=%.3f"
                    .format(statPeak, statMaxMotor))
                Log.i(TAG, "AUTOTEST RESULT: " + if (statNonZero >= 50 && statMaxMotor > 0.01)
                    "PASS - 捕获链路通,音频驱动马达" else "FAIL - 采集静音或马达无输出(nonZero=$statNonZero)")
                stopSelf()
            }, 14500)
        }
        return START_STICKY
    }

    private fun startForegroundWithType() {
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannelGroup(NotificationChannelGroup("hapticx", "HapticX"))
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL_ID, "触觉反馈引擎", NotificationManager.IMPORTANCE_LOW))
        val notification: Notification =
            Notification.Builder(this, CHANNEL_ID)
                .setContentTitle("HapticX 运行中")
                .setContentText("音频→触觉转换进行中")
                .setSmallIcon(android.R.drawable.ic_popup_reminder)
                .build()
        if (Build.VERSION.SDK_INT >= 29) {
            startForeground(1, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION)
        } else {
            startForeground(1, notification)
        }
    }

    override fun onDestroy() {
        tone?.stop()
        capture?.stop()
        output?.close()
        Log.i(TAG, "服务已停止")
        super.onDestroy()
    }
}

private typealias NotificationManager = android.app.NotificationManager
