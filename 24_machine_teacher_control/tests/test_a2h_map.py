"""N6 的验收：映射逐字节对得上，瞬态去重次数和时刻对得上。"""

import unittest

import numpy as np

from ns_rumble.a2h_map import A2HToNS
from ns_rumble.codec import encode_side
from ns_rumble.vendor.a2h_encoder import A2HEncoder
from ns_rumble.vendor.har_pack import frame_scaled
from tests.test_a2h_golden import BLOCK, BLOCKS, GAIN, SR, feed, sine


class TestMapBytes(unittest.TestCase):
    def test_transient_example_is_pure_function(self):
        self.assertEqual(encode_side(160, 0.85, 58.594, 0.67).hex(" "), "80 b8 92 68")

    def test_case1_both_hands(self):
        """60 Hz 单音：映射后左右两只手都应该是 04 08 92 68。"""
        enc = A2HEncoder(gain=1.0)
        mapper = A2HToNS(SR)
        total = 0
        for k in range(BLOCKS):
            t = (np.arange(BLOCK) + k * BLOCK) / SR
            blk = np.stack([sine(60.0)(t)] * 2, axis=1)
            enc.process_block(blk, SR)
            total += blk.shape[0]
            frame = frame_scaled(enc.last_frame, GAIN)
            left, right = mapper.frame_to_bytes(frame, total, len(enc._raw_l))
        self.assertEqual(left.hex(" "), "04 08 92 68")
        self.assertEqual(right.hex(" "), "04 08 92 68")

    def test_case2_right_hand(self):
        """左 60 Hz 右 150 Hz：右手应该是 78 92 3e 40。"""
        enc = A2HEncoder(gain=1.0)
        mapper = A2HToNS(SR)
        total = 0
        for k in range(BLOCKS):
            t = (np.arange(BLOCK) + k * BLOCK) / SR
            blk = np.stack([sine(60.0)(t), sine(150.0)(t)], axis=1)
            enc.process_block(blk, SR)
            total += blk.shape[0]
            frame = frame_scaled(enc.last_frame, GAIN)
            _left, right = mapper.frame_to_bytes(frame, total, len(enc._raw_l))
        self.assertEqual(right.hex(" "), "78 92 3e 40")


class TestTransientDedup(unittest.TestCase):
    def test_gated_burst(self):
        """0.85·sin(60Hz) 被 4 Hz 方波门控：100 块，去重后应触发 32 次。"""
        enc = A2HEncoder(gain=1.0)
        mapper = A2HToNS(SR)
        total = 0
        for _ in range(100):
            t = (np.arange(BLOCK) + total) / SR
            x = 0.85 * np.sin(2 * np.pi * 60 * t) * (np.sin(2 * np.pi * 4 * t) > 0)
            blk = np.stack([x, x], axis=1)
            enc.process_block(blk, SR)
            total += blk.shape[0]
            mapper.frame_to_bytes(enc.last_frame, total, len(enc._raw_l))

        hits = mapper.hits[0]
        self.assertEqual(len(hits), 32, f"触发 {len(hits)} 次，前 8 个 {hits[:8]}")
        first5 = [round(h / SR, 3) for h in hits[:5]]
        self.assertEqual(first5, [0.004, 0.037, 0.071, 0.104, 0.254], f"前 5 次时刻 {first5}")


if __name__ == "__main__":
    unittest.main()
