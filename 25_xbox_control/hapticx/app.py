"""app.py — HapticX 主界面(对标雷云 Synapse SENSA HD 版式)。

结构:
  顶部模块栏(仪表板 / SENSA HD 触觉反馈 / 设备 / 设置)
  └ 触觉反馈模块内居中胶囊页签:
      动态触觉反馈        → 左"动态触觉反馈"卡 + 右"检测到的设备"卡
      音频到触觉配置文件  → 预设列表 + 音频与输出卡 + Sensa HD 频段增益编辑器

运行:python app.py
"""
import os
import sys
import tkinter as tk
from tkinter import ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analyzer import (BAND_LABELS, MODE_BAND_GAINS, band_edges_for,
                      band_gains_for)
from audio_capture import list_output_devices
from config_store import load, save
from pipeline import HapticPipeline
from razer_probe import format_summary, probe_all
from ui import theme as T
from ui.band_gain_canvas import BandGainCanvas
from ui.spectrum_canvas import SpectrumCanvas
from ui.widgets import (Card, CheckBox, LevelBar, ModuleBar, PillTabs,
                        PresetList, RazerSlider, StatusDot, ToggleSwitch,
                        draw_icon)

MODE_ORDER = ["controlled", "balanced", "dynamic", "custom"]


def _lbl(parent, text, fg=T.TEXT_DIM, font=None, **kw):
    return tk.Label(parent, text=text, bg=parent["bg"], fg=fg,
                    font=font or T.FONT_SMALL, **kw)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("HapticX — SENSA HD 触觉反馈")
        self.configure(bg=T.BG)
        self.geometry("1100x860")
        self.minsize(1000, 700)

        self.config_data = load()
        self.probe_info = probe_all()
        self.pipeline = HapticPipeline(self.config_data)
        self.current_page = "haptics"
        self.haptic_tab = "dynamic"

        self._build_topbar()
        self._build_content()
        self._build_statusbar()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._last_device_poll = 0.0
        self.after(200, self._startup)
        self.after(33, self._refresh)

    # ==================== 顶部模块栏 ====================
    def _build_topbar(self):
        self.module_bar = ModuleBar(
            self,
            [("dashboard", "仪表板"), ("haptics", "SENSA HD 触觉反馈"),
             ("devices", "设备"), ("settings", "设置")],
            current="haptics", command=self._show_module)
        self.module_bar.pack(fill="x")

    # ==================== 内容区 ====================
    def _build_content(self):
        self.content = tk.Frame(self, bg=T.BG)
        self.content.pack(fill="both", expand=True, padx=24, pady=(14, 8))
        self.pages = {}
        for key in ("dashboard", "haptics", "devices", "settings"):
            self.pages[key] = tk.Frame(self.content, bg=T.BG)
        self._build_page_dashboard()
        self._build_page_haptics()
        self._build_page_devices()
        self._build_page_settings()
        self._show_module("haptics", notify=False)

    def _show_module(self, key, notify=True):
        if notify:
            self.module_bar.select(key, notify=False)
        for k, page in self.pages.items():
            page.pack_forget()
        self.pages[key].pack(fill="both", expand=True)
        self.current_page = key

    # ---------- 胶囊页签容器 ----------
    def _build_page_haptics(self):
        p = self.pages["haptics"]
        PillTabs(p, [("dynamic", "动态触觉反馈"),
                     ("profiles", "音频到触觉配置文件")],
                 current="dynamic", command=self._show_haptic_tab).pack(pady=(0, 14))
        self.haptic_pages = {
            "dynamic": tk.Frame(p, bg=T.BG),
            "profiles": tk.Frame(p, bg=T.BG),
        }
        self._build_tab_dynamic(self.haptic_pages["dynamic"])
        self._build_tab_profiles(self.haptic_pages["profiles"])
        self._show_haptic_tab("dynamic", notify=False)

    def _show_haptic_tab(self, key, notify=True):
        if notify:
            pass  # PillTabs 自身已高亮
        for k, page in self.haptic_pages.items():
            page.pack_forget()
        self.haptic_pages[key].pack(fill="both", expand=True)
        self.haptic_tab = key

    # ---------- 页签 1:动态触觉反馈 ----------
    def _build_tab_dynamic(self, p):
        grid = tk.Frame(p, bg=T.BG)
        grid.pack(fill="both", expand=True)
        grid.columnconfigure(0, weight=3)
        grid.columnconfigure(1, weight=2)

        # ---- 左卡:动态触觉反馈 ----
        left = Card(grid, title="动态触觉反馈", green_title=True, help_tip=True)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        b = left.body
        _lbl(b, "体验 HapticX 带来的无缝触觉反馈,它在你游玩游戏时自动在"
                "音频到触觉与游戏触觉之间切换。", fg=T.TEXT_DIM,
             wraplength=420, justify="left").pack(fill="x", pady=(2, 10))

        src = tk.Frame(b, bg=T.BG_CARD)
        src.pack(fill="x", pady=(0, 10))
        ic = tk.Canvas(src, width=22, height=20, bg=T.BG_CARD,
                       highlightthickness=0)
        ic.pack(side="left")
        draw_icon(ic, "gamepad", 11, 10, 13, T.TEXT)
        self.src_lbl = _lbl(src, "正在捕获:系统声音", fg=T.TEXT, font=T.FONT)
        self.src_lbl.pack(side="left", padx=(8, 0))

        # 子块 1:SENSA HD 游戏(需游戏支持,置灰)
        blk1 = tk.Frame(b, bg=T.BG_FIELD, highlightbackground=T.BORDER,
                        highlightthickness=1)
        blk1.pack(fill="x", pady=(0, 10), ipadx=12, ipady=10)
        r1 = tk.Frame(blk1, bg=T.BG_FIELD)
        r1.pack(fill="x", padx=12)
        ic1 = tk.Canvas(r1, width=40, height=36, bg=T.BG_FIELD,
                        highlightthickness=0)
        ic1.pack(side="left")
        draw_icon(ic1, "spiral", 20, 18, 22, T.BLUE)
        tk.Label(r1, text="SENSA HD 游戏", bg=T.BG_FIELD, fg=T.TEXT,
                 font=T.FONT_BOLD).pack(side="left", padx=(8, 0))
        ToggleSwitch(r1, initial=False, enabled=False).pack(side="right")
        _lbl(blk1, "在游玩 Sensa HD 游戏时,可感受到与我们与开发人员共同"
                   "创造的丰富自定义触觉反馈效果。", fg=T.TEXT_FAINT,
             wraplength=380, justify="left").pack(fill="x", padx=12, pady=(4, 0))
        _lbl(blk1, "查看游戏 ↗", fg=T.GREEN, font=T.FONT_LINK)\
            .pack(anchor="e", padx=12)

        # 子块 2:音频到触觉(总开关 + 强度)
        blk2 = tk.Frame(b, bg=T.BG_FIELD, highlightbackground=T.GREEN_DIM,
                        highlightthickness=1)
        blk2.pack(fill="x", ipadx=12, ipady=10)
        r2 = tk.Frame(blk2, bg=T.BG_FIELD)
        r2.pack(fill="x", padx=12)
        ic2 = tk.Canvas(r2, width=40, height=36, bg=T.BG_FIELD,
                        highlightthickness=0)
        ic2.pack(side="left")
        draw_icon(ic2, "rings", 20, 18, 22, T.GREEN)
        tk.Label(r2, text="音频到触觉", bg=T.BG_FIELD, fg=T.TEXT,
                 font=T.FONT_BOLD).pack(side="left", padx=(8, 0))
        self.tgl_master_blk = ToggleSwitch(
            r2, initial=self.config_data.get("vibration_on", True),
            command=self._set_vibration)
        self.tgl_master_blk.pack(side="right")
        _lbl(blk2, "通过系统声音驱动的触觉反馈感受声音——当前游戏支持时,"
                   "游戏内触觉反馈功能将自动接管。", fg=T.TEXT_FAINT,
             wraplength=380, justify="left").pack(fill="x", padx=12, pady=(4, 0))
        _lbl(blk2, "了解更多 ↗", fg=T.GREEN, font=T.FONT_LINK).pack(
            anchor="e", padx=12)
        self.sl_gain_blk = RazerSlider(blk2, "强度",
                                       from_=0.05, to=1.5,
                                       initial=self.config_data.get("gain", 0.67),
                                       command=self._on_gain, width=420)
        self.sl_gain_blk.pack(fill="x", padx=12, pady=(6, 0))

        # ---- 右卡:检测到的设备 ----
        right = Card(grid, title="检测到的设备", green_title=True, help_tip=True)
        right.grid(row=0, column=1, sticky="nsew")
        b = right.body
        _lbl(b, "调整每个设备的振动强度。", fg=T.TEXT_DIM).pack(
            fill="x", pady=(2, 10))

        dev = tk.Frame(b, bg=T.BG_FIELD, highlightbackground=T.BORDER,
                       highlightthickness=1)
        dev.pack(fill="x", ipadx=12, ipady=12)
        devrow = tk.Frame(dev, bg=T.BG_FIELD)
        devrow.pack(fill="x", padx=12)
        icd = tk.Canvas(devrow, width=34, height=26, bg=T.BG_FIELD,
                        highlightthickness=0)
        icd.pack(side="left")
        draw_icon(icd, "gamepad", 17, 13, 15, T.TEXT)
        self.dev_lbl = tk.Label(devrow, text="检测中…", bg=T.BG_FIELD,
                                fg=T.TEXT, font=T.FONT)
        self.dev_lbl.pack(side="left", padx=(8, 0))
        self.tgl_device = ToggleSwitch(
            devrow, initial=self.config_data.get("vibration_on", True),
            command=self._set_vibration)
        self.tgl_device.pack(side="right")
        self.sl_gain_dev = RazerSlider(dev, "振动强度",
                                       from_=0.05, to=1.5,
                                       initial=self.config_data.get("gain", 0.67),
                                       command=self._on_gain, width=380)
        self.sl_gain_dev.pack(fill="x", padx=12, pady=(8, 4))
        self.chk_a2h = CheckBox(dev, "音频到触觉(此设备)",
                                initial=self.config_data.get("vibration_on", True),
                                command=self._set_vibration)
        self.chk_a2h.pack(anchor="w", padx=12, pady=(2, 0))

    # ---------- 可滚动页面容器 ----------
    def _make_scroll_page(self, parent):
        """Canvas 滚动容器:内容高于可视区时出滚动条;矮时把内容拉高到铺满,
        让 expand 的子控件(频段画布)能吃掉多余空间。"""
        outer = tk.Frame(parent, bg=T.BG)
        outer.pack(fill="both", expand=True)
        canvas = tk.Canvas(outer, bg=T.BG, bd=0, highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(canvas, bg=T.BG)
        self._prof_canvas = canvas
        self._prof_inner = inner
        self._prof_win = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", self._prof_on_canvas_configure)
        # 滚轮全局接管,按指针位置判断是否落在本页(子控件上 Enter/Leave 会误触发)
        self.bind_all("<MouseWheel>", self._prof_mousewheel)
        return inner

    def _prof_mousewheel(self, e):
        w = self.winfo_containing(e.x_root, e.y_root)
        while w is not None:
            if w is self._prof_canvas:
                self._prof_canvas.yview_scroll(int(-e.delta / 120), "units")
                return
            w = getattr(w, "master", None)

    def _prof_on_canvas_configure(self, e):
        if e.width > 1:
            self._prof_canvas.itemconfigure(self._prof_win, width=e.width)
        self._prof_stretch()

    def _prof_stretch(self):
        """内容自然高度 < 可视高度时,把内容撑到可视高度(否则不滚动)。"""
        canvas = self._prof_canvas
        view_h = canvas.winfo_height()
        if view_h <= 1:
            return
        natural = self._prof_inner.winfo_reqheight()
        target = max(natural, view_h)
        if canvas.winfo_ismapped():
            canvas.itemconfigure(self._prof_win, height=target)

    # ---------- 页签 2:音频到触觉配置文件 ----------
    def _build_tab_profiles(self, p):
        # 可滚动页面:窗口矮时内容可滚到,不再把"频段增益"编辑器裁出窗外
        page = self._make_scroll_page(p)
        top = tk.Frame(page, bg=T.BG)
        top.pack(fill="x")
        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=2)

        # ---- 左卡:预设列表 ----
        left = Card(top, title="音频到触觉配置文件", green_title=True,
                    help_tip=True)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        b = left.body
        _lbl(b, "使用预设或自定义预设,选择 HapticX 触觉反馈技术如何将音频"
                "转换为触觉反馈。", fg=T.TEXT_DIM, wraplength=260,
             justify="left").pack(fill="x", pady=(2, 8))
        self.preset_list = PresetList(
            b,
            [("controlled", "sliders_v", "受控"),
             ("balanced", "wave", "均衡"),
             ("dynamic", "spiral", "动态"),
             ("custom", "sliders_h", "自订")],
            current=self.config_data.get("mode", "balanced"),
            command=self._on_mode, width=240)
        self.preset_list.pack(anchor="w")
        self.preset_info = tk.Frame(b, bg=T.BG_FIELD,
                                    highlightbackground=T.BORDER,
                                    highlightthickness=1)
        self.preset_info.pack(fill="x", pady=(8, 6), ipadx=10, ipady=8)
        self.info_title = tk.Label(self.preset_info, text="", bg=T.BG_FIELD,
                                   fg=T.TEXT, font=T.FONT_BOLD, anchor="w")
        self.info_title.pack(fill="x", padx=10, pady=(2, 0))
        self.info_desc = tk.Label(self.preset_info, text="", bg=T.BG_FIELD,
                                  fg=T.TEXT_DIM, font=T.FONT_SMALL,
                                  wraplength=250, justify="left", anchor="w")
        self.info_desc.pack(fill="x", padx=10, pady=(2, 4))
        btn_custom = tk.Canvas(b, width=110, height=32, bg=T.BG_CARD,
                               highlightthickness=1,
                               highlightbackground=T.BORDER, cursor="hand2")
        btn_custom.pack(anchor="w")
        btn_custom.create_text(55, 16, text="自 定 义", fill=T.TEXT,
                               font=T.FONT_BOLD, tags="bt")
        btn_custom.bind("<Button-1>", lambda e: self._on_mode("custom"))

        # ---- 右卡:音频与输出 ----
        right = Card(top, title="音频与输出", green_title=True, help_tip=True)
        right.grid(row=0, column=1, sticky="nsew")
        b = right.body
        row = tk.Frame(b, bg=T.BG_CARD)
        row.pack(fill="x", pady=(2, 6))
        _lbl(row, "音频输入设备", fg=T.TEXT_DIM, font=T.FONT).pack(side="left")
        self.audio_combo = ttk.Combobox(row, width=42, state="readonly")
        self.audio_combo.pack(side="left", padx=(16, 0))
        self.audio_combo.bind("<<ComboboxSelected>>", self._on_audio_device)
        self.sl_gain_prof = RazerSlider(b, "输出强度",
                                        from_=0.05, to=1.5,
                                        initial=self.config_data.get("gain", 0.67),
                                        command=self._on_gain, width=430,
                                        show_value=True)
        self.sl_gain_prof.pack(fill="x", pady=(4, 2))
        motors = tk.Frame(b, bg=T.BG_CARD)
        motors.pack(fill="x", pady=(6, 0))
        self.bar_left = LevelBar(motors, "左马达(低频)", width=280)
        self.bar_left.pack(side="left", padx=(0, 20))
        self.bar_right = LevelBar(motors, "右马达(高频·节拍)", width=280,
                                  color=T.BLUE)
        self.bar_right.pack(side="left")

        # ---- 编辑器卡:Sensa HD 设备频段增益 ----
        editor = Card(page, title="Sensa HD 设备 — 频段增益", green_title=True,
                      help_tip=True)
        editor.pack(fill="both", expand=True, pady=(12, 0))
        b = editor.body
        head = tk.Frame(b, bg=T.BG_CARD)
        head.pack(fill="x", pady=(0, 6))
        _lbl(head, "进行自定义时基于", fg=T.TEXT_DIM, font=T.FONT)\
            .pack(side="left")
        self.mode_box = ttk.Combobox(head, width=10, state="readonly",
                                     values=[T.MODE_NAMES[m] for m in MODE_ORDER])
        self.mode_box.current(MODE_ORDER.index(self.config_data.get("mode", "balanced")))
        self.mode_box.pack(side="left", padx=(10, 0))
        self.mode_box.bind("<<ComboboxSelected>>",
                           lambda e: self._on_mode(
                               MODE_ORDER[self.mode_box.current()]))
        btn_reset = tk.Canvas(head, width=70, height=26, bg=T.BG_CARD,
                              highlightthickness=1,
                              highlightbackground=T.BORDER, cursor="hand2")
        btn_reset.pack(side="right")
        btn_reset.create_text(35, 13, text="重 置", fill=T.TEXT, font=T.FONT)
        btn_reset.bind("<Button-1>", lambda e: self._reset_band_gains())

        mode0 = self.config_data.get("mode", "balanced")
        self.band_canvas = BandGainCanvas(
            b, width=880, height=240,
            band_gains=band_gains_for(self.config_data, mode0),
            band_edges=band_edges_for(self.config_data, mode0),
            band_colors=T.BAND_COLORS,
            command=self._on_band_gains,
            edge_command=self._on_band_edges)
        # fill+expand:窗口拉大时频段编辑器跟着变大(Canvas 已支持自适应重绘)
        self.band_canvas.pack(fill="both", expand=True, anchor="w")

        # 每频段参数行:最小值/最大值(可调,内外边界共享)+ 增益水平%
        spins = tk.Frame(b, bg=T.BG_CARD)
        spins.pack(fill="x", pady=(10, 0))
        self.gain_vars = []
        self.gain_spins = []
        self.edge_vars = {}   # (band, "lo"/"hi") -> StringVar
        for i in range(len(BAND_LABELS)):
            cell = tk.Frame(spins, bg=T.BG_FIELD,
                            highlightbackground=T.BORDER, highlightthickness=1)
            cell.pack(side="left", padx=(0, 12), ipadx=10, ipady=8)
            head2 = tk.Frame(cell, bg=T.BG_FIELD)
            head2.pack(fill="x", padx=8)
            dot = tk.Canvas(head2, width=12, height=12, bg=T.BG_FIELD,
                            highlightthickness=0)
            dot.pack(side="left")
            dot.create_oval(2, 2, 10, 10, fill=T.BAND_COLORS[i], outline="")
            tk.Label(head2, text="音频提示", bg=T.BG_FIELD, fg=T.TEXT,
                     font=T.FONT_SMALL).pack(side="left", padx=(5, 0))
            _lbl(head2, BAND_LABELS[i], fg=T.TEXT_FAINT).pack(
                side="left", padx=(6, 0))

            grid2 = tk.Frame(cell, bg=T.BG_FIELD)
            grid2.pack(fill="x", padx=8, pady=(4, 0))
            _lbl(grid2, "音频输入范围", fg=T.TEXT_DIM).grid(
                row=0, column=0, columnspan=4, sticky="w")
            _lbl(grid2, "最小值 (Hz)", fg=T.TEXT_FAINT).grid(row=1, column=0,
                                                            sticky="w", pady=(2, 0))
            # 首频段下界(30Hz)与末频段上界(200Hz)是触觉范围,固定只读
            lo_fixed = (i == 0)
            lo_v = tk.StringVar(value="30")
            lo = tk.Spinbox(grid2, from_=30, to=200, increment=5, width=6,
                            textvariable=lo_v, bg=T.BG_INPUT,
                            fg=T.TEXT if not lo_fixed else T.TEXT_FAINT,
                            relief="flat", buttonbackground=T.BG_FIELD,
                            insertbackground=T.TEXT,
                            state="disabled" if lo_fixed else "normal",
                            disabledbackground=T.BG_INPUT,
                            disabledforeground=T.TEXT_FAINT,
                            command=lambda i=i: self._on_edge_spin(i, "lo"))
            lo.grid(row=2, column=0, pady=(1, 0))
            if not lo_fixed:
                lo.bind("<Return>", lambda e, i=i: self._on_edge_spin(i, "lo"))
                lo.bind("<FocusOut>", lambda e, i=i: self._on_edge_spin(i, "lo"))
            self.edge_vars[(i, "lo")] = lo_v
            _lbl(grid2, "最大值 (Hz)", fg=T.TEXT_FAINT).grid(row=1, column=1,
                                                            sticky="w",
                                                            padx=(10, 0),
                                                            pady=(2, 0))
            hi_fixed = (i == len(BAND_LABELS) - 1)
            hi_v = tk.StringVar(value="200")
            hi = tk.Spinbox(grid2, from_=30, to=200, increment=5, width=6,
                            textvariable=hi_v, bg=T.BG_INPUT,
                            fg=T.TEXT if not hi_fixed else T.TEXT_FAINT,
                            relief="flat", buttonbackground=T.BG_FIELD,
                            insertbackground=T.TEXT,
                            state="disabled" if hi_fixed else "normal",
                            disabledbackground=T.BG_INPUT,
                            disabledforeground=T.TEXT_FAINT,
                            command=lambda i=i: self._on_edge_spin(i, "hi"))
            hi.grid(row=2, column=1, sticky="w", padx=(10, 0), pady=(1, 0))
            if not hi_fixed:
                hi.bind("<Return>", lambda e, i=i: self._on_edge_spin(i, "hi"))
                hi.bind("<FocusOut>", lambda e, i=i: self._on_edge_spin(i, "hi"))
            self.edge_vars[(i, "hi")] = hi_v
            _lbl(grid2, "增益水平 (%)", fg=T.TEXT_DIM).grid(row=1, column=2,
                                                           sticky="w",
                                                           padx=(16, 0),
                                                           pady=(2, 0))
            var = tk.StringVar(value="0")
            spin = tk.Spinbox(grid2, from_=0, to=200, increment=5, width=6,
                              textvariable=var, bg=T.BG_INPUT, fg=T.TEXT,
                              relief="flat", buttonbackground=T.BG_FIELD,
                              insertbackground=T.TEXT,
                              command=lambda i=i: self._on_spin(i))
            spin.grid(row=2, column=2, sticky="w", padx=(16, 0), pady=(1, 0))
            spin.bind("<Return>", lambda e, i=i: self._on_spin(i))
            spin.bind("<FocusOut>", lambda e, i=i: self._on_spin(i))
            self.gain_vars.append(var)
            self.gain_spins.append(spin)
            self._sync_spin(i)
            self._sync_edge_spin(i, "lo")
            self._sync_edge_spin(i, "hi")

        _lbl(b, "提示:上下拖「≡」调增益;左右拖频段分隔线(或在最小/最大值框输入)"
                "调音频输入范围;柱状图为实时系统声音。",
             fg=T.TEXT_FAINT).pack(anchor="w", pady=(8, 0))

    # ---------- 仪表板 ----------
    def _build_page_dashboard(self):
        p = self.pages["dashboard"]
        card = Card(p, title="设备概览", subtitle="连接与运行状态")
        card.pack(fill="x")
        row = tk.Frame(card.body, bg=T.BG_CARD)
        row.pack(fill="x")
        self.dash_dot = StatusDot(row, state="off")
        self.dash_dot.pack(side="left")
        self.dash_devname = tk.Label(row, text="检测中…", bg=T.BG_CARD,
                                     fg=T.TEXT, font=T.FONT_H1)
        self.dash_devname.pack(side="left", padx=10)

        grid = tk.Frame(card.body, bg=T.BG_CARD)
        grid.pack(fill="x", pady=(10, 0))
        self.dash_labels = {}
        for i, (key, label) in enumerate((
                ("connection", "连接状态"), ("mode", "当前模式"),
                ("gain", "输出强度"), ("beats", "节拍累计"),
                ("audio", "音频源"), ("runtime", "振动状态"))):
            cell = tk.Frame(grid, bg=T.BG_FIELD, highlightbackground=T.BORDER,
                            highlightthickness=1)
            cell.grid(row=i // 3, column=i % 3, sticky="nsew", padx=4, pady=4)
            grid.columnconfigure(i % 3, weight=1)
            tk.Label(cell, text=label, bg=T.BG_FIELD, fg=T.TEXT_DIM,
                     font=T.FONT_SMALL).pack(anchor="w", padx=10, pady=(8, 0))
            val = tk.Label(cell, text="--", bg=T.BG_FIELD, fg=T.TEXT,
                           font=T.FONT_BOLD)
            val.pack(anchor="w", padx=10, pady=(0, 8))
            self.dash_labels[key] = val

        spec = Card(p, title="实时频谱", subtitle="30-130Hz 触觉频段高亮")
        spec.pack(fill="x", pady=(14, 0))
        self.spectrum = SpectrumCanvas(spec.body, width=720, height=180)
        self.spectrum.pack(fill="x")

    # ---------- 设备 ----------
    def _build_page_devices(self):
        p = self.pages["devices"]
        card = Card(p, title="雷云侦察情报", subtitle="从雷云4日志提取")
        card.pack(fill="both", expand=True)
        text = tk.Text(card.body, bg=T.BG_FIELD, fg=T.TEXT_DIM,
                       font=("Consolas", 9), relief="flat",
                       highlightthickness=1, highlightbackground=T.BORDER,
                       wrap="none")
        from tkinter import ttk as _ttk
        scroll = _ttk.Scrollbar(card.body, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        text.insert("1.0", format_summary(self.probe_info))
        text.configure(state="disabled")

    # ---------- 设置 ----------
    def _build_page_settings(self):
        p = self.pages["settings"]
        card = Card(p, title="自订模式参数", subtitle="仅自订模式生效")
        card.pack(fill="x")
        self.custom_sliders = {}
        overrides = self.config_data.get("custom_overrides", {})
        for key, (label, from_, to, _fmt) in {
            "gate": ("静音门限", 0.01, 0.15, None),
            "band_scale": ("频段缩放", 0.2, 1.2, None),
            "gamma": ("压缩器 gamma", 1.0, 6.0, None),
            "transient_vol": ("瞬态脉冲强度", 0.0, 1.0, None),
            "freq_win": ("频率窗 (s)", 0.03, 0.3, None),
            "amp_win": ("振幅窗 (s)", 0.01, 0.12, None),
        }.items():
            row = tk.Frame(card.body, bg=T.BG_CARD)
            row.pack(fill="x", pady=3)
            slider = RazerSlider(row, label, from_=from_, to=to,
                                 initial=float(overrides.get(key, 0.5)),
                                 command=lambda v, k=key: self._on_custom(k, v),
                                 width=420, show_value=True, fmt="{:.3f}")
            slider.pack(side="left")
            self.custom_sliders[key] = slider

        card2 = Card(p, title="通用")
        card2.pack(fill="x", pady=(14, 0))
        row = tk.Frame(card2.body, bg=T.BG_CARD)
        row.pack(fill="x")
        tk.Label(row, text="手柄 XInput 序号", bg=T.BG_CARD, fg=T.TEXT_DIM,
                 font=T.FONT).pack(side="left")
        self.user_spin = tk.Spinbox(row, from_=0, to=3, width=4,
                                    bg=T.BG_INPUT, fg=T.TEXT, relief="flat",
                                    buttonbackground=T.BG_CARD,
                                    insertbackground=T.TEXT,
                                    textvariable=tk.StringVar(
                                        value=str(self.config_data.get("user_index", 0))))
        self.user_spin.pack(side="left", padx=10)
        btn = tk.Canvas(row, width=110, height=32, bg=T.GREEN_DIM,
                        highlightthickness=0, cursor="hand2")
        btn.pack(side="right")
        btn.create_text(55, 16, text="保存配置", fill=T.GREEN_TEXT,
                        font=T.FONT_BOLD)
        btn.bind("<Button-1>", lambda e: self._save())

    # ==================== 状态栏 ====================
    def _build_statusbar(self):
        bar = tk.Frame(self, bg=T.BG_CARD, height=30)
        bar.pack(side="bottom", fill="x")
        self.status_lbl = tk.Label(bar, text="就绪", bg=T.BG_CARD,
                                   fg=T.TEXT_DIM, font=T.FONT_SMALL, anchor="w")
        self.status_lbl.pack(side="left", padx=14)
        self.conn_lbl = tk.Label(bar, text="", bg=T.BG_CARD, fg=T.TEXT_DIM,
                                 font=T.FONT_SMALL)
        self.conn_lbl.pack(side="right", padx=14)

    # ==================== 事件与同步 ====================
    def _startup(self):
        dev = self.probe_info.get("device", {})
        name = dev.get("productName", "通用 XInput 手柄")
        self.dev_lbl.configure(text=name)
        self.dash_devname.configure(text=name)
        if self.probe_info.get("process"):
            self.status_lbl.configure(
                text=f"[!] 检测到雷云({self.probe_info['process']})在运行 — "
                     f"若振动异常请在雷云中关闭 SENSA 动态触觉", fg=T.AMBER)
        self.audio_combo.set(self.config_data.get("audio_device") or
                             (self.audio_combo["values"][0]
                              if self.audio_combo["values"] else ""))
        self.src_lbl.configure(
            text=f"正在捕获:{self.config_data.get('audio_device') or '系统默认输出'}")
        self.pipeline.start(self.config_data.get("audio_device"))
        self._sync_mode_info()

    def _load_audio_devices(self):
        try:
            devices = [name for name, _ in list_output_devices()]
        except Exception:  # noqa: BLE001
            devices = []
        self.audio_combo["values"] = devices

    # 振动总开关:三处控件双向同步
    def _set_vibration(self, on):
        self.tgl_master_blk.set(on)
        self.tgl_device.set(on)
        self.chk_a2h.set(on)
        self.pipeline.set_vibration(on)
        self.config_data["vibration_on"] = on

    # 强度:三处滑条双向同步
    def _on_gain(self, val):
        self.sl_gain_blk.set(val)
        self.sl_gain_dev.set(val)
        self.sl_gain_prof.set(val)
        self.pipeline.set_gain(val)
        self.config_data["gain"] = round(val, 3)

    def _on_mode(self, mode):
        if mode not in MODE_ORDER:
            return
        self.pipeline.set_mode(mode)
        gains = band_gains_for(self.config_data, mode)
        edges = band_edges_for(self.config_data, mode)
        self.pipeline.set_band_gains(gains)
        self.band_canvas.set_gains(gains)
        self.band_canvas.set_band_edges(edges)
        self.config_data["mode"] = mode
        # 同步三处模式选择控件
        self.preset_list.select(mode, notify=False)
        self.mode_box.current(MODE_ORDER.index(mode))
        self._sync_mode_info()
        for i in range(len(BAND_LABELS)):
            self._sync_spin(i)
        self._sync_edge_spins()

    def _sync_mode_info(self):
        mode = self.config_data.get("mode", "balanced")
        self.info_title.configure(text=f"基于:{T.MODE_NAMES[mode]}预设。")
        self.info_desc.configure(text=T.MODE_DESC.get(mode, ""))

    def _on_custom(self, key, val):
        self.pipeline.set_custom_overrides({key: round(val, 4)})

    def _on_band_gains(self, gains):
        mode = self.config_data.get("mode", "balanced")
        self.config_data.setdefault("mode_band_gains", {})[mode] = \
            [round(g, 2) for g in gains]
        self.pipeline.set_band_gains(gains)
        for i in range(len(BAND_LABELS)):
            self._sync_spin(i)

    def _on_band_edges(self, edges):
        """画布上拖频段边界 → 记配置 + 更新管线 + 同步数值框。"""
        mode = self.config_data.get("mode", "balanced")
        self.config_data.setdefault("mode_band_edges", {})[mode] = \
            [round(e, 1) for e in edges]
        self.pipeline.set_band_edges(edges)
        self._sync_edge_spins()

    def _on_edge_spin(self, i, which):
        """最小值/最大值框调整 → 夹紧到合法区间 + 全链路同步。"""
        mode = self.config_data.get("mode", "balanced")
        edges = list(band_edges_for(self.config_data, mode))
        j = i if which == "lo" else i + 1
        if j <= 0 or j >= len(edges) - 1:
            return  # 外边界固定
        try:
            val = float(self.edge_vars[(i, which)].get())
        except (ValueError, tk.TclError):
            return
        lo = max(30.0, edges[j - 1] + 10.0)
        hi = min(200.0, edges[j + 1] - 10.0)
        edges[j] = min(hi, max(lo, val))
        self.config_data.setdefault("mode_band_edges", {})[mode] = \
            [round(e, 1) for e in edges]
        self.pipeline.set_band_edges(edges)
        self.band_canvas.set_band_edges(edges)
        self._sync_edge_spins()

    def _sync_edge_spin(self, i, which):
        mode = self.config_data.get("mode", "balanced")
        edges = band_edges_for(self.config_data, mode)
        self.edge_vars[(i, which)].set(f"{edges[i if which == 'lo' else i + 1]:.0f}")

    def _sync_edge_spins(self):
        for i in range(len(BAND_LABELS)):
            self._sync_edge_spin(i, "lo")
            self._sync_edge_spin(i, "hi")

    def _on_spin(self, i):
        mode = self.config_data.get("mode", "balanced")
        try:
            pct = float(self.gain_vars[i].get())
        except (ValueError, tk.TclError):
            return
        pct = min(200.0, max(0.0, pct))
        gains = band_gains_for(self.config_data, mode)
        gains = list(gains)
        gains[i] = pct / 100.0
        self.config_data.setdefault("mode_band_gains", {})[mode] = \
            [round(g, 2) for g in gains]
        self.pipeline.set_band_gains(gains)
        self.band_canvas.set_gains(gains)
        self._sync_spin(i)

    def _sync_spin(self, i):
        mode = self.config_data.get("mode", "balanced")
        gains = band_gains_for(self.config_data, mode)
        self.gain_vars[i].set(f"{gains[i] * 100:.0f}")

    def _reset_band_gains(self):
        mode = self.config_data.get("mode", "balanced")
        self.config_data.get("mode_band_gains", {}).pop(mode, None)
        self.config_data.get("mode_band_edges", {}).pop(mode, None)
        gains = band_gains_for(self.config_data, mode)
        edges = band_edges_for(self.config_data, mode)
        self.pipeline.set_band_gains(gains)
        self.pipeline.set_band_edges(edges)
        self.band_canvas.set_gains(gains)
        self.band_canvas.set_band_edges(edges)
        for i in range(len(BAND_LABELS)):
            self._sync_spin(i)
        self._sync_edge_spins()
        self.status_lbl.configure(
            text=f"{T.MODE_NAMES[mode]} 频段增益/范围已重置为预设", fg=T.GREEN)

    def _on_audio_device(self, event=None):
        name = self.audio_combo.get()
        if name and name != self.pipeline.state.get("audio_device"):
            self.config_data["audio_device"] = name
            self.src_lbl.configure(text=f"正在捕获:{name}")
            self.pipeline.restart_capture(name)

    def _save(self):
        try:
            self.config_data["user_index"] = int(self.user_spin.get())
        except ValueError:
            pass
        if save(self.config_data):
            self.status_lbl.configure(text="配置已保存", fg=T.GREEN)
        else:
            self.status_lbl.configure(text="配置保存失败", fg=T.RED)

    # ==================== 刷新循环 ====================
    def _refresh(self):
        state = self.pipeline.snapshot()

        connected = state["connected"] and state["running"]
        self.conn_lbl.configure(
            text=f"XInput {'已连接' if state['connected'] else '未连接'} · "
                 f"捕获 {'运行' if state['running'] else '停止'}",
            fg=T.GREEN_TEXT if connected else T.AMBER)

        # 频段编辑器背景谱(仅 profiles 页可见时更新)
        if self.current_page == "haptics" and self.haptic_tab == "profiles":
            self.band_canvas.update_spectrum(state["viz"])
            self.bar_left.set(state["left"])
            self.bar_right.set(state["right"])

        # 仪表板频谱
        if self.current_page == "dashboard":
            in_band = [30.0 <= 20.0 * (8000.0 / 20.0) ** (i / 15.0) <= 130.0
                       for i in range(16)]
            self.spectrum.update_data(state["viz"], in_band,
                                      state["left"], state["right"],
                                      state["beat"])

        # 仪表板数据
        if self.current_page == "dashboard":
            self.dash_dot.set("ok" if state["connected"] else "err")
            vals = {
                "connection": "已连接" if state["connected"] else "未连接",
                "mode": T.MODE_NAMES.get(state["mode"], state["mode"]),
                "gain": f"{state['gain']:.2f}",
                "beats": str(state["beats"]),
                "audio": state.get("audio_device") or "--",
                "runtime": "振动开启" if state["vibration_on"] else "振动关闭",
            }
            for key, val in vals.items():
                self.dash_labels[key].configure(text=val)

        # 默认输出设备热切换检测(2s 一次)
        now = self._now_ms()
        if state["running"] and now - self._last_device_poll > 2000:
            self._last_device_poll = now
            self._poll_default_device()
        self.after(33, self._refresh)

    @staticmethod
    def _now_ms():
        import time
        return time.time() * 1000

    def _poll_default_device(self):
        try:
            import soundcard as sc
            current = sc.default_speaker().name
        except Exception:  # noqa: BLE001
            return
        using_default = not self.config_data.get("audio_device")
        if using_default and current != self.pipeline.state.get("audio_device"):
            self.pipeline.restart_capture(None)
            self.status_lbl.configure(text=f"输出设备已切换:{current}", fg=T.AMBER)

    def _on_close(self):
        try:
            self.pipeline.shutdown()
        finally:
            self._save()
            self.destroy()


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
