"""CamelCode 入口 —— 支持 CLI 和 TUI 两种模式。

Usage:
    python main.py        # 启动 TUI 模式
    python main.py --cli  # 启动 CLI 模式
"""
from __future__ import annotations

import argparse
import os

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agents.lead_agent import LeadAgent
from src.prompts import getSystemPrompt


def _run_cli() -> None:
    """纯 CLI 模式。"""
    print("\033[93m" + r"""
      ╭───╮ ╭───╮
      │ ■ │ │ ■ │   Camel Code
      ╰─┬─╯ ╰─┬─╯
     __/       \__
    /  o       o  \
   │      ___      │
    \_____________/
      ││       ││
""" + "\033[0m")
    print("输入问题，回车发送。输入 q 退出。\n")

    lead_agent = LeadAgent()
    history: list = []
    history.append(SystemMessage(content=getSystemPrompt(os.getcwd())))

    while True:
        try:
            query = input("\033[36ms01 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break

        history.append(HumanMessage(content=query))
        lead_agent.run_agent_turn(history)
        last_msg = history[-1]
        response_content = getattr(last_msg, "content", "")
        if isinstance(response_content, list):
            for block in response_content:
                block_type = block.get("type")
                if block_type == "thinking":
                    print(f"\n\033[90m[Thinking]\033[0m")
                    print(block.get("thinking"))
                elif block_type == "text":
                    text = block.get("text")
                    print(f"\n\033[92m[Text]\033[0m")
                    print(text)
        elif isinstance(response_content, str):
            print(response_content)

        print()


def _run_tui() -> None:
    """TUI 模式。"""
    from src.tui import CamelTUIApp

    lead_agent = LeadAgent()
    app = CamelTUIApp(agent=lead_agent, cwd=os.getcwd())
    app.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CamelCode - AI 编码助手")
    parser.add_argument("--cli", action="store_true", help="使用 CLI 模式（默认 TUI）")
    args = parser.parse_args()

    if args.cli:
        _run_cli()
    else:
        _run_tui()
