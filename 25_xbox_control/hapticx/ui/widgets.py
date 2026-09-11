"""widgets.py — 雷云 Synapse 风格控件库。

包含:模块顶栏 / 胶囊页签 / 卡片 / 药丸开关 / 细轨滑条 / 复选框 /
预设列表 / 电平条 / 圆角矩形与图标绘制工具。
"""
import math
import tkinter as tk
import tkinter.font as tkfont

from .theme import (BG_CARD, BG_CARD_HOVER, BG_FIELD, BG_INPUT, BORDER,
                    BORDER_LIGHT, FONT, FONT_BOLD, FONT_LOGO, FONT_SMALL,
                    GREEN, GREEN_DIM, GREEN_TEXT, PILL_FG, TEXT, TEXT_DIM,
                    TEXT_FAINT)


# ============================ 绘图工具 ============================

def round_rect(c, x0, y0, x1, y1, r, **kw):
    """圆角矩形(Canvas polygon smooth 实现)。"""
    r = min(r, (x1 - x0) / 2, (y1 - y0) / 2)
    pts = [x0 + r, y0, x1 - r, y0, x1 - r, y0 + r, x1, y0 + r,
           x1, y1 - r, x1 - r, y1 - r, x1 - r, y1, x0 + r, y1,
           x0, y1 - r, x0, y0 + r, x0, y0 + r]
    return c.create_polygon(pts, smooth=True, **kw)


def draw_icon(c, name, cx, cy, s, color):
    """按名称在画布上绘制线性小图标,s=图标边长。"""
    if name == "gamepad":
        w, h = s * 1.7, s
        round_rect(c, cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2,
                   h / 2.4, outline=color, width=1.4)
        # 左十字键
        c.create_line(cx - w * 0.28, cy, cx - w * 0.18, cy, fill=color, width=1.4)
        c.create_line(cx - w * 0.23, cy - s * 0.16,
                      cx - w * 0.23, cy + s * 0.16, fill=color, width=1.4)
        # 右按键
        c.create_oval(cx + w * 0.24 - 2, cy - 5, cx + w * 0.24 + 2, cy - 1,
                      fill=color, outline="")
        c.create_oval(cx + w * 0.14 - 2, cy + 1, cx + w * 0.14 + 2, cy + 5,
                      fill=color, outline="")
    elif name == "rings":  # ((o)) 音频到触觉
        for k, r in ((0, s * 0.18), (1, s * 0.36), (2, s * 0.5)):
            c.create_oval(cx - r, cy - r, cx + r, cy + r,
                          outline=color, width=1.3 if k else 1.6)
        c.create_oval(cx - 2, cy - 2, cx + 2, cy + 2, fill=color, outline="")
    elif name == "spiral":
        pts = []
        for i in range(40):
            t = i / 39 * math.pi * 2.6
            r = s / 2 * (1 - i / 39 * 0.8)
            pts += [cx + r * math.cos(t), cy + r * math.sin(t)]
        c.create_line(*pts, fill=color, width=1.4, smooth=True)
    elif name == "wave":
        pts = []
        for i in range(33):
            x = cx - s / 2 + s * i / 32
            y = cy - math.sin(i / 32 * 2 * math.pi) * s * 0.3
            pts += [x, y]
        c.create_line(*pts, fill=color, width=1.4, smooth=True)
    elif name == "sliders_v":
        for k, dx in enumerate((-s * 0.32, 0.0, s * 0.32)):
            c.create_line(cx + dx, cy - s / 2, cx + dx, cy + s / 2,
                          fill=color, width=1.4)
            hy = cy - s * 0.28 + k * s * 0.28
            c.create_line(cx + dx - 3.5, hy, cx + dx + 3.5, hy,
                          fill=color, width=2.2)
    elif name == "sliders_h":
        for k, dy in enumerate((-s * 0.32, 0.0, s * 0.32)):
            c.create_line(cx - s / 2, cy + dy, cx + s / 2, cy + dy,
                          fill=color, width=1.4)
            kx = cx - s * 0.25 + k * s * 0.25
            c.create_oval(kx - 2.5, cy + dy - 2.5, kx + 2.5, cy + dy + 2.5,
                          fill=color, outline="")
    elif name == "grid":  # 仪表板
        g = s / 2 + 2
        for dx in (-g / 2, g / 2):
            for dy in (-g / 2, g / 2):
                c.create_rectangle(cx + dx - g / 4, cy + dy - g / 4,
                                   cx + dx + g / 4, cy + dy + g / 4,
                                   outline=color, width=1.2)
    elif name == "plug":  # 设备
        c.create_rectangle(cx - s * 0.3, cy - s * 0.15,
                           cx + s * 0.1, cy + s * 0.15,
                           outline=color, width=1.3)
        c.create_line(cx + s * 0.1, cy, cx + s * 0.5, cy, fill=color, width=1.6)
        for dy in (-s * 0.12, s * 0.12):
            c.create_line(cx - s * 0.5, cy + dy, cx - s * 0.3, cy + dy,
                          fill=color, width=1.3)
    elif name == "gear":  # 设置
        c.create_oval(cx - s * 0.32, cy - s * 0.32,
                      cx + s * 0.32, cy + s * 0.32, outline=color, width=1.3)
        for i in range(8):
            a = i * math.pi / 4
            c.create_line(cx + s * 0.32 * math.cos(a), cy + s * 0.32 * math.sin(a),
                          cx + s * 0.5 * math.cos(a), cy + s * 0.5 * math.sin(a),
                          fill=color, width=1.3)
    elif name == "trash":
        c.create_rectangle(cx - s * 0.3, cy - s * 0.28,
                           cx + s * 0.3, cy + s * 0.4,
                           outline=color, width=1.2)
        c.create_line(cx - s * 0.38, cy - s * 0.28,
                      cx + s * 0.38, cy - s * 0.28, fill=color, width=1.2)
        c.create_line(cx, cy - s * 0.42, cx, cy - s * 0.28, fill=color, width=1.2)
        for dx in (-s * 0.12, 0.0, s * 0.12):
            c.create_line(cx + dx, cy - s * 0.14, cx + dx, cy + s * 0.26,
                          fill=color, width=1.0)


