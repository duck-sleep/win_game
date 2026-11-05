"""机械师 G6 V2（NS 模式，USB 直连，枚举成 057E:2009 Pro Controller）的 HID 收发。

协议字节只用工单 16_机械师唱小星星.md「协议」章里的那些：
  输出 80 02/03/04（USB 专有）、01（振动+子命令）、10（只振动）；输入 81 xx / 21 xx / 30 xx。
不发子命令 80 06（复位）、80 92（任意 UART），不碰 SPI 写。
"""

from __future__ import annotations

import time

import hid

from .codec import NEUTRAL

INIT_RETRY = 3
REPLY_MS = 20          # 单次 read 的等待
REPLY_BUDGET_MS = 100  # 一个应答总共等多久


class NSController:
    VID, PID, LEN = 0x057E, 0x2009, 64

    # 实测左右与协议相反时置 True（N3 用户判），不要在 send 之外另做交换
    SWAP_LR = False

    def __init__(self) -> None:
        self.dev = None
        self._count = 0

    # ---------- 底层 ----------

    def open(self) -> None:
        found = hid.enumerate(self.VID, self.PID)
        if not found:
            raise RuntimeError(
                f"没找到 {self.VID:04X}:{self.PID:04X}：手柄不在 NS 模式，或没插 USB")
        dev = hid.device()
        dev.open_path(found[0]["path"])
        dev.set_nonblocking(False)
        self.dev = dev

    def _write(self, payload: bytes) -> None:
        pkt = bytes(payload[:self.LEN]).ljust(self.LEN, b"\x00")
        n = self.dev.write(pkt)
        if n < 0:
            raise OSError(f"HID write 失败（返回 {n}）")

    def _next_count(self) -> int:
        self._count = (self._count + 1) & 0x0F
        return self._count

    def _wait_reply(self, want0: int, want1: int | None = None) -> bytes | None:
        """读应答，总超时 REPLY_BUDGET_MS；0x30 之类无关报告直接跳过。"""
        deadline = time.monotonic() + REPLY_BUDGET_MS / 1000.0
        while time.monotonic() < deadline:
            r = bytes(self.dev.read(64, REPLY_MS) or b"")
            if not r or r[0] != want0:
                continue
            if want1 is not None and (len(r) < 2 or r[1] != want1):
                continue
            return r
        return None

    # ---------- 初始化 ----------

    def init_usb(self) -> None:
        # 80 02：100 ms 超时，最多重试 3 次；还等不到就是真连不上
        for _ in range(INIT_RETRY):
            self._write(bytes([0x80, 0x02]))
            if self._wait_reply(0x81, 0x02) is not None:
                break
        else:
            raise RuntimeError("80 02 握手无应答：手柄可能被 Steam/BetterJoy 占用，或不在 NS 模式")

        self._write(bytes([0x80, 0x03]))          # 切高速；有的兼容手柄不回，继续
        self._wait_reply(0x81, 0x03)

        self._write(bytes([0x80, 0x02]))          # 再来一次握手；等不到也继续
        self._wait_reply(0x81, 0x02)

        self._write(bytes([0x80, 0x04]))          # 强制只走 USB，无应答，不等

    def enable_vibration(self) -> None:
        pkt = bytes([0x01, self._next_count()]) + NEUTRAL + NEUTRAL + bytes([0x48, 0x01])
        self._write(pkt)
        deadline = time.monotonic() + REPLY_BUDGET_MS / 1000.0
        while time.monotonic() < deadline:
            r = bytes(self.dev.read(64, REPLY_MS) or b"")
            if len(r) >= 15 and r[0] == 0x21 and (r[13] & 0x80) and r[14] == 0x48:
                return
        raise RuntimeError("子命令 48（开振动）没有 ACK")

    # ---------- 发振动 ----------

    def send(self, left4: bytes, right4: bytes) -> None:
        if len(left4) != 4 or len(right4) != 4:
            raise ValueError(f"一侧必须是 4 字节，收到 {len(left4)} / {len(right4)}")
        l, r = (right4, left4) if self.SWAP_LR else (left4, right4)
        self._write(bytes([0x10, self._next_count()]) + bytes(l) + bytes(r))

    def stop(self) -> None:
        for _ in range(3):
            self.send(NEUTRAL, NEUTRAL)
            time.sleep(0.020)

    def close(self) -> None:
        if self.dev is None:
            return
        try:
            self.stop()
        finally:
            d, self.dev = self.dev, None
            d.close()
