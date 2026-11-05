"""N5 的验收：复制过来的雷云对齐编码器，标准值必须逐帧对得上。

对不上**不要去改编码器**（它在 25_xbox_control 里和雷云 DLL 逐帧对过），
先怀疑复制错了 / numpy 版本 / 导入路径。
"""

import unittest

import numpy as np

from ns_rumble.vendor.a2h_encoder import A2HEncoder
from ns_rumble.vendor.har_pack import frame_scaled

SR = 48000.0
BLOCK = 960          # 20 ms
BLOCKS = 25          # 喂到稳态
GAIN = 0.67          # 雷云滑条 67

AMP_TOL = 1e-3
HZ_TOL = 1e-2


def sine(hz):
    return lambda t: 0.4 * np.sin(2.0 * np.pi * hz * t)


def feed(sig_l, sig_r=None):
    """相位从 0 连续，喂 BLOCKS 块，返回乘过增益的最后一帧。"""
    enc = A2HEncoder(gain=1.0)
    for k in range(BLOCKS):
        t = (np.arange(BLOCK) + k * BLOCK) / SR
        left = sig_l(t)
        right = left if sig_r is None else sig_r(t)
        blk = np.stack([left, right], axis=1)
        enc.process_block(blk, SR)
    return frame_scaled(enc.last_frame, GAIN)


def check_curves(test, part, want):
    test.assertGreaterEqual(len(part.curves), len(want), f"曲线条数不够: {part.curves}")
    for (got_amp, got_hz), (want_amp, want_hz) in zip(part.curves, want):
        test.assertAlmostEqual(got_amp, want_amp, delta=AMP_TOL,
                               msg=f"力度 {got_amp} ≠ {want_amp}")
        test.assertAlmostEqual(got_hz, want_hz, delta=HZ_TOL,
                               msg=f"Hz {got_hz} ≠ {want_hz}")


class TestA2HGolden(unittest.TestCase):
    def test_case1_both_60hz(self):
        """左右都是 0.4·sin(2π·60t)：两只手都是 60 Hz 带那条曲线吃满。"""
        frame = feed(sine(60.0))
        self.assertEqual(len(frame.parts), 2)
        for part in frame.parts:
            check_curves(self, part, [(0.67, 58.594), (0.018, 58.594)])
            self.assertEqual(part.transients, [], "稳态正弦不该有瞬态")

    def test_case2_left_60_right_150(self):
        """左右不同频率：右手换到 150 Hz 带，第一条曲线掉到 0。"""
        frame = feed(sine(60.0), sine(150.0))
        check_curves(self, frame.parts[0], [(0.67, 58.594), (0.018, 58.594)])
        check_curves(self, frame.parts[1], [(0.0, 152.344), (0.5639, 152.344)])


if __name__ == "__main__":
    unittest.main()
