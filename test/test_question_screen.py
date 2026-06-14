"""测试 QuestionScreen。"""
from __future__ import annotations

from src.tui.screens.question_screen import QuestionScreen


def test_question_screen_stores_question_and_meta():
    """QuestionScreen 应保存问题和元数据。"""
    screen = QuestionScreen("Which color?", {"options": ["red", "blue"]})

    assert screen.question == "Which color?"
    assert screen.meta["options"] == ["red", "blue"]
