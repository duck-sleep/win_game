package com.meig.hapticx.dsp

/**
 * FFT.kt — 实信号 FFT(幅度谱),支持任意长度。
 *
 * Windows 版 analyzer.py 用 np.fft.rfft(FFT_WINDOW=2400),
 * 2400 = 2^5·3·5^2 非 2 次幂,这里用 Bluestein 算法(chirp-z 变换)
 * 借助标准 2 次幂 FFT 实现,保证与 numpy 结果逐 bin 对齐(对拍前提)。
 */
object Fft {

    /** 返回实信号 x(长度 n)的 rfft 幅度谱,长度 n/2+1。 */
    fun realMagnitude(x: DoubleArray, n: Int): DoubleArray {
        val half = n / 2
        val re = DoubleArray(n)
        val im = DoubleArray(n)
        System.arraycopy(x, 0, re, 0, n)
        if (n and (n - 1) == 0) {
            fftRadix2(re, im, false)
        } else {
            bluestein(re, im)
        }
        val mag = DoubleArray(half + 1)
        for (i in 0..half) mag[i] = kotlin.math.sqrt(re[i] * re[i] + im[i] * im[i])
        return mag
    }

    /** 标准 2 次幂原地 FFT(迭代 Cooley-Tukey)。 */
    private fun fftRadix2(re: DoubleArray, im: DoubleArray, inverse: Boolean) {
        val n = re.size
        // 位反转置换
        var j = 0
        for (i in 1 until n) {
            var bit = n shr 1
            while (j and bit != 0) { j = j xor bit; bit = bit shr 1 }
            j = j or bit
            if (i < j) {
                var t = re[i]; re[i] = re[j]; re[j] = t
                t = im[i]; im[i] = im[j]; im[j] = t
            }
        }
        var len = 2
        while (len <= n) {
            val ang = 2.0 * Math.PI / len * (if (inverse) 1.0 else -1.0)
            val wRe = kotlin.math.cos(ang)
            val wIm = kotlin.math.sin(ang)
            var i = 0
            while (i < n) {
                var curRe = 1.0; var curIm = 0.0
                for (k in 0 until len / 2) {
                    val uRe = re[i + k]; val uIm = im[i + k]
                    val vRe = re[i + k + len / 2] * curRe - im[i + k + len / 2] * curIm
                    val vIm = re[i + k + len / 2] * curIm + im[i + k + len / 2] * curRe
                    re[i + k] = uRe + vRe; im[i + k] = uIm + vIm
                    re[i + k + len / 2] = uRe - vRe; im[i + k + len / 2] = uIm - vIm
                    val nRe = curRe * wRe - curIm * wIm
                    curIm = curRe * wIm + curIm * wRe; curRe = nRe
                }
                i += len
            }
            len = len shl 1
        }
        if (inverse) {
            for (i in 0 until n) { re[i] /= n; im[i] /= n }
        }
    }

    /** Bluestein:任意 N 的 DFT,借助 M≥2N-1 的 2 次幂卷积。 */
    private fun bluestein(re: DoubleArray, im: DoubleArray) {
        val n = re.size
        var m = 1
        while (m < 2 * n - 1) m = m shl 1

        // chirp: w[k] = exp(-i·pi·k²/N)
        val aRe = DoubleArray(m); val aIm = DoubleArray(m)
        val bRe = DoubleArray(m); val bIm = DoubleArray(m)
        for (k in 0 until n) {
            val t = Math.PI * ((k.toLong() * k) % (2L * n)).toDouble() / n
            val c = kotlin.math.cos(t); val s = kotlin.math.sin(-t)
            aRe[k] = re[k] * c - im[k] * s
            aIm[k] = re[k] * s + im[k] * c
            bRe[k] = c; bIm[k] = -s
            if (k > 0) {
                bRe[m - k] = c; bIm[m - k] = -s   // b[-k]
            }
        }
        fftRadix2(aRe, aIm, false)
        fftRadix2(bRe, bIm, false)
        for (i in 0 until m) {
            val r = aRe[i] * bRe[i] - aIm[i] * bIm[i]
            aIm[i] = aRe[i] * bIm[i] + aIm[i] * bRe[i]
            aRe[i] = r
        }
        fftRadix2(aRe, aIm, true)
        System.arraycopy(aRe, 0, re, 0, n)
        System.arraycopy(aIm, 0, im, 0, n)
    }
}
