package com.meig.hapticx

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.media.projection.MediaProjectionManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.SeekBar
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.meig.hapticx.dsp.A2HAnalyzer
import com.meig.hapticx.haptics.LogOutput
import com.meig.hapticx.service.HapticXService

class MainActivity : AppCompatActivity() {

    companion object {
        private const val REQ_PROJECTION = 1
        private const val REQ_NOTIF = 2
        private const val PREF = "hapticx"
    }

    private lateinit var status: TextView
    private lateinit var motors: TextView
    private lateinit var beat: TextView
    private lateinit var spectrum: SpectrumView
    private lateinit var startBtn: Button
    private lateinit var barL: ProgressBar
    private lateinit var barR: ProgressBar
    private lateinit var lab0: TextView
    private lateinit var lab1: TextView
    private lateinit var lab2: TextView
    private lateinit var gain0: SeekBar
    private lateinit var gain1: SeekBar
    private lateinit var gain2: SeekBar
    private val modeBtns = mutableMapOf<String, Button>()
    private var mode = "balanced"
    private var applyingSliders = false
    private val ui = Handler(Looper.getMainLooper())

    private val tick = object : Runnable {
        override fun run() {
            spectrum.invalidate()
            val running = HapticXService.isRunning()
            val fr = HapticXService.latestFrame()
            if (!running) {
                motors.text = "左马达 --  ｜  右马达 --（未捕获）"
                barL.progress = 0
                barR.progress = 0
            } else if (fr != null) {
                val (l, r) = fr
                val lp = kotlin.math.round(l * 100.0).toInt().coerceIn(0, 100)
                val rp = kotlin.math.round(r * 100.0).toInt().coerceIn(0, 100)
                motors.text = "左马达 %d%%  ｜  右马达 %d%%".format(lp, rp)
                barL.progress = lp
                barR.progress = rp
                val peak = HapticXService.lastPcmPeak()
                status.text = "引擎运行中 采到 %.0f%%  源=%s ｜ %s".format(
                    peak * 100.0, HapticXService.source() ?: "?", modeName(mode))
            }
            beat.setTextColor(if (HapticXService.lastTransient()) Color.rgb(0x44, 0xd6, 0x2c) else Color.rgb(0x3d, 0x4f, 0x6b))
            startBtn.text = if (running) getString(R.string.stop) else getString(R.string.start)
            window.decorView.postDelayed(this, 33)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        status = findViewById(R.id.status)
        motors = findViewById(R.id.motors)
        beat = findViewById(R.id.beat)
        spectrum = findViewById(R.id.spectrum)
        startBtn = findViewById(R.id.start)
        barL = findViewById(R.id.barL)
        barR = findViewById(R.id.barR)
        lab0 = findViewById(R.id.lab0)
        lab1 = findViewById(R.id.lab1)
        lab2 = findViewById(R.id.lab2)
        gain0 = findViewById(R.id.gain0)
        gain1 = findViewById(R.id.gain1)
        gain2 = findViewById(R.id.gain2)
        mode = getSharedPreferences(PREF, MODE_PRIVATE).getString("mode", "balanced") ?: "balanced"

        startBtn.setOnClickListener {
            if (HapticXService.isRunning()) {
                stopService(Intent(this, HapticXService::class.java))
                LogOutput().forceZero()
                status.text = "已停止"
            } else startCapture()
        }
        findViewById<Button>(R.id.tone).setOnClickListener {
            if (!Settings.canDrawOverlays(this)) {
                startActivity(Intent(
                    Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:$packageName")))
                status.text = "请允许「显示在其他应用上层」，再点一次"
            } else if (HapticXService.isRunning()) {
                HapticXService.showHud()
                status.text = "悬浮条已打开，切到游戏就能看见马达"
            } else status.text = "请先开始捕获"
        }

        val modesBox = findViewById<LinearLayout>(R.id.modes)
        for (m in listOf("controlled", "balanced", "dynamic", "custom")) {
            val b = Button(this)
            b.text = modeName(m)
            b.layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
            b.setOnClickListener { selectMode(m) }
            modesBox.addView(b)
            modeBtns[m] = b
        }
        bindGain(gain0, 0, "超低音", lab0)
        bindGain(gain1, 1, "低音", lab1)
        bindGain(gain2, 2, "中低音", lab2)
        findViewById<Button>(R.id.resetGains).setOnClickListener {
            getSharedPreferences(PREF, MODE_PRIVATE).edit().remove("gains_$mode").apply()
            refreshModeUi()
            pushConfig()
        }
        refreshModeUi()

        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
            != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.POST_NOTIFICATIONS), REQ_NOTIF)
        }
        window.decorView.post(tick)
    }

