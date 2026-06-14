"""CamelCode 入口 —— 启动 TUI 模式。

Usage:
    python main.py
"""
from __future__ import annotations

import os

from src.agents.lead_agent import LeadAgent
from src.tui import CamelTUIApp


def main() -> None:
    """启动 CamelCode TUI。"""
    lead_agent = LeadAgent()
    app = CamelTUIApp(agent=lead_agent, cwd=os.getcwd())
    app.run()


if __name__ == "__main__":
    main()