# ============================ 卡片 ============================

class Card(tk.Frame):
    """深色模块卡片。green_title=True 时标题用雷蛇绿(官方样式)。"""

    def __init__(self, parent, title=None, subtitle=None,
                 green_title=False, help_tip=False, **kw):
        super().__init__(parent, bg=BG_CARD, highlightbackground=BORDER,
                         highlightthickness=1, **kw)
        if title:
            head = tk.Frame(self, bg=BG_CARD)
            head.pack(fill="x", padx=16, pady=(14, 2))
            tk.Label(head, text=title, bg=BG_CARD,
                     fg=GREEN if green_title else TEXT,
                     font=FONT_BOLD).pack(side="left")
            if subtitle:
                tk.Label(head, text=subtitle, bg=BG_CARD, fg=TEXT_DIM,
                         font=FONT_SMALL).pack(side="left", padx=(8, 0))
            if help_tip:
                h = tk.Canvas(head, width=16, height=16, bg=BG_CARD,
                              highlightthickness=0)
                h.pack(side="right")
                h.create_oval(1, 1, 15, 15, outline=TEXT_FAINT, width=1)
                h.create_text(8, 8, text="?", fill=TEXT_FAINT,
                              font=("Microsoft YaHei UI", 8))
        self.body = tk.Frame(self, bg=BG_CARD)
        self.body.pack(fill="both", expand=True, padx=16, pady=(6, 14))


# ============================ 模块顶栏 ============================

