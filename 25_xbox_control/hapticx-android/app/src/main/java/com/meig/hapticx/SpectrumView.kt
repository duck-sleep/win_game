package com.meig.hapticx

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.util.AttributeSet
import android.view.View
import com.meig.hapticx.service.HapticXService

/**
 * SpectrumView — 实时频谱(16 对数频段,20Hz-8kHz)。
 * 触觉频段(30-130Hz)绿色高亮,其余灰蓝——对齐 Windows 版主界面观感。
 */
class SpectrumView(ctx: Context, attrs: AttributeSet?) : View(ctx, attrs) {

    private val barPaint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val inBandPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.rgb(0x44, 0xd6, 0x2c) }
    private val outBandPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.rgb(0x3d, 0x4f, 0x6b) }
    private val textPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.rgb(0x9a, 0xa3, 0xb0); textSize = 24f
    }

    override fun onDraw(c: Canvas) {
        val viz = HapticXService.vizSnapshot() ?: return
        val w = width.toFloat()
        val h = height.toFloat() - 34f
        val bw = w / viz.size
        for (i in viz.indices) {
            val bh = (viz[i] * h).toFloat().coerceAtLeast(4f)
            val left = i * bw + bw * 0.15f
            val right = (i + 1) * bw - bw * 0.15f
            barPaint.color = if (HapticXService.analyzer()?.vizInBand?.get(i) == true)
                inBandPaint.color else outBandPaint.color
            c.drawRect(left, h - bh, right, h, barPaint)
        }
        c.drawText("20Hz", 4f, height - 6f, textPaint)
        val t = textPaint.measureText("8kHz")
        c.drawText("8kHz", w - t - 4f, height - 6f, textPaint)
    }
}
