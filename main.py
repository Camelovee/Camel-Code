"""CamelCode 入口 —— CLI 模式。

Usage:
    python main.py
"""
from __future__ import annotations

import os

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agents.lead_agent import LeadAgent
from src.prompts import getSystemPrompt


def _run_cli() -> None:
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


if __name__ == "__main__":
    _run_cli()