class ModuleBar(tk.Frame):
    """官方 Synapse 式顶部模块导航。激活模块:纯黑底 + 绿色底边条。"""

    ICONS = {"dashboard": "grid", "haptics": "gamepad",
             "devices": "plug", "settings": "gear"}

    def __init__(self, parent, modules, current, command, logo="HapticX"):
        super().__init__(parent, bg="#0a0b0c", height=54)
        self.pack_propagate(False)
        self.modules = dict(modules)  # key -> label
        self.command = command
        self.current = None
        self.tabs = {}

        logo_box = tk.Frame(self, bg="#0a0b0c")
        logo_box.pack(side="left", padx=(18, 26))
        parts = logo.rstrip("X")
        tk.Label(logo_box, text=parts, bg="#0a0b0c", fg=TEXT,
                 font=FONT_LOGO).pack(side="left")
        tk.Label(logo_box, text="X", bg="#0a0b0c", fg=GREEN,
                 font=FONT_LOGO).pack(side="left")

        for key, label in modules:
            tab = tk.Frame(self, bg="#0a0b0c", cursor="hand2")
            tab.pack(side="left", fill="y")
            inner = tk.Frame(tab, bg="#0a0b0c")
            inner.pack(padx=14, pady=8)
            ic = tk.Canvas(inner, width=20, height=20, bg="#0a0b0c",
                           highlightthickness=0)
            ic.pack(side="left")
            lbl = tk.Label(inner, text=label, bg="#0a0b0c", fg=TEXT_DIM,
                           font=FONT, anchor="w")
            lbl.pack(side="left", padx=(7, 0))
            line = tk.Frame(tab, bg="#0a0b0c", height=3)
            line.pack(side="bottom", fill="x")
            tab.bind("<Button-1>", lambda e, k=key: self.select(k, notify=True))
            lbl.bind("<Button-1>", lambda e, k=key: self.select(k, notify=True))
            self.tabs[key] = (tab, ic, lbl, line)
        self.select(current, notify=False)

    def select(self, key, notify=False):
        if key not in self.tabs:
            return
        self.current = key
        for k, (tab, ic, lbl, line) in self.tabs.items():
            active = k == key
            for w in (tab, ic, lbl):
                w.configure(bg="#000000" if active else "#0a0b0c")
            ic.delete("all")
            draw_icon(ic, self.ICONS.get(k, "grid"), 10, 10, 14,
                      GREEN if active else TEXT_FAINT)
            lbl.configure(fg=TEXT if active else TEXT_DIM,
                          font=FONT_BOLD if active else FONT)
            line.configure(bg=GREEN if active else "#0a0b0c")
        if notify and self.command:
            self.command(key)


# ============================ 胶囊页签 ============================

class PillTabs(tk.Frame):
    """居中胶囊页签(官方:选中=绿底深字,未选=灰字)。"""

    def __init__(self, parent, tabs, current, command):
        super().__init__(parent, bg=parent["bg"])
        self.command = command
        self.current = None
        self.font = tkfont.Font(font=FONT_BOLD)
        self.tabs = {}
        for key, label in tabs:
            w = self.font.measure(label) + 44
            c = tk.Canvas(self, width=w, height=30, bg=parent["bg"],
                          highlightthickness=0, cursor="hand2")
            c.pack(side="left", padx=8)
            c.create_text(w / 2, 15, text=label, font=FONT, tags="t")
            c.bind("<Button-1>", lambda e, k=key: self.select(k, notify=True))
            self.tabs[key] = (c, label)
        self.select(current, notify=False)

    def select(self, key, notify=False):
        if key not in self.tabs:
            return
        self.current = key
        for k, (c, label) in self.tabs.items():
            c.delete("all")
            if k == key:
                round_rect(c, 2, 2, c.winfo_reqwidth() - 2, 28, 14,
                           fill=GREEN, outline="")
                c.create_text(c.winfo_reqwidth() / 2, 15, text=label,
                              fill=PILL_FG, font=FONT_BOLD)
            else:
                c.create_text(c.winfo_reqwidth() / 2, 15, text=label,
                              fill=TEXT_DIM, font=FONT)
        if notify and self.command:
            self.command(key)


# ============================ 开关 ============================

class ToggleSwitch(tk.Canvas):
    """药丸形开关:开=绿轨白钮,关=灰轨灰钮。enabled=False 时锁定置灰。"""

    def __init__(self, parent, width=44, height=22, command=None,
                 initial=False, enabled=True):
        super().__init__(parent, width=width, height=height, bg=parent["bg"],
                         highlightthickness=0, bd=0)
        self.w, self.h = width, height
        self.command = command
        self.on = bool(initial)
        self.enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        if enabled:
            self.bind("<Button-1>", lambda e: self.toggle())
        self._draw()

    def _draw(self):
        self.delete("all")
        if not self.enabled:
            track, knob = "#23262a", "#565c63"
        else:
            track = GREEN if self.on else "#3a4046"
            knob = "#f2f4f2" if self.on else "#a8aeb4"
        round_rect(self, 1, 1, self.w - 1, self.h - 1, self.h / 2 - 0.5,
                   fill=track, outline="")
        cx = self.w - self.h / 2 if self.on else self.h / 2
        r = self.h / 2 - 4
        self.create_oval(cx - r, self.h / 2 - r, cx + r, self.h / 2 + r,
                         fill=knob, outline="")

    def toggle(self):
        if not self.enabled:
            return
        self.on = not self.on
        self._draw()
        if self.command:
            self.command(self.on)

    def set(self, on):
        on = bool(on)
        if self.on != on:
            self.on = on
            self._draw()


