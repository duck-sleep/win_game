package com.meig.hapticx.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationChannelGroup
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.util.Log
import com.meig.hapticx.MainActivity
import com.meig.hapticx.audio.PlaybackCaptureEngine
import com.meig.hapticx.dsp.A2HAnalyzer
import com.meig.hapticx.haptics.HapticsOutput
import com.meig.hapticx.haptics.LogOutput
import com.meig.hapticx.haptics.MotorHudOverlay

class HapticXService : Service() {

    companion object {
        const val TAG = "HapticX"
        const val EXTRA_RESULT_DATA = "resultData"
        const val EXTRA_AUTO_TEST = "auto_test"
        const val EXTRA_MODE = "mode"
        const val EXTRA_GAINS = "gains"
        const val ACTION_STOP = "com.meig.hapticx.STOP"
        const val CHANNEL_ID = "hapticx"
        private var instance: HapticXService? = null
        @Volatile var lastError: String? = null
            private set
        fun isRunning(): Boolean = instance?.captureLive == true
        fun analyzer(): A2HAnalyzer? = instance?.analyzer
        fun latestFrame(): Pair<Double, Double>? = instance?.lastFrame
        fun vizSnapshot(): DoubleArray? = instance?.analyzer?.viz
        fun source(): String? = instance?.source
        fun lastPcmPeak(): Double = instance?.lastPcmPeak ?: 0.0
        fun lastTransient(): Boolean = instance?.lastBeat == true
        fun applyConfig(mode: String?, gains: DoubleArray?) {
            instance?.analyzer?.reconfigure(newMode = mode, newBandGains = gains)
        }
        fun showHud() { instance?.hud?.show() }
    }

    private var playback: PlaybackCaptureEngine? = null
    private var output: HapticsOutput? = null
    private var analyzer: A2HAnalyzer? = null
    private var lastFrame: Pair<Double, Double>? = null
    private var source: String? = null
    @Volatile private var captureLive = false
    @Volatile private var lastBeat = false
    private var holdL = 0.0
    private var holdR = 0.0
    @Volatile private var lastPcmPeak = 0.0
    private var hud: MotorHudOverlay? = null
    private val main = Handler(Looper.getMainLooper())

    override fun onCreate() {
        super.onCreate()
        instance = this
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopSelf()
            return START_NOT_STICKY
        }
        if (captureLive) return START_NOT_STICKY
        lastError = null
        val resultData = intent?.getBundleExtra(EXTRA_RESULT_DATA)?.let { b ->
            b.getParcelable<Intent>(EXTRA_RESULT_DATA)?.let { d -> b.getInt("resultCode", -1) to d }
        }
        if (resultData == null) {
            lastError = "需要屏幕捕获授权"
            Log.e(TAG, lastError!!)
            stopSelf()
            return START_NOT_STICKY
        }
        startForegroundWithType()
        val startMode = intent?.getStringExtra(EXTRA_MODE) ?: "balanced"
        analyzer = A2HAnalyzer(mode = startMode)
        intent?.getDoubleArrayExtra(EXTRA_GAINS)?.let { analyzer?.reconfigure(newBandGains = it) }
        output = LogOutput().apply { open() }
        startPlaybackCapture(resultData.first, resultData.second)
        return START_NOT_STICKY
    }

    private fun onPcm(block: DoubleArray) {
        val a = analyzer ?: return
        // 每块都进分析器,让包络自己衰减;不再因单块 peak 低就砍成 0
        var peak = 0.0
        for (v in block) {
            val aAbs = kotlin.math.abs(v)
            if (aAbs > peak) peak = aAbs
        }
        lastPcmPeak = peak
        val f = a.processBlock(block)
        // 轻微保持,避免 20ms 闪没;不再用 0.88 把条粘在高位
        holdL = maxOf(f.left, holdL * 0.72)
        holdR = maxOf(f.right, holdR * 0.72)
        if (holdL < 0.02) holdL = 0.0
        if (holdR < 0.02) holdR = 0.0
        lastFrame = holdL to holdR
        lastBeat = f.transient
        output?.emit(holdL, holdR)
        hud?.update(holdL, holdR, lastPcmPeak)
    }

    private fun startPlaybackCapture(code: Int, data: Intent) {
        source = "AudioPlaybackCapture"
        val projection = getSystemService(MediaProjectionManager::class.java)
            .getMediaProjection(code, data)
        if (projection == null) {
            lastError = "MediaProjection 为空"
            Log.e(TAG, lastError!!)
            stopSelf()
            return
        }
        projection.registerCallback(object : MediaProjection.Callback() {
            override fun onStop() { stopSelf() }
        }, Handler(Looper.getMainLooper()))
        playback = PlaybackCaptureEngine(
            projection,
            onBlock = { onPcm(it) },
            onError = { msg ->
                Log.e(TAG, "PlaybackCapture 失败: $msg")
                lastError = msg
                captureLive = false
                stopSelf()
            }
        )
        playback?.start()
        captureLive = true
        main.post {
            hud = MotorHudOverlay(this).also { it.show() }
        }
        Log.i(TAG, "采集=AudioPlaybackCapture → DSP → HapticXOut")
    }

    private fun startForegroundWithType() {
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannelGroup(NotificationChannelGroup("hapticx", "HapticX"))
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL_ID, "触觉反馈引擎", NotificationManager.IMPORTANCE_LOW))
        val openPi = PendingIntent.getActivity(
            this, 1, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val stopPi = PendingIntent.getService(
            this, 2, Intent(this, HapticXService::class.java).setAction(ACTION_STOP),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val notification: Notification =
            Notification.Builder(this, CHANNEL_ID)
                .setContentTitle("HapticX 运行中")
                .setContentText("正在偷听系统音频 · 点此可停")
                .setSmallIcon(android.R.drawable.ic_popup_reminder)
                .setContentIntent(openPi)
                .addAction(android.R.drawable.ic_menu_close_clear_cancel, "停止震动", stopPi)
                .setOngoing(true)
                .build()
        if (Build.VERSION.SDK_INT >= 29)
            startForeground(1, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION)
        else startForeground(1, notification)
    }

    override fun onTaskRemoved(rootIntent: Intent?) {
        stopSelf()
        super.onTaskRemoved(rootIntent)
    }

    override fun onDestroy() {
        captureLive = false
        playback?.stop()
        hud?.hide()
        hud = null
        (output as? LogOutput)?.forceZero()
        output?.close()
        lastFrame = 0.0 to 0.0
        if (instance === this) instance = null
        Log.i(TAG, "服务已停止")
        super.onDestroy()
    }
}

private typealias NotificationManager = android.app.NotificationManager
