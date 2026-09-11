"""theme.py — 雷云 Synapse(SENSA HD)风格深色主题。

色板取自官方截图:近黑页面背景 + 浅一档卡片 + 雷蛇绿点缀。
"""

BG = "#101113"           # 页面背景
BG_TOP = "#0a0b0c"       # 顶部模块栏
BG_CARD = "#1a1c1f"      # 卡片
BG_CARD_HOVER = "#212428"
BG_FIELD = "#131518"     # 卡片内嵌块
BG_INPUT = "#0d0e10"     # 输入框/图表底
BORDER = "#2a2e33"
BORDER_LIGHT = "#3a4046"

TEXT = "#e6e6e6"
TEXT_DIM = "#8f979e"
TEXT_FAINT = "#5f676e"

GREEN = "#44d62c"        # 雷蛇绿
GREEN_DIM = "#1f3d17"
GREEN_TEXT = "#9fe58f"
PILL_FG = "#0b120a"      # 胶囊选中态上的深色文字
BLUE = "#29c7d6"         # Sensa HD 青
VIOLET = "#8a9bf0"       # 第三频段紫

AMBER = "#e8b64c"
RED = "#e8544c"

BAND_COLORS = [GREEN, BLUE, VIOLET]

FONT = ("Microsoft YaHei UI", 10)
FONT_BOLD = ("Microsoft YaHei UI", 10, "bold")
FONT_SMALL = ("Microsoft YaHei UI", 9)
FONT_SMALL_DIM = ("Microsoft YaHei UI", 9)
FONT_LINK = ("Microsoft YaHei UI", 9, "underline")
FONT_TITLE = ("Microsoft YaHei UI", 15, "bold")
FONT_LOGO = ("Microsoft YaHei UI", 16, "bold")
FONT_H1 = ("Microsoft YaHei UI", 12, "bold")

SIDEBAR_W = 190
CARD_PAD = 14
RADIUS = 10

MODE_NAMES = {
    "controlled": "受控",
    "balanced": "均衡",
    "dynamic": "动态",
    "custom": "自订",
}
MODE_DESC = {
    "controlled": "振动克制,仅强低音触发,响应平缓。",
    "balanced": "雷云默认配方,全频段平滑跟随。",
    "dynamic": "响应灵敏的配置文件,可最大限度地增强沉浸感和空间感。"
               "充满动作情节的事件会让人感觉更加生动和真实。",
    "custom": "自定义频段门限/增益/瞬态参数。",
}