# ============================ 滑条 ============================

class RazerSlider(tk.Frame):
    """官方式细轨滑条:4px 暗轨 + 绿色已填充段 + 圆形绿钮。"""

    def __init__(self, parent, label=None, from_=0.0, to=1.0, initial=0.5,
                 command=None, width=260, show_value=False, enabled=True,
                 fmt="{:.0f}%"):
        super().__init__(parent, bg=parent["bg"])
        self.command = command
        self.from_, self.to = float(from_), float(to)
        self.value = float(initial)
        self.enabled = enabled
        self.fmt = fmt
        self.cv_w = width
        row = tk.Frame(self, bg=self["bg"])
        row.pack(fill="x")
        if label:
            tk.Label(row, text=label, bg=self["bg"], fg=TEXT_DIM,
                     font=FONT_SMALL).pack(side="left")
        self.cv = tk.Canvas(row, width=width, height=26, bg=self["bg"],
                            highlightthickness=0, bd=0,
                            cursor="hand2" if enabled else "arrow")
        self.cv.pack(side="left", fill="x", expand=True)
        self.value_lbl = None
        if show_value:
            self.value_lbl = tk.Label(row, text=self._fmt(), bg=self["bg"],
                                      fg=GREEN_TEXT, font=FONT_BOLD, width=5)
            self.value_lbl.pack(side="left")
        if enabled:
            self.cv.bind("<Button-1>", self._on_ev)
            self.cv.bind("<B1-Motion>", self._on_ev)
        self._draw()

    def _fmt(self):
        return self.fmt.format(self.value)

    def _x2val(self, x):
        pad = 10
        f = min(1.0, max(0.0, (x - pad) / max(self.cv_w - 2 * pad, 1)))
        return self.from_ + f * (self.to - self.from_)

    def _on_ev(self, e):
        self.set(self._x2val(e.x), notify=True)

    def _draw(self):
        self.cv.delete("all")
        pad, y, r = 10, 13, 7
        w = self.cv_w
        f = (self.value - self.from_) / max(self.to - self.from_, 1e-9)
        f = min(1.0, max(0.0, f))
        kx = pad + f * (w - 2 * pad)
        if self.enabled:
            track, fill, knob, ring = "#0d0e10", GREEN, GREEN, "#1f3d17"
        else:
            track, fill, knob, ring = "#14161a", "#3a4046", "#565c63", "#23262a"
        round_rect(self.cv, pad, y - 2, w - pad, y + 2, 2,
                   fill=track, outline=BORDER)
        if kx > pad + 3:
            round_rect(self.cv, pad, y - 2, kx, y + 2, 2, fill=fill, outline="")
        self.cv.create_oval(kx - r, y - r, kx + r, y + r,
                            fill=knob, outline=ring, width=1.5)
        if self.value_lbl:
            self.value_lbl.configure(text=self._fmt())

    def set(self, val, notify=False):
        if self.to > self.from_:
            step = (self.to - self.from_) / 200.0
            val = round(val / step) * step
        self.value = min(self.to, max(self.from_, val))
        self._draw()
        if notify and self.enabled and self.command:
            self.command(self.value)


# ============================ 复选框 ============================

class CheckBox(tk.Frame):
    """绿色复选框 + 文字(官方设备卡样式)。"""

    def __init__(self, parent, text, initial=False, command=None):
        super().__init__(parent, bg=parent["bg"])
        self.command = command
        self.on = bool(initial)
        self.box = tk.Canvas(self, width=16, height=16, bg=parent["bg"],
                             highlightthickness=0, cursor="hand2")
        self.box.pack(side="left")
        self.lbl = tk.Label(self, text=text, bg=parent["bg"], fg=TEXT,
                            font=FONT_SMALL, cursor="hand2")
        self.lbl.pack(side="left", padx=(8, 0))
        for w in (self.box, self.lbl):
            w.bind("<Button-1>", lambda e: self.toggle())
        self._draw()

    def _draw(self):
        self.box.delete("all")
        if self.on:
            self.box.create_rectangle(1, 1, 15, 15, fill=GREEN, outline=GREEN)
            self.box.create_line(4, 8, 7, 11, fill="#0b120a", width=2,
                                 joinstyle="miter", capstyle="butt")
            self.box.create_line(7, 11, 12, 4, fill="#0b120a", width=2,
                                 joinstyle="miter", capstyle="butt")
        else:
            self.box.create_rectangle(1, 1, 15, 15, fill=BG_INPUT,
                                      outline=BORDER_LIGHT)

    def toggle(self):
        self.on = not self.on
        self._draw()
        if self.command:
            self.command(self.on)

    def set(self, on):
        if self.on != bool(on):
            self.on = bool(on)
            self._draw()


