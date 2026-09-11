"""spectrum_canvas.py — 实时频谱 + 双马达电平画布。

16 个对数频段柱(20Hz-8kHz),触觉频段(30-130Hz)用雷蛇绿,其余暗灰;
下方左/右马达电平条 + 节拍指示灯。
"""
import tkinter as tk

from .theme import (BG_CARD, BG_FIELD, BORDER, FONT_SMALL, GREEN, GREEN_DIM,
                    TEXT_DIM, TEXT_FAINT, FONT, FONT_BOLD, TEXT)

BAR_COUNT = 16
HIST = 8  # 峰值保持条回落速度相关


class SpectrumCanvas(tk.Canvas):
    def __init__(self, parent, width=560, height=170):
        super().__init__(parent, width=width, height=height, bg=BG_CARD,
                         highlightthickness=0, bd=0)
        self.w, self.h = width, height
        self.peak_hold = [0.0] * BAR_COUNT
        self.beat_flash = 0.0
        self._layout()

    def _layout(self):
        self.spectrum_top = 24
        # 底部需容纳"频率刻度 + 两行马达条"(约 14 + 26*2 高度),
        # 频谱柱高度 = 画布高 - 顶部标题 - 94,否则右马达条会被裁出画布
        self.spectrum_h = self.h - 94
        self.motor_top = self.spectrum_top + self.spectrum_h + 14
        pad = 2
        self.bar_w = (self.w - 24 - pad * (BAR_COUNT - 1)) / BAR_COUNT

    def update_data(self, viz, in_band, left, right, beat):
        self.delete("all")

        # 标题行
        self.create_text(4, 6, anchor="nw", text="实时频谱",
                         fill=TEXT, font=FONT_BOLD)
        self.create_text(self.w - 4, 6, anchor="ne", text="30-130Hz 触觉频段",
                         fill=GREEN, font=FONT_SMALL)
        # 节拍指示
        if beat:
            self.beat_flash = 1.0
        self.beat_flash *= 0.72
        if self.beat_flash > 0.05:
            bx = self.w - 150
            self.create_oval(bx - 8, 4, bx + 8, 20,
                             fill=GREEN, outline=GREEN_DIM)
            self.create_text(bx + 14, 12, anchor="w", text="BEAT",
                             fill=GREEN, font=FONT_SMALL)

        # 频谱柱
        base_y = self.spectrum_top + self.spectrum_h
        for i, level in enumerate(viz):
            x = 12 + i * (self.bar_w + 2)
            # 峰值保持
            self.peak_hold[i] = max(float(level), self.peak_hold[i] - 0.025)
            ph = self.peak_hold[i]
            color = GREEN if in_band[i] else "#3f464e"
            if float(level) > 0.01:
                bar_h = max(float(level), 0.02) * self.spectrum_h
                self.create_rectangle(x, base_y - bar_h, x + self.bar_w, base_y,
                                      fill=color, outline="")
            if ph > 0.05:
                py = base_y - ph * self.spectrum_h
                self.create_rectangle(x, py - 2, x + self.bar_w, py,
                                      fill="#6a7580", outline="")

        # 频率刻度
        marks = [(0, "20"), (4, "60"), (7, "150"), (11, "600"), (15, "8k")]
        for idx, label in marks:
            x = 12 + idx * (self.bar_w + 2) + self.bar_w / 2
            self.create_text(x, base_y + 12, anchor="n", text=label,
                             fill=TEXT_FAINT, font=FONT_SMALL)

        # 马达电平条
        for row, (name, level) in enumerate((("左马达(低频)", left),
                                             ("右马达(高频·节拍)", right))):
            y = self.motor_top + row * 26
            self.create_text(12, y + 7, anchor="nw", text=name,
                            fill=TEXT_DIM, font=FONT_SMALL)
            bx, bw = 150, self.w - 170
            self.create_rectangle(bx, y, bx + bw, y + 14,
                                  fill=BG_FIELD, outline=BORDER)
            fw = bw * max(0.0, min(1.0, level))
            if fw > 1:
                self.create_rectangle(bx, y, bx + fw, y + 14,
                                      fill=GREEN, outline="")
            self.create_text(bx + bw + 8, y + 7, anchor="nw",
                            text=f"{level * 100:4.0f}%", fill=TEXT,
                            font=FONT_SMALL)
