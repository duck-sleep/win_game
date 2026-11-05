"""har_pack.py — 按编码器 DLL GetHapticPayload 位布局抄的 packed HAR。

不 LoadLibrary。GetHapticPayloadSize（rva 0x29240）+ 本机 DLL 实测 20 ms A2H 包：
  头 7 bit = min(127, floor(块时长 × 4000))。20 ms → 80，不是部位数。
  每个部位 0x50：
    每条振幅/pitch 曲线：1 bit 有效 + 关键帧数 × 13
      关键帧 = 6 bit 时间（0x28a70，×63）+ 7 bit Value（0x28b60，×127）
    每个瞬态：1 bit 有效 + 20 bit（6 时间 + 7 振幅 + 7 频率）
  对齐到 8 bit 再 /8 = 字节数

A2H 在 20 ms 一块里，每条打开的曲线写 4 个相同的（力度 6 位 + 音高 7 位）。
音高 0–127 对应马达 30–400 Hz。没有砸到时曲线后面写 1 个 0，不把曲线力度填进 21 位瞬态。

逻辑内容对齐 HAR.AddParametricEffect（InterhapticsEngine.h）：
  amplitude[] Time,Value  Value∈[0,1]
  pitch[]     Time,Value  Value∈[0,1]
  pitchMin/Max
  transients[] Time, Amp, Frequency
Sage T1 部位 216 / 116。
"""
from __future__ import annotations

from dataclasses import dataclass, field

BODYPART_LEFT = 216
BODYPART_RIGHT = 116
TIME_BITS = 6
VALUE_BITS = 7
TIME_MAX = (1 << TIME_BITS) - 1   # 63
VALUE_MAX = (1 << VALUE_BITS) - 1  # 127
HEADER_BITS = 7
TRANSIENT_BITS = 20  # 6+7+7
CURVE_KF_BITS = 13   # 6+7
TICK_HZ = 4000.0     # Encode 里 duration * 4000 写入头
PERIOD_S = 0.02
A2H_KEYFRAMES = 4    # Sage T1 活对象：每条曲线 4 个相同关键帧
DEFAULT_PARTS = 2
MOTOR_FMIN = 30.0
MOTOR_FMAX = 400.0


class BitWriter:
    """MSB-first，和 DLL bts / shr 写入一致。"""

    def __init__(self):
        self.bits = 0
        self.nbits = 0

    def write(self, value: int, width: int) -> None:
        value &= (1 << width) - 1 if width < 32 else 0xFFFFFFFF
        self.bits = (self.bits << width) | value
        self.nbits += width

    def to_bytes(self) -> bytes:
        pad = (8 - (self.nbits % 8)) % 8
        nbits = self.nbits + pad
        raw = self.bits << pad
        nbytes = nbits // 8
        return raw.to_bytes(nbytes, "big") if nbytes else b""


class BitReader:
    def __init__(self, data: bytes):
        self.bits = int.from_bytes(data, "big") if data else 0
        self.nbits = len(data) * 8
        self.pos = 0

    def read(self, width: int) -> int:
        if self.pos + width > self.nbits:
            return 0
        shift = self.nbits - self.pos - width
        mask = (1 << width) - 1
        self.pos += width
        return (self.bits >> shift) & mask


def _q_time(t: float) -> int:
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return int(t * TIME_MAX + 0.5) & TIME_MAX


def _q_val(v: float, vmin: float = 0.0, vmax: float = 1.0) -> int:
    if vmax <= vmin:
        return 0
    if v > vmax:
        v = vmax
    elif v < vmin:
        v = vmin
    return int((v - vmin) * VALUE_MAX / (vmax - vmin) + 0.5) & VALUE_MAX


def _u_time(q: int) -> float:
    return q / TIME_MAX if TIME_MAX else 0.0


def _u_val(q: int, vmin: float = 0.0, vmax: float = 1.0) -> float:
    return vmin + (q / VALUE_MAX) * (vmax - vmin) if VALUE_MAX else vmin


@dataclass
class Keyframe:
    time: float
    value: float


@dataclass
class Transient:
    time: float
    amp: float
    pitch: float


@dataclass
class BodypartFrame:
    bodypart_id: int
    amplitude: list[Keyframe] = field(default_factory=list)
    pitch: list[Keyframe] = field(default_factory=list)
    transients: list[Transient] = field(default_factory=list)
    freq_hz: float = 0.0
    curves: list[tuple[float, float]] = field(default_factory=list)


def duration_ticks(period_s: float = PERIOD_S) -> int:
    """头 7 bit：min(127, round(秒 × 4000))。20 ms → 80。"""
    ticks = int(float(period_s) * TICK_HZ + 0.5)
    return max(0, min((1 << HEADER_BITS) - 1, ticks))