    private fun selectMode(m: String) {
        mode = m
        getSharedPreferences(PREF, MODE_PRIVATE).edit().putString("mode", m).apply()
        refreshModeUi()
        pushConfig()
        status.text = "模式: ${modeName(m)}"
    }

    private fun currentGains(): DoubleArray {
        val prefs = getSharedPreferences(PREF, MODE_PRIVATE)
        val def = A2HAnalyzer.MODE_BAND_GAINS[mode] ?: A2HAnalyzer.BAND_DEFAULT
        val raw = prefs.getString("gains_$mode", null)
        if (raw != null) {
            val p = raw.split(',').mapNotNull { it.toDoubleOrNull() }
            if (p.size == 3) return doubleArrayOf(p[0], p[1], p[2])
        }
        return def.copyOf()
    }

    private fun refreshModeUi() {
        applyingSliders = true
        val g = currentGains()
        gain0.progress = (g[0] * 100).toInt().coerceIn(0, 200)
        gain1.progress = (g[1] * 100).toInt().coerceIn(0, 200)
        gain2.progress = (g[2] * 100).toInt().coerceIn(0, 200)
        lab0.text = "超低音 ${gain0.progress}%"
        lab1.text = "低音 ${gain1.progress}%"
        lab2.text = "中低音 ${gain2.progress}%"
        applyingSliders = false
        for ((k, b) in modeBtns) {
            if (k == mode) {
                b.setBackgroundColor(Color.rgb(0x1a, 0x4a, 0x22))
                b.setTextColor(Color.rgb(0x44, 0xd6, 0x2c))
            } else {
                b.setBackgroundColor(Color.rgb(0x1c, 0x24, 0x30))
                b.setTextColor(Color.WHITE)
            }
        }
    }

    private fun bindGain(bar: SeekBar, idx: Int, name: String, lab: TextView) {
        bar.setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(seekBar: SeekBar?, progress: Int, fromUser: Boolean) {
                lab.text = "$name ${progress}%"
                if (!fromUser || applyingSliders) return
                val g = currentGains()
                g[idx] = progress / 100.0
                getSharedPreferences(PREF, MODE_PRIVATE).edit()
                    .putString("gains_$mode", g.joinToString(",")).apply()
                pushConfig()
            }
            override fun onStartTrackingTouch(seekBar: SeekBar?) {}
            override fun onStopTrackingTouch(seekBar: SeekBar?) {}
        })
    }

    private fun pushConfig() {
        HapticXService.applyConfig(mode, currentGains())
    }

    private fun startCapture() {
        if (HapticXService.isRunning()) return
        if (Build.VERSION.SDK_INT >= 23 && !Settings.canDrawOverlays(this)) {
            startActivity(Intent(
                Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse("package:$packageName")))
            status.text = "先允许悬浮窗，再点开始捕获"
            return
        }
        status.text = "申请音频捕获…"
        ui.post {
            try {
                startActivityForResult(
                    getSystemService(MediaProjectionManager::class.java).createScreenCaptureIntent(),
                    REQ_PROJECTION)
            } catch (e: Exception) {
                status.text = "捕获申请失败: ${e.message}"
            }
        }
    }

    @Deprecated("Deprecated in Java")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != REQ_PROJECTION) return
        if (resultCode == Activity.RESULT_OK && data != null) {
            val i = Intent(this, HapticXService::class.java).apply {
                val bundle = Bundle().apply {
                    putInt("resultCode", resultCode)
                    putParcelable(HapticXService.EXTRA_RESULT_DATA, data)
                }
                putExtra(HapticXService.EXTRA_RESULT_DATA, bundle)
                putExtra(HapticXService.EXTRA_MODE, mode)
                putExtra(HapticXService.EXTRA_GAINS, currentGains())
            }
            if (Build.VERSION.SDK_INT >= 26) startForegroundService(i) else startService(i)
            ui.postDelayed({
                status.text = "引擎运行中 源=${HapticXService.source()} ｜ ${modeName(mode)}"
            }, 800)
        } else status.text = "捕获授权被拒绝"
    }

    override fun onDestroy() {
        window.decorView.removeCallbacks(tick)
        super.onDestroy()
    }

    private fun modeName(m: String) = when (m) {
        "controlled" -> "受控"
        "balanced" -> "均衡"
        "dynamic" -> "动态"
        "custom" -> "自订"
        else -> m
    }
}
