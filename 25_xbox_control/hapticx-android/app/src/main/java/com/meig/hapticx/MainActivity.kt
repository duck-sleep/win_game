package com.meig.hapticx

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioTrack
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Bundle
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.meig.hapticx.dsp.A2HAnalyzer
import com.meig.hapticx.service.HapticXService

/**
 * MainActivity — 雷云风格调试界面 v0.1。
 * 功能:授权屏幕捕获 → 启动前台服务;四模式切换;实时频谱 + 马达强度读数。
 * 后续里程碑:频段增益编辑器(对齐 Windows 版 profiles 页)。
 */
class MainActivity : AppCompatActivity() {

    companion object {
        private const val REQ_PROJECTION = 1
        private const val REQ_NOTIF = 2
    }

    private lateinit var status: TextView
    private lateinit var motors: TextView
    private lateinit var spectrum: SpectrumView
    private lateinit var startBtn: Button
    private var mode = "balanced"
    private var toneTrack: AudioTrack? = null
    private var autoTest = false

    private val tick = object : Runnable {
        override fun run() {
            spectrum.invalidate()
            HapticXService.latestFrame()?.let { (l, r) ->
                motors.text = "左马达 %d%%  ｜  右马达 %d%%".format((l * 100).toInt(), (r * 100).toInt())
            }
            window.decorView.postDelayed(this, 33)   // ~30fps
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        status = findViewById(R.id.status)
        motors = findViewById(R.id.motors)
        spectrum = findViewById(R.id.spectrum)
        startBtn = findViewById(R.id.start)

        startBtn.setOnClickListener {
            if (HapticXService.isRunning()) {
                stopService(Intent(this, HapticXService::class.java))
                status.text = "已停止"
                startBtn.text = getString(R.string.start)
            } else {
                requestProjection()
            }
        }

        // 自播自采测试:本 app 自己播 USAGE_MEDIA 测试音(targetSdk 34 保证可被采集)
        findViewById<Button>(R.id.tone).setOnClickListener { playTone() }

        // 四模式按钮组
        val modesBox = findViewById<LinearLayout>(R.id.modes)
        for (m in listOf("controlled", "balanced", "dynamic", "custom")) {
            val b = Button(this)
            b.text = modeName(m)
            b.setOnClickListener {
                mode = m
                HapticXService.analyzer()?.reconfigure(newMode = m)
                status.text = "模式: ${modeName(m)}"
            }
            modesBox.addView(b)
        }

        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
            != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.POST_NOTIFICATIONS), REQ_NOTIF)
        }
        window.decorView.post(tick)

        // 一键自测:am start --ez auto_test true → 自动申请捕获(appops 已预授权则无弹窗)
        // → 服务自动采集+自播测试音 → logcat 打印 AUTOTEST SUMMARY/RESULT
        if (intent?.getBooleanExtra("auto_test", false) == true) {
            autoTest = true
            status.text = "AUTO-TEST —— 1s 后自动申请捕获"
            window.decorView.postDelayed({
                if (!HapticXService.isRunning()) {
                    requestProjection()
                }
            }, 1000)
        }
    }

    private fun requestProjection() {
        val mpm = getSystemService(MediaProjectionManager::class.java)
        startActivityForResult(mpm.createScreenCaptureIntent(), REQ_PROJECTION)
    }

    @Deprecated("Deprecated in Java")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == REQ_PROJECTION) {
            if (resultCode == Activity.RESULT_OK && data != null) {
                val i = Intent(this, HapticXService::class.java).apply {
                    val bundle = Bundle().apply {
                        putInt("resultCode", resultCode)
                        putParcelable(HapticXService.EXTRA_RESULT_DATA, data)
                    }
                    putExtra(HapticXService.EXTRA_RESULT_DATA, bundle)
                    if (autoTest) putExtra(HapticXService.EXTRA_AUTO_TEST, true)
                }
                if (Build.VERSION.SDK_INT >= 26) startForegroundService(i) else startService(i)
                status.text = "模式: ${modeName(mode)} ｜ 引擎运行中"
                startBtn.text = getString(R.string.stop)
            } else {
                status.text = "捕获授权被拒绝"
            }
        }
    }

    override fun onDestroy() {
        window.decorView.removeCallbacks(tick)
        stopTone()
        super.onDestroy()
    }

    /** 播放 5 秒 440Hz 立体声测试音(USAGE_MEDIA + CONTENT_TYPE_MUSIC,可被播放采集) */
    private fun playTone() {
        stopTone()
        val sr = 48000
        val durSec = 5
        val n = sr * durSec
        val buf = ShortArray(n * 2)   // 立体声交错的
        for (i in 0 until n) {
            val s = (12000 * kotlin.math.sin(2.0 * Math.PI * 440.0 * i / sr)).toInt().toShort()
            buf[2 * i] = s
            buf[2 * i + 1] = s
        }
        val track = AudioTrack(
            AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                .build(),
            AudioFormat.Builder()
                .setSampleRate(sr)
                .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                .setChannelMask(AudioFormat.CHANNEL_OUT_STEREO)
                .build(),
            buf.size * 2, AudioTrack.MODE_STATIC, AudioManager.AUDIO_SESSION_ID_GENERATE
        )
        track.write(buf, 0, buf.size)
        track.play()
        toneTrack = track
        status.text = "自播测试音 5s —— 看马达读数是否跳动"
        window.decorView.postDelayed({
            status.text = if (HapticXService.isRunning()) "模式: ${modeName(mode)} ｜ 引擎运行中" else status.text
        }, 5200)
    }

    private fun stopTone() {
        toneTrack?.let { try { it.stop(); it.release() } catch (_: Exception) {} }
        toneTrack = null
    }

    private fun modeName(m: String) = when (m) {
        "controlled" -> "受控"
        "balanced" -> "均衡"
        "dynamic" -> "动态"
        "custom" -> "自订"
        else -> m
    }
}
