package com.meig.hapticx.dsp

/**
 * A2HAnalyzer.kt — analyzer.py 的 Kotlin 逐算法移植(对拍基准)。
 *
 * 参数全部来自雷云 A2H 配方,与 Windows 版 HapticX 同源:
 *   频段 30-130Hz / EQ(0:1, 50:1, 100:0.3, 150:0.3) / 振幅窗 40ms /
 *   频率窗 125ms / 门限 0.03 / 压缩器 gamma 3 / 瞬态 prominence 0.4、时长 22ms。
 * 详见 12_win_上机跑/09_动态触觉反馈技术.md 与 10_安卓雷云技术.md。
 */
class A2HAnalyzer(
    mode: String = "balanced",
    var gain: Double = 0.67,          // 雷云 SetHapticMixerGain gain=67 → 0.67
    bandGains: DoubleArray? = null,
    bandEdges: DoubleArray? = null,
) {
    companion object {
        const val SAMPLE_RATE = 48000
        const val FFT_WINDOW = 2400     // 50ms,雷云 period_ms_fft=50
        const val FFT_HOP = 960         // 20ms

        // 四模式预设(均衡=雷云真值);模式差异=门限/gamma/瞬态
        val MODES: Map<String, Map<String, Double>> = mapOf(
            "controlled" to mapOf("gate" to 0.04, "band_scale" to 1.0, "transient_vol" to 0.25, "gamma" to 3.5, "freq_win" to 0.15, "amp_win" to 0.04),
            "balanced" to mapOf("gate" to 0.03, "band_scale" to 1.0, "transient_vol" to 0.35, "gamma" to 3.0, "freq_win" to 0.125, "amp_win" to 0.04),
            "dynamic" to mapOf("gate" to 0.02, "band_scale" to 1.0, "transient_vol" to 0.60, "gamma" to 4.0, "freq_win" to 0.06, "amp_win" to 0.025),
            "custom" to mapOf("gate" to 0.03, "band_scale" to 1.0, "transient_vol" to 0.50, "gamma" to 3.0, "freq_win" to 0.125, "amp_win" to 0.04),
        )

        val EQ_KEYFRAMES = arrayOf(0.0 to 1.0, 50.0 to 1.0, 100.0 to 0.3, 150.0 to 0.3)

        const val BAND_MIN = 30.0
        const val BAND_MAX = 130.0
        val BAND_EDGES = doubleArrayOf(30.0, 70.0, 100.0, 200.0)
        val BAND_LABELS = arrayOf("超低音", "低音", "中低音")
        val BAND_DEFAULT = doubleArrayOf(1.0, 0.7, 0.3)
        val MODE_BAND_GAINS = mapOf(
            "controlled" to doubleArrayOf(0.7, 0.5, 0.2),
            "balanced" to doubleArrayOf(1.0, 0.7, 0.3),
            "dynamic" to doubleArrayOf(1.3, 0.6, 0.2),
            "custom" to doubleArrayOf(1.0, 0.7, 0.3),
        )

        const val REF_LEVEL = 0.3      // 压缩器固定参考值(不依赖 gate)
        const val PROMINENCE = 0.4
        const val TRANSIENT_DUR = 0.022
        const val REFRACTORY = 0.12

        /** 频率→rfft bin 序号(采样率 48k,窗 2400,分辨率 20Hz/bin)。 */
        fun freqOfBin(i: Int) = i * SAMPLE_RATE.toDouble() / FFT_WINDOW
    }

    var mode: String = mode
        private set
    var cfg: Map<String, Double> = MODES[mode] ?: MODES["balanced"]!!
        private set

    private val buffer = DoubleArray(FFT_WINDOW)
    private val window = DoubleArray(FFT_WINDOW).also {
        for (i in 0 until FFT_WINDOW)
            it[i] = 0.5 - 0.5 * kotlin.math.cos(2.0 * Math.PI * i / (FFT_WINDOW - 1))
    }
    private var prevSpectrum: DoubleArray? = null
    private val nBins = FFT_WINDOW / 2 + 1
    private val bandMask = BooleanArray(nBins)
    private var eqTable = DoubleArray(nBins)

    var bandGains: DoubleArray = bandGains?.copyOf() ?: BAND_DEFAULT.copyOf()
        private set
    var bandEdges: DoubleArray = bandEdges?.copyOf() ?: BAND_EDGES.copyOf()
        private set

    // 可视化:16 个对数频段(20Hz-8kHz)
    val vizEdges = DoubleArray(17).also {
        for (i in 0..16) it[i] = 20.0 * Math.pow(8000.0 / 20.0, i / 16.0)
    }
    val viz = DoubleArray(16)
    val vizInBand = BooleanArray(16).also {
        for (i in 0 until 16) it[i] = vizEdges[i] >= BAND_MIN && vizEdges[i] <= BAND_MAX
    }

    // 状态
    private var env = 0.0
    private var freqEnv = 0.0
    private var transientAmp = 0.0
    private var transientDecay = 0.0
    private var transientFresh = false
    private val blockPeriod = FFT_HOP.toDouble() / SAMPLE_RATE
    var beatCount = 0
        private set
    private var elapsed = 0.0
    private var lastBeatT = -1.0

    init {
        for (i in 0 until nBins) bandMask[i] = freqOfBin(i) in BAND_MIN..BAND_MAX
        rebuildEq()
    }

    private fun linearInterp(x: Double, kf: Array<Pair<Double, Double>>): Double {
        if (x <= kf.first().first) return kf.first().second
        for (i in 1 until kf.size) {
            if (x <= kf[i].first) {
                val (x0, y0) = kf[i - 1]; val (x1, y1) = kf[i]
                return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
            }
        }
        return kf.last().second
    }

    private fun rebuildEq() {
        val base = DoubleArray(nBins)
        for (i in 0 until nBins) base[i] = linearInterp(freqOfBin(i), EQ_KEYFRAMES)
        for (i in 0 until bandEdges.size - 1) {
            val lo = bandEdges[i]; val hi = bandEdges[i + 1]
            for (b in 0 until nBins) {
                val f = freqOfBin(b)
                if (f >= lo && f < hi) base[b] *= bandGains[i]
            }
        }
        eqTable = base
    }

    /** UI 在线切模式。 */
    fun reconfigure(newMode: String? = null, newGain: Double? = null,
                    newBandGains: DoubleArray? = null, newBandEdges: DoubleArray? = null) {
        if (newMode != null && MODES.containsKey(newMode)) { cfg = MODES[newMode]!!; mode = newMode }
        if (newGain != null) gain = newGain.coerceIn(0.05, 1.5)
        if (newBandGains != null) {
            bandGains = DoubleArray(newBandGains.size) { newBandGains[it].coerceIn(0.0, 2.0) }
            rebuildEq()
        }
        if (newBandEdges != null) {
            bandEdges = DoubleArray(newBandEdges.size) {
                newBandEdges[it].coerceIn(30.0, 200.0)
            }
            rebuildEq()
        }
    }

    private fun eqWeightedBand(): Pair<Double, Double> {
        // 对齐 Python 版:rfft(buffer * window) —— 窗函数必须乘上
        val windowed = DoubleArray(FFT_WINDOW) { buffer[it] * window[it] }
        val spectrum = Fft.realMagnitude(windowed, FFT_WINDOW)
        for (i in 0 until spectrum.size) spectrum[i] /= FFT_WINDOW
        // viz:16 对数频段 RMS
        for (v in 0 until 16) {
            var sum = 0.0; var cnt = 0
            val lo = vizEdges[v]; val hi = vizEdges[v + 1]
            for (b in 0 until nBins) {
                val f = freqOfBin(b)
                if (f >= lo && f < hi) { sum += spectrum[b] * spectrum[b]; cnt++ }
            }
            viz[v] = if (cnt == 0) 0.0
                     else kotlin.math.sqrt(sum / cnt) / 0.25
            if (viz[v] > 1.0) viz[v] = 1.0
        }
        // 上升通量:只统计 30-130Hz 鼓点频段
        var flux = 0.0
        prevSpectrum?.let { prev ->
            for (b in 0 until nBins) {
                if (bandMask[b]) {
                    val d = spectrum[b] - prev[b]
                    if (d > 0) flux += d
                }
            }
        }
        prevSpectrum = spectrum
        var sum = 0.0; var cnt = 0
        for (b in 0 until nBins) {
            if (bandMask[b]) { sum += (spectrum[b] * eqTable[b]).let { it * it }; cnt++ }
        }
        return kotlin.math.sqrt(sum / cnt) to flux
    }

    private fun envelope(amp: Double): Double {
        val tau = cfg["amp_win"]!!
        val alpha = 1.0 - kotlin.math.exp(-blockPeriod / kotlin.math.max(tau, 1e-6))
        val release = alpha * 0.4
        env += (amp - env) * (if (amp > env) alpha else release)
        return env
    }

    private fun frequencySmooth(amp: Double): Double {
        val tau = cfg["freq_win"]!!
        val alpha = 1.0 - kotlin.math.exp(-blockPeriod / kotlin.math.max(tau, 1e-6))
        freqEnv += (amp - freqEnv) * alpha
        return freqEnv
    }

    private fun detectTransient(flux: Double): Boolean {
        elapsed += blockPeriod
        if (cfg["transient_vol"]!! <= 0) return false
        if (freqEnv <= 1e-6) return false
        if (elapsed - lastBeatT < REFRACTORY) return false
        if (flux / (freqEnv + 1e-9) > PROMINENCE * 8) {
            transientAmp = cfg["transient_vol"]!!
            transientDecay = kotlin.math.exp(-blockPeriod / kotlin.math.max(TRANSIENT_DUR, 1e-6))
            transientFresh = true
            beatCount++
            lastBeatT = elapsed
            return true
        }
        return false
    }

    /** 输入 20ms 块(960 samples),返回 (left, right, smoothed, transient)。 */
    fun processBlock(samples: DoubleArray): MotorFrame {
        System.arraycopy(buffer, samples.size, buffer, 0, FFT_WINDOW - samples.size)
        System.arraycopy(samples, 0, buffer, FFT_WINDOW - samples.size, samples.size)
        val (amp, flux) = eqWeightedBand()
        val smoothed = frequencySmooth(envelope(amp))

        val gate = cfg["gate"]!!
        val gated = if (smoothed > gate) smoothed else 0.0
        val gamma = cfg["gamma"]!!
        val compressed = if (gated > 0)
            Math.pow(gated / REF_LEVEL, 1.0 / gamma).coerceIn(0.0, 1.0)
        else 0.0

        detectTransient(flux)
        if (transientFresh) {
            transientFresh = false
        } else if (transientAmp > 0) {
            transientAmp *= transientDecay
            if (transientAmp < 0.02) transientAmp = 0.0
        }

        val bandLevel = compressed * cfg["band_scale"]!!
        val left = (bandLevel + transientAmp * 0.7).coerceIn(0.0, 1.0) * gain
        val right = (transientAmp + bandLevel * 0.4).coerceIn(0.0, 1.0) * gain
        return MotorFrame(left, right, smoothed, transientAmp > 0)
    }
}

/** 一轮分析输出:左右马达强度 0-1 + 平滑电平 + 是否瞬态节拍。 */
data class MotorFrame(val left: Double, val right: Double,
                      val level: Double, val transient: Boolean)
