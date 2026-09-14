package com.meig.hapticx.haptics

import android.util.Log

interface HapticsOutput {
    fun open() {}
    fun close() {}
    fun emit(left: Double, right: Double)
    val name: String
}

class LogOutput : HapticsOutput {
    companion object { const val TAG = "HapticXOut" }
    private var last = 0L
    private var lastSilent = true
    override val name = "log"
    override fun emit(left: Double, right: Double) {
        val silent = left <= 0.0 && right <= 0.0
        val now = System.currentTimeMillis()
        if (silent) {
            if (lastSilent && now - last < 200) return
            lastSilent = true
        } else {
            if (now - last < 30) return
            lastSilent = false
        }
        last = now
        Log.i(TAG, "L=${"%.3f".format(left)} R=${"%.3f".format(right)}")
    }

    fun forceZero() {
        lastSilent = false
        last = 0L
        Log.i(TAG, "L=0.000 R=0.000")
        lastSilent = true
        last = System.currentTimeMillis()
    }

    override fun close() {
        forceZero()
        forceZero()
    }
}
