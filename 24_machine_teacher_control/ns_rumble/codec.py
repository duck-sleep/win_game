"""NS（Switch Pro Controller 协议）HD 振动的 4 字节编码。

协议与公式抄自 16_机械师唱小星星.md「协议」章，其上游是：
  - dekuNukem Nintendo_Switch_Reverse_Engineering: rumble_data_table.md / bluetooth_hid_notes.md
  - SDL src/joystick/hidapi/SDL_hidapi_switch.c: EncodeRumble

振幅档上限 AMP_MAX_INDEX=100（dekuNukem 表 HA=0xC8），表里更高的值原文标注会伤 LRA，
任何路径都要夹到 <=100。
"""

from __future__ import annotations

import math

# 静止 = 高频 320 Hz 振幅 0、低频 160 Hz 振幅 0
NEUTRAL = bytes([0x00, 0x01, 0x40, 0x40])

# 安全上限（见模块 docstring）
AMP_MAX_INDEX = 100

# 振荡器可编码范围
HF_MIN, HF_MAX = 0x004, 0x1FC   # 81.75 – 1252.57 Hz
LF_MIN, LF_MAX = 0x01, 0x7F     # 40.88 – 626.29 Hz


def amp_index(amp: float) -> int:
    """振幅 0.0–1.0 → dekuNukem 振幅表行号 0–100（HA = 2i）。"""
    if amp <= 0.0:
        return 0
    amp = min(amp, 1.0)
    if amp > 0.23:
        i = round(math.log2(amp * 8.7) * 32.0)
    elif amp > 0.12:
        i = round(math.log2(amp * 17.0) * 16.0)
    else:
        i = max(1, round(15 + 4 * math.log2(amp / 0.112491)))
    return max(0, min(AMP_MAX_INDEX, int(i)))


def freq_code(hz: float) -> int:
    """Hz → 对数频率码 e = round(log2(Hz/10) * 32)，1/32 八度一档。"""
    hz = min(max(hz, 1.0), 1252.0)
    return int(round(math.log2(hz / 10.0) * 32.0))


def encode_side(hf_hz: float, hf_amp: float, lf_hz: float, lf_amp: float) -> bytes:
    """一侧马达的 4 字节：高频振荡器 + 低频振荡器。"""
    ih, il = amp_index(hf_amp), amp_index(lf_amp)
    if ih == 0 and il == 0:
        return NEUTRAL
    hf = max(HF_MIN, min(HF_MAX, (freq_code(hf_hz) - 0x60) * 4))
    lf = max(LF_MIN, min(LF_MAX, freq_code(lf_hz) - 0x40))
    # 低频振幅是 15 位 + 1 位奇偶标志；dekuNukem 示例公式 encoded/2+64 会丢那位奇偶标志
    lf_amp16 = ((il & 1) << 15) | (0x40 + (il >> 1))
    return bytes([
        hf & 0xFF,
        (ih * 2) | ((hf >> 8) & 0x01),
        lf | ((lf_amp16 >> 8) & 0x80),
        lf_amp16 & 0xFF,
    ])