@dataclass
class HapticFrame:
    """GetHapticPayload 的逻辑内容 + packed 字节。"""
    pitch_min: float = 30.0
    pitch_max: float = 80.0
    parts: list[BodypartFrame] = field(default_factory=list)
    packed: bytes = b""
    ticks: int = 80

    def sample(self, t: float = 0.0) -> tuple[float, float, float, bool]:
        """混音器 / Provider 当前时刻：amp_l, amp_r, pitch_norm, has_transient。"""
        if not self.parts:
            return 0.0, 0.0, 0.0, False
        left = right = pitch = 0.0
        hit = False
        for part in self.parts:
            amp = _interp(part.amplitude, t)
            pn = _interp(part.pitch, t)
            if part.bodypart_id == BODYPART_RIGHT:
                right = amp
            else:
                left = amp
            if pn > pitch:
                pitch = pn
            for tr in part.transients:
                if abs(tr.time - t) <= 1.0 / TIME_MAX or t <= 0.0:
                    hit = True
                    if tr.amp > (right if part.bodypart_id == BODYPART_RIGHT else left):
                        if part.bodypart_id == BODYPART_RIGHT:
                            right = max(right, tr.amp)
                        else:
                            left = max(left, tr.amp)
                    if tr.pitch > pitch:
                        pitch = tr.pitch
        if len(self.parts) == 1:
            right = left
        return left, right, pitch, hit


def _interp(kfs: list[Keyframe], t: float) -> float:
    if not kfs:
        return 0.0
    if t <= kfs[0].time:
        return kfs[0].value
    for a, b in zip(kfs, kfs[1:]):
        if t <= b.time:
            span = b.time - a.time
            u = 0.0 if span <= 1e-12 else (t - a.time) / span
            return a.value + (b.value - a.value) * u
    return kfs[-1].value


def payload_size_bits(frame: HapticFrame) -> int:
    n = HEADER_BITS
    for part in frame.parts:
        for curve in (part.amplitude, part.pitch):
            n += 1
            if curve:
                n += len(curve) * CURVE_KF_BITS
        n += 1
        if part.transients:
            n += TRANSIENT_BITS
    pad = (8 - (n % 8)) % 8
    return n + pad


def freq_skirt(freq_hz: float, fmin: float, fmax: float, width: float = 50.0) -> float:
    """FUN_18001fe00：频段外各 50 Hz 线性衰减，再往外力度写 0。"""
    low = 0.0 if fmin - width < 0.0 else fmin - width
    if freq_hz <= low or freq_hz >= fmax + width:
        return 0.0
    if freq_hz >= fmin:
        if freq_hz <= fmax:
            return 1.0
        return 1.0 - (freq_hz - fmax) / width
    if fmin <= low:
        return 1.0
    return (freq_hz - low) / (fmin - low)


def q6_amp(amp: float) -> int:
    """0x28a70：clamp 到 [0,1] 后 ×63，四舍五入。"""
    a = 0.0 if amp < 0.0 else (1.0 if amp > 1.0 else float(amp))
    return int(a * TIME_MAX + 0.5) & TIME_MAX


def q7_hz(hz: float, fmin: float = MOTOR_FMIN, fmax: float = MOTOR_FMAX) -> int:
    """0x28b60：clamp 到马达 30–400 Hz，再截成 0–127。"""
    f = fmin if hz < fmin else (fmax if hz > fmax else float(hz))
    span = fmax - fmin
    if span <= 1e-9:
        return 0
    return int((f - fmin) * VALUE_MAX / span) & VALUE_MAX


def frame_scaled(frame: HapticFrame, gain: float) -> HapticFrame:
    """混音器只乘每条曲线的力度。音高不动。不改原来的帧。"""
    g = max(0.0, float(gain))
    parts = []
    for part in frame.parts:
        curves = [
            (max(0.0, min(1.0, float(a) * g)), float(hz))
            for a, hz in part.curves
        ]
        amp0 = curves[0][0] if curves else 0.0
        parts.append(BodypartFrame(
            bodypart_id=part.bodypart_id,
            amplitude=[Keyframe(0.0, amp0)] * A2H_KEYFRAMES,
            pitch=list(part.pitch),
            transients=[
                Transient(tr.time, max(0.0, min(1.0, tr.amp * g)), tr.pitch)
                for tr in part.transients
            ],
            freq_hz=part.freq_hz,
            curves=curves,
        ))
    out = HapticFrame(
        pitch_min=frame.pitch_min,
        pitch_max=frame.pitch_max,
        parts=parts,
        ticks=frame.ticks,
    )
    pack_frame(out)
    return out


