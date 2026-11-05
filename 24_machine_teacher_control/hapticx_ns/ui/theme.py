"""theme.py — 机械师版配色：**版式照抄雷云 Synapse(SENSA HD)，点缀色从雷蛇绿换成机械师蓝**。

和 25 那份的唯一区别就是下面这几个色值 + 背景带一点冷色，
目的是桌面上两个窗口一眼分得清：绿 = 雷蛇 Sage T1，蓝 = 机械师 G6 V2(NS)。
标识符也跟着改了（GREEN→BLUE，原来的 Sensa 青 BLUE 让位成 CYAN），不留"名字叫绿、其实是蓝"的坑。
"""

BG = "#0f1116"           # 页面背景（比雷云版冷一档）
BG_TOP = "#0a0c11"       # 顶部模块栏
BG_CARD = "#191d25"      # 卡片
BG_CARD_HOVER = "#20252f"
BG_FIELD = "#13171e"     # 卡片内嵌块
BG_INPUT = "#0d1015"     # 输入框/图表底
BORDER = "#29313d"
BORDER_LIGHT = "#3a4454"

TEXT = "#e6e6e6"
TEXT_DIM = "#8f979e"
TEXT_FAINT = "#5f676e"

BLUE = "#2f7bff"         # 机械师蓝（雷云那版这里是雷蛇绿 #44d62c）
BLUE_DIM = "#13294d"
BLUE_TEXT = "#a8c8ff"
PILL_FG = "#0a1220"      # 胶囊选中态上的深色文字
CYAN = "#29c7d6"         # Sensa HD 青
VIOLET = "#8a9bf0"       # 第三频段紫

AMBER = "#e8b64c"
RED = "#e8544c"

BAND_COLORS = [BLUE, CYAN, VIOLET]

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
