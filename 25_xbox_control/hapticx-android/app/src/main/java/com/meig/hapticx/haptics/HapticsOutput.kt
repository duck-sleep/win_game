package com.meig.hapticx.haptics

import android.util.Log

/**
 * HapticsOutput — 触觉输出抽象(双通道:外接手柄 / 掌机自身马达,阶段2先做前者)。
 *
 * 手柄线(阶段0,当前挂起):EvdevOutput 直接 /dev/input/eventX + EVIOCSFF,
 * 等效 Windows XInputSetState。手柄到位后启用。
 * 当前默认 LogOutput:把左右马达强度打到 logcat + UI,用于无手柄验证全链路。
 */
interface HapticsOutput {
    fun open() {}
    fun close() {}
    /** @param left/right 0..1 */
    fun emit(left: Double, right: Double)
    val name: String
}

/** 无手柄阶段的输出:logcat 记录(30ms 节流),配合对拍脚本使用。 */
class LogOutput : HapticsOutput {
    companion object { const val TAG = "HapticXOut" }
    private var last = 0L
    override val name = "log"
    override fun emit(left: Double, right: Double) {
        val now = System.currentTimeMillis()
        if (now - last < 30) return   // ~30Hz 采样记录,足够对拍
        last = now
        Log.i(TAG, "L=${"%.3f".format(left)} R=${"%.3f".format(right)}")
    }
}
