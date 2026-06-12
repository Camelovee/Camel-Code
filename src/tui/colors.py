"""TUI 配色常量 —— 沙漠骆驼主题。

所有颜色统一在此定义，供 theme.css 和 transcript 等代码共用。
"""
from __future__ import annotations

# ── 基础色板 ──────────────────────────────────────────────────
BACKGROUND = "#1A1410"      # 主背景
FOREGROUND = "#E8DCC8"      # 主文字
PANEL_BG = "#2D2418"        # 面板背景
BORDER = "#4A3F30"          # 边框/分隔线
INPUT_BG = "#3D3220"        # 输入框背景
INPUT_BORDER = "#5A5040"    # 输入框边框

# ── 强调色 ─────────────────────────────────────────────────────
GOLD = "#D4A843"            # 金色（Logo、prompt、user-label）
CAMEL = "#C19A6B"           # 骆驼棕（assistant-label、model名）
BLUE_GRAY = "#8B9DC3"       # 蓝灰（tool-label）
MUTED = "#A89878"           # 柔和色（version、hint、compression-info）

# ── 状态色 ─────────────────────────────────────────────────────
SUCCESS = "#6B9B6B"         # 成功/就绪
WARNING = "#CD853F"         # 警告/忙碌
ERROR = "#C45B4A"           # 错误/危险
