package com.meig.hapticx.dsp

/**
 * CompareMain — DSP 对拍 runner(临时工具,不打包进 APK 也可保留,无副作用)。
 *
 * 读 tools/crosscheck_fixture.csv(Windows analyzer.py 生成的基准),
 * 用本端 A2HAnalyzer 逐块重放,打印最大数值偏差。
 *
 * 运行(项目根):
 *   gradle :app:compileDebugKotlin --offline
 *   java -cp "app/build/tmp/kotlin-classes/debug;<kotlin-stdlib.jar>" \
 *        com.meig.hapticx.dsp.CompareMain tools/crosscheck_fixture.csv
 */
fun main(args: Array<String>) {
    val path = args.getOrElse(0) { "tools/crosscheck_fixture.csv" }
    val lines = java.io.File(path).readLines()
    val header = lines.first { it.startsWith("#") }
    val mode = Regex("mode=(\\w+)").find(header)!!.groupValues[1]
    val gain = Regex("gain=([0-9.]+)").find(header)!!.groupValues[1].toDouble()
    val bg = Regex("band_gains=\\[([^]]+)]").find(header)!!.groupValues[1]
        .split(",").map { it.trim().toDouble() }.toDoubleArray()
    val be = Regex("band_edges=\\[([^]]+)]").find(header)!!.groupValues[1]
        .split(",").map { it.trim().toDouble() }.toDoubleArray()
    val expectBeats = Regex("beat_count=(\\d+)").find(header)!!.groupValues[1].toInt()

    val an = A2HAnalyzer(mode = mode, gain = gain, bandGains = bg, bandEdges = be)

    var maxDL = 0.0; var maxDR = 0.0; var maxDS = 0.0
    var transMismatch = 0; var blocks = 0
    var i = 1
    val transActual = StringBuilder()
    val transExpect = StringBuilder()
    while (i < lines.size) {
        val l = lines[i]
        when {
            l.startsWith("B,") -> {
                val p = l.split(",")
                val el = p[1].toDouble(); val er = p[2].toDouble()
                val es = p[3].toDouble(); val et = p[4] == "1"
                val samples = lines[i + 1].split(",")
                    .map { it.trim().toDouble() }.toDoubleArray()
                val f = an.processBlock(samples)
                maxDL = maxOf(maxDL, kotlin.math.abs(f.left - el))
                maxDR = maxOf(maxDR, kotlin.math.abs(f.right - er))
                maxDS = maxOf(maxDS, kotlin.math.abs(f.level - es))
                if (f.transient != et) transMismatch++
                transActual.append(if (f.transient) 1 else 0)
                transExpect.append(if (et) 1 else 0)
                blocks++
                i += 2
            }
            l.startsWith("V,") -> {
                val expect = l.split(",").drop(1).map { it.trim().toDouble() }
                var maxViz = 0.0
                for (k in expect.indices)
                    maxViz = maxOf(maxViz, kotlin.math.abs(an.viz[k] - expect[k]))
                println("viz max diff      = $maxViz")
                println("viz expected[0..3] = ${expect.take(4)}")
                println("viz actual[0..3]   = ${an.viz.take(4).toList()}")
                i++
            }
            else -> i++
        }
    }
    println("blocks compared   = $blocks")
    println("max |dLeft|       = $maxDL")
    println("max |dRight|      = $maxDR")
    println("max |dLevel|      = $maxDS")
    println("transient mismatch= $transMismatch ($transExpect vs $transActual)")
    println("beat_count        = ${an.beatCount} (expect $expectBeats)")

    val tol = 1e-6
    val ok = maxDL < tol && maxDR < tol && maxDS < tol &&
        transMismatch == 0 && an.beatCount == expectBeats
    println(if (ok) "CROSSCHECK PASS (tol=$tol)" else "CROSSCHECK FAIL")
    if (!ok) kotlin.system.exitProcess(1)
}
