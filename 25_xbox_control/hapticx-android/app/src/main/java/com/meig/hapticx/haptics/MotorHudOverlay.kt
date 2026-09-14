package com.meig.hapticx.haptics

import android.content.Context
import android.graphics.PixelFormat
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.provider.Settings
import android.util.Log
import android.view.Gravity
import android.view.LayoutInflater
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.ProgressBar
import android.widget.TextView
import com.meig.hapticx.R

/**
 * 游戏全屏时仍能看见的马达条。TYPE_APPLICATION_OVERLAY，不抢焦点。
 */
class MotorHudOverlay(private val ctx: Context) {
    companion object { private const val TAG = "HapticXHud" }

    private val wm = ctx.getSystemService(WindowManager::class.java)
    private val ui = Handler(Looper.getMainLooper())
    private var root: View? = null
    private var hudL: TextView? = null
    private var hudR: TextView? = null
    private var hudPeak: TextView? = null
    private var barL: ProgressBar? = null
    private var barR: ProgressBar? = null
    private var lp: WindowManager.LayoutParams? = null
    private var lastPost = 0L
    @Volatile private var pendingL = 0.0
    @Volatile private var pendingR = 0.0
    @Volatile private var pendingPeak = 0.0

    fun show() {
        ui.post {
            if (root != null) return@post
            if (Build.VERSION.SDK_INT >= 23 && !Settings.canDrawOverlays(ctx)) {
                Log.w(TAG, "无悬浮窗权限")
                return@post
            }
            val v = LayoutInflater.from(ctx).inflate(R.layout.overlay_hud, null)
            hudL = v.findViewById(R.id.hudL)
            hudR = v.findViewById(R.id.hudR)
            hudPeak = v.findViewById(R.id.hudPeak)
            barL = v.findViewById(R.id.hudBarL)
            barR = v.findViewById(R.id.hudBarR)
            v.findViewById<View>(R.id.hudClose).setOnClickListener { hide() }
            val title = v.findViewById<View>(R.id.hudTitle)
            val params = WindowManager.LayoutParams(
                WindowManager.LayoutParams.WRAP_CONTENT,
                WindowManager.LayoutParams.WRAP_CONTENT,
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                    WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL or
                    WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
                PixelFormat.TRANSLUCENT
            ).apply {
                gravity = Gravity.TOP or Gravity.START
                x = 24
                y = 160
            }
            enableDrag(title, v, params)
            try {
                wm.addView(v, params)
                root = v
                lp = params
                Log.i(TAG, "悬浮条已打开")
            } catch (e: Exception) {
                Log.e(TAG, "加悬浮条失败: ${e.message}")
            }
        }
    }

    fun hide() {
        ui.post {
            val v = root ?: return@post
            try { wm.removeView(v) } catch (_: Exception) {}
            root = null
            lp = null
        }
    }

    fun update(left: Double, right: Double, peak: Double) {
        pendingL = left
        pendingR = right
        pendingPeak = peak
        val now = SystemClock.uptimeMillis()
        if (now - lastPost < 50) return
        lastPost = now
        ui.post {
            val lpct = kotlin.math.round(pendingL * 100.0).toInt().coerceIn(0, 100)
            val rpct = kotlin.math.round(pendingR * 100.0).toInt().coerceIn(0, 100)
            hudL?.text = "左 %d%%".format(lpct)
            hudR?.text = "右 %d%%".format(rpct)
            barL?.progress = lpct
            barR?.progress = rpct
            hudPeak?.text = "采到 %.0f%%".format(pendingPeak * 100.0)
        }
    }

    private fun enableDrag(handle: View, window: View, params: WindowManager.LayoutParams) {
        var downX = 0f
        var downY = 0f
        var startX = 0
        var startY = 0
        handle.setOnTouchListener { _, e ->
            when (e.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    downX = e.rawX
                    downY = e.rawY
                    startX = params.x
                    startY = params.y
                    true
                }
                MotionEvent.ACTION_MOVE -> {
                    params.x = startX + (e.rawX - downX).toInt()
                    params.y = startY + (e.rawY - downY).toInt()
                    try { wm.updateViewLayout(window, params) } catch (_: Exception) {}
                    true
                }
                else -> false
            }
        }
    }
}
