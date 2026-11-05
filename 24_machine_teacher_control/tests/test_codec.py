"""N2 的验收：编码逐字节对得上工单里的「标准值」表。"""

import unittest

from ns_rumble.codec import NEUTRAL, amp_index, encode_side


class TestAmpIndex(unittest.TestCase):
    GOLDEN = [
        (0.018, 4),
        (0.0269, 7),
        (0.2, 28),
        (0.25, 36),
        (0.5, 68),
        (0.5639, 73),
        (0.67, 81),
        (0.85, 92),
        (1.0, 100),
        (1.5, 100),      # 超范围要夹到上限，不能越 100
    ]

    def test_table(self):
        for amp, want in self.GOLDEN:
            self.assertEqual(amp_index(amp), want, f"amp_index({amp})")

    def test_zero_and_negative(self):
        self.assertEqual(amp_index(0.0), 0)
        self.assertEqual(amp_index(-1.0), 0)


class TestEncodeSide(unittest.TestCase):
    # encode_side(hf_hz, hf_amp, lf_hz, lf_amp) -> 4 字节（工单「标准值」表逐行）
    GOLDEN = [
        ((320, 0, 160, 0), "00 01 40 40"),
        ((160, 0.5, 160, 0.5), "80 88 40 62"),
        ((320, 0.5, 320, 0.5), "00 89 60 62"),
        ((640, 0.5, 640, 0.5), "80 89 7f 62"),          # 低频夹到 626
        ((160, 0.2, 160, 0.2), "80 38 40 4e"),
        ((160, 0.0119, 160, 0.0119), "80 04 40 41"),
        ((1252, 1.0, 1252, 1.0), "fc c9 7f 72"),        # 低频夹到 626
        ((261.63, 0.5, 261.63, 0.5), "dc 88 57 62"),    # C4
        ((392.0, 0.5, 392.0, 0.5), "24 89 69 62"),      # G4
        ((440.0, 0.5, 440.0, 0.5), "3c 89 6f 62"),      # A4
        ((58.594, 0.018, 58.594, 0.67), "04 08 92 68"),  # 雷云 60 Hz 例
        ((152.344, 0.5639, 152.344, 0.0), "78 92 3e 40"),  # 雷云 150 Hz 例
        ((160, 0.85, 58.594, 0.67), "80 b8 92 68"),      # 瞬态叠加例
    ]

    def test_table(self):
        for args, want in self.GOLDEN:
            self.assertEqual(encode_side(*args).hex(" "), want, f"encode_side{args}")

    def test_silence_is_neutral(self):
        self.assertEqual(encode_side(320, 0, 160, 0), NEUTRAL)
        self.assertEqual(encode_side(1000, 0, 100, 0), NEUTRAL)

    def test_length_and_range(self):
        for args, _ in self.GOLDEN:
            b = encode_side(*args)
            self.assertEqual(len(b), 4)
        # 振幅档不许越过 100 → 高频振幅字节 = 2i ≤ 0xC8
        b = encode_side(1252, 9.9, 1252, 9.9)
        self.assertLessEqual(b[1] & 0xFE, 0xC8)


if __name__ == "__main__":
    unittest.main()
