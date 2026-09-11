"""band_gain_canvas.py — 雷云 Sensa HD 风格频段增益编辑器(对标官方自定义配置文件)。

视觉:
  横轴 = 频率 20Hz-8kHz(对数),底部刻度 30Hz…8kHz + 超低音/低音/中音/高音分段名;
  背景 = 实时灰色谱柱(系统声音);
  30-200Hz 触觉区叠加 3 个彩色频段区域(半透明填充,高度=增益),
  每个区域带「≡」拖拽把手(上下拖=调增益),频段边界画彩色分隔线 + 底部小方块;
  纵轴 = 增益百分比刻度。

数据:内部以百分比(0-200)显示,对外仍以倍率(0-2.0)回调,与旧版兼容。
"""
import math
import tkinter as tk

from analyzer import BAND_EDGES
from .theme import BG_INPUT, BORDER, FONT, FONT_SMALL, GREEN_DIM, TEXT, \
    TEXT_DIM, TEXT_FAINT
from .widgets import round_rect

AXIS_MIN, AXIS_MAX = 20.0, 8000.0
GAIN_MAX = 200.0  # 百分比上限(对应倍率 2.0)

# 频段边界:外边界 30/200Hz 为触觉处理范围,固定;内边界可拖
EDGE_MIN, EDGE_MAX = 30.0, 200.0
EDGE_GAP = 10.0   # 相邻边界最小间隔 (Hz)
EDGE_HIT = 6      # 边界拖拽命中半径 (px)

FREQ_TICKS = [(30, "30Hz"), (50, "50Hz"), (100, "100Hz"), (200, "200Hz"),
              (500, "500Hz"), (1000, "1kHz"), (5000, "5kHz"), (8000, "8kHz")]
SEGMENTS = [(30, 100, "超低音"), (100, 200, "低音"),
            (200, 5000, "中音"), (5000, 8000, "高音")]
AXIS_TICKS = [0, 50, 100, 150, 200]