def pack_frame(frame: HapticFrame) -> bytes:
    """每条 band 一条曲线，4 个相同关键帧。最后一条关掉，瞬态位写 0。"""
    w = BitWriter()
    w.write(int(frame.ticks) & ((1 << HEADER_BITS) - 1), HEADER_BITS)
    for part in frame.parts:
        curves = part.curves
        if not curves and part.amplitude:
            curves = [(part.amplitude[-1].value, part.freq_hz)]
        for amp, hz in curves:
            w.write(1, 1)
            aq, fq = q6_amp(amp), q7_hz(hz)
            for _ in range(A2H_KEYFRAMES):
                w.write(aq, TIME_BITS)
                w.write(fq, VALUE_BITS)
        w.write(0, 1)
        slots = part.transients[:2]
        for tr in slots:
            w.write(1, 1)
            w.write(q6_amp(tr.amp), TIME_BITS)
            w.write(q7_hz(tr.pitch), VALUE_BITS)
            tcode = int(round(tr.time))
            if tcode < 0:
                tcode = 0
            if tcode > VALUE_MAX:
                tcode = VALUE_MAX
            w.write(tcode, VALUE_BITS)
        if len(slots) < 2:
            w.write(0, 1)
    packed = w.to_bytes()
    frame.packed = packed
    return packed


def unpack_frame(data: bytes, pitch_min: float = 30.0, pitch_max: float = 80.0) -> HapticFrame:
    r = BitReader(data)
    ticks = r.read(HEADER_BITS)
    nparts = DEFAULT_PARTS
    ids = [BODYPART_LEFT, BODYPART_RIGHT]
    parts = []
    for i in range(nparts):
        part = BodypartFrame(bodypart_id=ids[i] if i < len(ids) else i)
        for name in ("amplitude", "pitch"):
            present = r.read(1)
            kfs = []
            if present:
                for _ in range(A2H_KEYFRAMES):
                    kfs.append(Keyframe(_u_time(r.read(TIME_BITS)), _u_val(r.read(VALUE_BITS))))
            setattr(part, name, kfs)
        present = r.read(1)
        if present:
            part.transients = [Transient(
                _u_time(r.read(TIME_BITS)),
                _u_val(r.read(VALUE_BITS)),
                _u_val(r.read(VALUE_BITS)),
            )]
        parts.append(part)
    return HapticFrame(
        pitch_min=pitch_min, pitch_max=pitch_max, parts=parts, packed=data, ticks=ticks,
    )


def frame_from_block(
    amp_l: float,
    amp_r: float,
    pitch_norm: float,
    transient_amp: float = 0.0,
    pitch_min: float = 30.0,
    pitch_max: float = 80.0,
    period_s: float = PERIOD_S,
    freq_hz: float = 0.0,
    curves_l: list[tuple[float, float]] | None = None,
    curves_r: list[tuple[float, float]] | None = None,
    transients: list[Transient] | None = None,
    transients_l: list[Transient] | None = None,
    transients_r: list[Transient] | None = None,
) -> HapticFrame:
    """一块 PCM 一个 payload。每条 band 4 个相同关键帧。每只手自己的瞬态，最多两条。"""
    del transient_amp
    pn = max(0.0, min(1.0, float(pitch_norm)))
    al = max(0.0, min(1.0, float(amp_l)))
    ar = max(0.0, min(1.0, float(amp_r)))
    hz = float(freq_hz)
    if hz <= 1.0 and pn > 0.0:
        hz = pitch_min + pn * (pitch_max - pitch_min)
    if not curves_l:
        curves_l = [(al, hz)]
    if not curves_r:
        curves_r = [(ar, hz)]
    if transients_l is None:
        transients_l = list(transients or [])
    if transients_r is None:
        transients_r = list(transients or [])
    parts = []
    for bid, curves, slots in (
        (BODYPART_LEFT, curves_l, transients_l),
        (BODYPART_RIGHT, curves_r, transients_r),
    ):
        amp0 = curves[0][0] if curves else 0.0
        hz0 = curves[0][1] if curves else hz
        parts.append(BodypartFrame(
            bodypart_id=bid,
            amplitude=[Keyframe(0.0, amp0)] * A2H_KEYFRAMES,
            pitch=[Keyframe(0.0, pn)] * A2H_KEYFRAMES,
            freq_hz=hz0,
            curves=[(max(0.0, min(1.0, a)), float(f)) for a, f in curves],
            transients=list(slots),
        ))
    frame = HapticFrame(
        pitch_min=pitch_min, pitch_max=pitch_max, parts=parts,
        ticks=duration_ticks(period_s),
    )
    pack_frame(frame)
    return frame