# ============================ 预设列表 ============================

class PresetList(tk.Frame):
    """官方音频到触觉配置文件式竖排预设按钮。选中=绿框亮字。"""

    def __init__(self, parent, items, current, command, width=250):
        super().__init__(parent, bg=parent["bg"])
        self.command = command
        self.items = {}
        self.current = None
        self.width = width
        for cid, icon, zh in items:
            c = tk.Canvas(self, width=width, height=40, bg=parent["bg"],
                          highlightthickness=0, cursor="hand2")
            c.pack(fill="x", pady=4)
            c.bind("<Button-1>", lambda e, k=cid: self.select(k, notify=True))
            c.bind("<Enter>", lambda e, k=cid: self._hover(k, True))
            c.bind("<Leave>", lambda e, k=cid: self._hover(k, False))
            self.items[cid] = (c, icon, zh, False)
        self.select(current, notify=False)

    def _hover(self, cid, on):
        c, icon, zh, _ = self.items[cid]
        self.items[cid] = (c, icon, zh, on)
        self._draw(cid)

    def select(self, cid, notify=False):
        if self.current != cid:
            self.current = cid
            for k in self.items:
                self._draw(k)
        if notify and self.command:
            self.command(cid)

    def _draw(self, cid):
        c, icon, zh, hov = self.items[cid]
        c.delete("all")
        w, h = self.width, 40
        sel = cid == self.current
        round_rect(c, 1.5, 1.5, w - 1.5, h - 1.5, 8,
                   fill="#20351c" if sel else (BG_CARD_HOVER if hov else BG_FIELD),
                   outline=GREEN if sel else BORDER, width=2 if sel else 1)
        ic = GREEN if sel else TEXT_DIM
        draw_icon(c, icon, 26, h / 2, 16, ic)
        c.create_text(44, h / 2, anchor="w", text=zh,
                      fill=TEXT if sel else TEXT_DIM, font=FONT)


# ============================ 电平条 ============================

class LevelBar(tk.Canvas):
    """细电平条(马达输出)。"""

    def __init__(self, parent, label, width=230, color=GREEN):
        super().__init__(parent, width=width, height=18, bg=parent["bg"],
                         highlightthickness=0)
        self.label = label
        self.width = width
        self.color = color
        self.level = 0.0
        tk.Label(self, text=label, bg=parent["bg"], fg=TEXT_DIM,
                 font=FONT_SMALL).place(x=0, y=1)
        self.pct = tk.Label(self, text="0%", bg=parent["bg"], fg=TEXT,
                            font=FONT_SMALL)
        self.pct.place(x=width - 34, y=1)

    def set(self, level):
        self.level = max(0.0, min(1.0, float(level)))
        self.delete("all")
        x0, x1 = 86, self.width - 44
        self.create_rectangle(x0, 4, x1, 14, fill=BG_INPUT, outline=BORDER)
        fw = (x1 - x0) * self.level
        if fw > 1:
            self.create_rectangle(x0, 4, x0 + fw, 14, fill=self.color, outline="")
        self.pct.configure(text=f"{self.level * 100:.0f}%")


# ============================ 状态点 ============================

class StatusDot(tk.Canvas):
    """状态指示灯(绿=正常/灰=离线/黄=提醒/红=错误)。"""

    COLORS = {"ok": GREEN, "off": "#5c646b", "warn": "#e8b64c", "err": "#e8544c"}

    def __init__(self, parent, size=10, state="off"):
        super().__init__(parent, width=size, height=size,
                         bg=parent["bg"], highlightthickness=0, bd=0)
        self.size = size
        self.set(state)

    def set(self, state):
        self.delete("all")
        color = self.COLORS.get(state, "#5c646b")
        self.create_oval(0, 0, self.size, self.size, fill=color, outline="")