class BandGainCanvas(tk.Canvas):
    def __init__(self, parent, width=840, height=240, band_gains=None,
                 band_colors=None, band_edges=None, command=None,
                 edge_command=None, **kw):
        super().__init__(parent, width=width, height=height, bg=BG_INPUT,
                         highlightthickness=1, highlightbackground=BORDER,
                         bd=0, **kw)
        self.w, self.h = width, height
        self.command = command
        self.edge_command = edge_command
        self.band_colors = band_colors or ["#44d62c", "#29c7d6", "#8a9bf0"]
        gains = band_gains or [1.0, 0.7, 0.3]
        self.gains = [min(2.0, max(0.0, float(g))) * 100.0 for g in gains]
        self.edges = [float(e) for e in
                      (band_edges if band_edges else BAND_EDGES)]

        self.ml = 16      # 左留白
        self.mr = 40      # 右刻度区
        self.mt = 12      # 顶部留白
        self.mb = 46      # 底部(频率刻度+分段名)
        self.pw = self.w - self.ml - self.mr
        self.ph = self.h - self.mt - self.mb

        self.viz = [0.0] * 16  # 实时谱(20Hz-8kHz,16 个对数频段)
        self._drag_i = None
        self._drag_off = 0.0
        self._drag_edge = None

        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Motion>", self._on_motion)
        # 窗口自适应:跟随父容器尺寸变化重算绘图区并重绘
        self.bind("<Configure>", self._on_resize)
        self._draw()

    # ---------- 坐标换算 ----------
    def _on_resize(self, e):
        """容器拉伸时重算绘图区(忽略初始往返和过小尺寸)。"""
        if e.width == self.w and e.height == self.h:
            return
        if e.width < 120 or e.height < 120:
            return
        self.w, self.h = e.width, e.height
        self.pw = self.w - self.ml - self.mr
        self.ph = self.h - self.mt - self.mb
        self._draw()

    def _fx(self, f):
        f = min(AXIS_MAX, max(AXIS_MIN, f))
        return self.ml + (math.log(f) - math.log(AXIS_MIN)) \
            / (math.log(AXIS_MAX) - math.log(AXIS_MIN)) * self.pw

    def _fx_inv(self, x):
        """像素 x → 频率(对数轴反变换)。"""
        t = (x - self.ml) / max(self.pw, 1)
        t = min(1.0, max(0.0, t))
        return AXIS_MIN * (AXIS_MAX / AXIS_MIN) ** t

    def _gy(self, pct):
        return self.mt + self.ph - (pct / GAIN_MAX) * self.ph

    def _band_x(self, i):
        x0, x1 = self._fx(self.edges[i]), self._fx(self.edges[i + 1])
        return x0, x1

    # ---------- 实时谱 ----------
    def update_spectrum(self, viz):
        self.viz = viz
        self._draw()

    # ---------- 数据 ----------
    def set_gains(self, band_gains):
        """外部(加载配置/切换模式)更新倍率后刷新。"""
        self.gains = [min(2.0, max(0.0, float(g))) * 100.0 for g in band_gains]
        self._draw()

    def set_band_edges(self, edges):
        """外部(加载配置/切换模式)更新频段边界后刷新。"""
        self.edges = [float(e) for e in edges]
        self._draw()

    def _emit(self):
        if self.command:
            self.command([g / 100.0 for g in self.gains])

    def _emit_edges(self):
        if self.edge_command:
            self.edge_command(list(self.edges))

    # ---------- 交互 ----------
    def _near_edge(self, x):
        """命中内边界(返回边界序号 j),没命中返回 None。"""
        for j in range(1, len(self.edges) - 1):
            if abs(x - self._fx(self.edges[j])) <= EDGE_HIT:
                return j
        return None

    def _on_motion(self, e):
        if self._drag_i is not None or self._drag_edge is not None:
            return
        near = self._near_edge(e.x) is not None \
            and self.mt <= e.y <= self.mt + self.ph
        self.configure(cursor="sb_h_double_arrow" if near else "")

    def _on_press(self, e):
        # 优先命中频段边界(左右拖调范围)
        if self.mt <= e.y <= self.mt + self.ph:
            j = self._near_edge(e.x)
            if j is not None:
                self._drag_edge = j
                return
        for i in range(len(self.gains)):
            x0, x1 = self._band_x(i)
            top = self._gy(self.gains[i])
            # 命中「≡」把手或区域内任意位置都进入拖拽
            if x0 - 4 <= e.x <= x1 + 4 and self.mt <= e.y <= self.mt + self.ph:
                self._drag_i = i
                self._drag_off = e.y - top
                if abs(e.y - top) > 14:  # 点在远处:直接跳到该高度
                    pct = (self.mt + self.ph - e.y) / self.ph * GAIN_MAX
                    self.gains[i] = min(GAIN_MAX, max(0.0, pct))
                    self._drag_off = 0.0
                    self._draw()
                    self._emit()
                return

    def _on_drag(self, e):
        if self._drag_edge is not None:
            j = self._drag_edge
            f = self._fx_inv(e.x)
            lo = max(EDGE_MIN, self.edges[j - 1] + EDGE_GAP)
            hi = min(EDGE_MAX, self.edges[j + 1] - EDGE_GAP)
            self.edges[j] = min(hi, max(lo, f))
            self._draw()
            self._emit_edges()
            return
        if self._drag_i is None:
            return
        y = e.y - self._drag_off
        pct = (self.mt + self.ph - y) / self.ph * GAIN_MAX
        self.gains[self._drag_i] = min(GAIN_MAX, max(0.0, pct))
        self._draw()
        self._emit()

    def _on_release(self, _e):
        self._drag_i = None
        self._drag_edge = None

    # ---------- 绘制 ----------
    def _draw(self):
        self.delete("all")
        base_y = self.mt + self.ph

        # 纵轴刻度 + 横向网格
        for pct in AXIS_TICKS:
            y = self._gy(pct)
            self.create_line(self.ml, y, self.ml + self.pw, y,
                             fill=BORDER, dash=(1, 3))
            self.create_text(self.ml + self.pw + 8, y, anchor="w",
                             text=f"{pct}", fill=TEXT_FAINT, font=FONT_SMALL)

        # 背景实时谱(灰色,官方样式)
        for i, level in enumerate(self.viz):
            lo = AXIS_MIN * (AXIS_MAX / AXIS_MIN) ** (i / 16.0)
            hi = AXIS_MIN * (AXIS_MAX / AXIS_MIN) ** ((i + 1) / 16.0)
            x0, x1 = self._fx(lo) + 1, self._fx(hi) - 1
            if x1 <= x0 or level < 0.015:
                continue
            bh = max(float(level), 0.02) * self.ph
            self.create_rectangle(x0, base_y - bh, x1, base_y,
                                  fill="#3c424a", outline="")

        # 触觉频段区域(30-200Hz):半透明填充 + 顶部亮线 + 「≡」把手
        for i, pct in enumerate(self.gains):
            x0, x1 = self._band_x(i)
            color = self.band_colors[i % len(self.band_colors)]
            top = self._gy(pct)
            self.create_rectangle(x0, top, x1, base_y, fill=color,
                                  stipple="gray50", outline="")
            self.create_line(x0, top, x1, top, fill=color, width=2)
            # 「≡」把手
            cx = (x0 + x1) / 2
            round_rect(self, cx - 19, top - 8, cx + 19, top + 8, 7,
                       fill=color, outline="")
            for k in range(2):
                gy = top - 3 + k * 5
                self.create_line(cx - 10, gy, cx + 10, gy,
                                 fill="#0b120a", width=2)
            # 增益数值
            self.create_text(cx, top - 16, anchor="s",
                             text=f"{pct:.0f}%", fill=color, font=FONT)

        # 频段内边界(可拖):彩线贯穿 + 底部拖拽方块 + 拖动时显示频率
        for j in range(1, len(self.edges) - 1):
            x = self._fx(self.edges[j])
            color = self.band_colors[j % len(self.band_colors)]
            self.create_line(x, self.mt, x, base_y, fill=color, width=1.5)
            self.create_rectangle(x - 5, base_y - 4, x + 5, base_y + 4,
                                  fill=color, outline="#0b120a")
            if j == self._drag_edge:
                self.create_text(x, self.mt + 2, anchor="n",
                                 text=f"{self.edges[j]:.0f}Hz",
                                 fill=color, font=FONT)
        # 触觉区外边界(30Hz / 200Hz,固定)
        for f in (self.edges[0], self.edges[-1]):
            x = self._fx(f)
            self.create_line(x, self.mt, x, base_y, fill=BORDER, width=1)

        # 频率刻度
        for f, label in FREQ_TICKS:
            x = self._fx(f)
            self.create_text(x, base_y + 7, anchor="n", text=label,
                             fill=TEXT_DIM, font=FONT_SMALL)

        # 分段名(超低音/低音/中音/高音)
        for lo, hi, name in SEGMENTS:
            x = (self._fx(lo) + self._fx(hi)) / 2
            self.create_text(x, base_y + 24, anchor="n", text=name,
                             fill=TEXT_FAINT, font=FONT_SMALL)
