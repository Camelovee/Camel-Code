from __future__ import annotations

import json

from langchain_core.tools import tool


@tool(
    description=(
        "Ask the user a clarifying question and pause the current turn until the user replies. "
        "Use this when you need clarification, need to choose between options, or need confirmation. "
        "Do not ask clarifying questions in plain assistant text."
    )
)
def ask_user(
    question: str,
    options: list[str] | None = None,
    allow_multiple: bool = False,
    allow_cancel: bool = True,
) -> str:
    """
    向用户提出澄清问题，并暂停当前轮次等待用户回复。

    Args:
        question: 要询问用户的问题
        options: 可选的选项列表，供用户选择
        allow_multiple: 是否允许用户选择多个选项
        allow_cancel: 是否允许用户取消/拒绝回答
    """
    result = {
        "ok": True,
        "output": question,
        "await_user": True,
        "meta": {
            "options": options,
            "allow_multiple": allow_multiple,
            "allow_cancel": allow_cancel,
        },
    }
    return json.dumps(result, ensure_ascii=False)
