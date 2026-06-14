"""向用户提问的模态弹窗。"""
from __future__ import annotations

import json

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Markdown, RadioSet, SelectionList


class QuestionScreen(ModalScreen[str | None]):
    """询问用户问题并返回答案。取消时返回 None。"""

    CSS_PATH = "css/question_screen.css"

    def __init__(self, question: str, meta: dict | None = None) -> None:
        super().__init__()
        self.question = question
        self.meta = meta or {}
        self.options: list[str] | None = self.meta.get("options")
        self.allow_multiple: bool = self.meta.get("allow_multiple", False)
        self.allow_cancel: bool = self.meta.get("allow_cancel", True)

    def compose(self) -> ComposeResult:
        """组装弹窗界面。"""
        yield Vertical(
            Markdown(self.question, id="question-markdown"),
            self._build_input_widget(),
            Horizontal(
                Button("确认", id="confirm", variant="primary"),
                Button("取消", id="cancel", variant="error") if self.allow_cancel else Label(""),
                id="button-row",
            ),
            id="question-dialog",
        )

    def _build_input_widget(self):
        """根据 meta 构建输入控件。"""
        if not self.options:
            return Input(placeholder="请输入你的回答...", id="answer-input")

        if self.allow_multiple:
            return SelectionList(*[(opt, opt) for opt in self.options], id="answer-selection")

        return RadioSet(*self.options, id="answer-radio")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """处理按钮点击。"""
        if event.button.id == "cancel":
            self.dismiss(None)
            return

        answer = self._collect_answer()
        self.dismiss(answer)

    def _collect_answer(self) -> str:
        """收集用户输入。"""
        if not self.options:
            input_widget = self.query_one("#answer-input", Input)
            return input_widget.value

        if self.allow_multiple:
            selection = self.query_one("#answer-selection", SelectionList)
            selected = [str(item) for item in selection.selected]
            return json.dumps(selected, ensure_ascii=False)

        radio = self.query_one("#answer-radio", RadioSet)
        return str(radio.pressed_button.label) if radio.pressed_button else ""
