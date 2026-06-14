"""CamelTUIApp —— Textual App 主类。

组装 Header、Transcript、InputBox、FooterBar，
协调 LeadAgent 执行与 UI 更新。
"""
from __future__ import annotations

from textual.app import App, ComposeResult
from textual.worker import Worker, WorkerState
from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.callbacks import AgentCallbacks
from src.agents.lead_agent import LeadAgent
from src.prompts import get_system_prompt
from src.tui.events import (
    AgentEvent,
    AssistantMessageEvent,
    CompressionEvent,
    ContextStatsEvent,
    ProgressMessageEvent,
    ToolResultEvent,
    ToolStartEvent,
)
from src.tui.colors import CAMEL, ERROR
from src.tui.widgets.footer import FooterBar
from src.tui.widgets.header import Header
from src.tui.widgets.input_box import InputBox
from src.tui.screens.question_screen import QuestionScreen
from src.tui.widgets.transcript import Transcript


class CamelTUIApp(App):
    """CamelCode TUI 应用。"""

    CSS_PATH = [
        "css/app.css",
        "css/header.css",
        "css/footer.css",
        "css/input_box.css",
        "css/transcript.css",
    ]
    BINDINGS = [
        ("ctrl+c", "quit", "退出"),
    ]

    def __init__(self, agent: LeadAgent, cwd: str) -> None:
        super().__init__()
        self._agent = agent
        self._cwd = cwd
        self._history: list = []
        self._is_busy: bool = False

    def compose(self) -> ComposeResult:
        """组装 UI。"""
        self._header = Header()
        self._header.set_model_name(self._agent.model_name)

        self._transcript = Transcript()
        self._input_box = InputBox()
        self._footer = FooterBar()
        self._footer.set_tools(list(self._agent.tools.keys()))

        yield self._header
        yield self._transcript
        yield self._input_box
        yield self._footer

    def on_mount(self) -> None:
        """挂载后初始化。"""
        # 添加 system prompt
        self._history.append(SystemMessage(content=get_system_prompt(self._cwd)))
        # 设置标题
        self.title = "CamelCode"
        self.sub_title = self._agent.model_name
        # 聚焦输入框
        self._input_box.focus_input()

    # ── 事件处理 ──────────────────────────────────────────────

    def on_input_box_submitted(self, event: InputBox.Submitted) -> None:
        """处理用户输入提交。"""
        if self._is_busy:
            self._footer.set_status("Agent 正在运行中...", busy=True)
            return

        value = event.value

        # 处理斜杠命令
        if value.startswith("/"):
            handled = self._handle_slash_command(value)
            if handled:
                return

        # 普通消息：添加到历史并启动 Agent
        self._transcript.add_user_message(value)
        self._history.append(HumanMessage(content=value))
        self._start_agent_turn()

    def _handle_slash_command(self, value: str) -> bool:
        """处理斜杠命令，返回是否已处理。"""
        parts = value.split()
        cmd = parts[0].lower()

        if cmd in ("/quit", "/exit"):
            self.exit()
            return True

        if cmd == "/help":
            help_text = (
                f"[{CAMEL} bold]可用命令[/]\n"
                "  /help      - 显示帮助\n"
                "  /tools     - 显示可用工具\n"
                "  /clear     - 清空对话历史\n"
                "  /snip      - 手动裁剪上下文\n"
                "  /compact   - 手动压缩上下文\n"
                "  /collapse  - 手动折叠上下文\n"
                "  /model     - 显示模型信息\n"
                "  /quit      - 退出"
            )
            self._transcript.write("")
            self._transcript.write(help_text)
            return True

        if cmd == "/tools":
            tools_text = "\n".join(
                f"  {name}: {tool.description}"
                for name, tool in self._agent.tools.items()
            )
            self._transcript.write("")
            self._transcript.write(f"[{CAMEL} bold]可用工具[/]\n{tools_text}")
            return True

        if cmd == "/clear":
            # 保留 system prompt，清空其余
            system = [m for m in self._history if isinstance(m, SystemMessage)]
            self._history = system
            self._transcript.clear()
            self._transcript.write("[dim]对话历史已清空[/]")
            return True

        if cmd == "/model":
            self._transcript.write("")
            self._transcript.write(
                f"[{CAMEL} bold]模型信息[/]\n"
                f"  模型: {self._agent.model_name}\n"
                f"  Provider: {self._agent.llm.__class__.__name__}"
            )
            return True

        if cmd in ("/snip", "/compact", "/collapse"):
            self._transcript.write("")
            self._transcript.write(
                f"[dim]{cmd} 命令需要上下文压缩管道支持，当前版本暂不支持手动触发[/]"
            )
            return True

        return False

    # ── Agent 执行 ─────────────────────────────────────────────

    def _make_callbacks(self) -> AgentCallbacks:
        """构造传递给 Agent 的回调集合。"""
        return AgentCallbacks(
            on_tool_start=self._on_tool_start,
            on_tool_result=self._on_tool_result,
            on_assistant_message=self._on_assistant_message,
            on_progress_message=self._on_progress_message,
            on_context_stats=self._on_context_stats,
            on_compression=self._on_compression,
        )

    def _start_agent_turn(self) -> None:
        """启动 Agent 回合（在后台 Worker 中执行）。"""
        self._is_busy = True
        self._footer.set_status("思考中...", busy=True)

        callbacks = self._make_callbacks()

        def run_agent() -> list:
            """在 Worker 线程中执行的 Agent 逻辑。"""
            return self._agent.run_agent_turn(self._history, callbacks=callbacks)

        self.run_worker(run_agent, thread=True, name="agent_turn")

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Worker 状态变化时更新 UI。"""
        if event.state == WorkerState.SUCCESS:
            if self._agent.awaiting_user_input:
                self.push_screen(
                    QuestionScreen(
                        self._agent.pending_question or "",
                        self._agent.pending_question_meta,
                    ),
                    callback=self._on_question_answered,
                )
                return

            self._is_busy = False
            self._footer.set_status("就绪", busy=False)
            self._input_box.focus_input()
        elif event.state == WorkerState.ERROR:
            self._is_busy = False
            self._footer.set_status("执行出错", busy=False)
            self._transcript.add_assistant_message(
                f"[{ERROR}]请求执行过程中出现错误，请重试。[/]"
            )
            self._input_box.focus_input()

    def _on_question_answered(self, answer: str | None) -> None:
        """处理 QuestionScreen 返回的答案。"""
        final_answer = answer if answer is not None else "CANCELLED"
        self._history.append(HumanMessage(content=final_answer))
        self._transcript.add_user_message(final_answer)
        self._start_agent_turn()

    # ── Agent 回调处理 ─────────────────────────────────────────

    def _on_tool_start(self, name: str, args: dict) -> None:
        """Agent 工具开始回调。"""
        self.call_from_thread(self.post_message, ToolStartEvent(name, args))

    def _on_tool_result(self, name: str, output: str, is_error: bool) -> None:
        """Agent 工具结果回调。"""
        self.call_from_thread(self.post_message, ToolResultEvent(name, output, is_error))

    def _on_assistant_message(self, content: str) -> None:
        """Agent 助手消息回调。"""
        self.call_from_thread(self.post_message, AssistantMessageEvent(content))

    def _on_progress_message(self, content: str) -> None:
        """Agent 进度消息回调。"""
        self.call_from_thread(self.post_message, ProgressMessageEvent(content))

    def _on_context_stats(self, stats) -> None:
        """Agent 上下文统计回调。"""
        self.call_from_thread(self.post_message, ContextStatsEvent(stats))

    def _on_compression(self, kind: str, result: dict) -> None:
        """Agent 压缩事件回调。"""
        self.call_from_thread(self.post_message, CompressionEvent(kind, result))

    def on_tool_start_event(self, event: ToolStartEvent) -> None:
        """处理工具开始事件。"""
        self._footer.set_status(f"运行 {event.tool_name}...", busy=True)
        self._transcript.add_tool_start(event.tool_name, event.tool_input)

    def on_tool_result_event(self, event: ToolResultEvent) -> None:
        """处理工具结果事件。"""
        self._transcript.add_tool_result(
            event.tool_name, event.output, event.is_error
        )
        self._footer.set_status("思考中...", busy=True)

    def on_assistant_message_event(self, event: AssistantMessageEvent) -> None:
        """处理助手消息事件。"""
        self._transcript.add_assistant_message(event.content)

    def on_progress_message_event(self, event: ProgressMessageEvent) -> None:
        """处理进度消息事件。"""
        self._transcript.add_progress_message(event.content)

    def on_context_stats_event(self, event: ContextStatsEvent) -> None:
        """处理上下文统计事件。"""
        self._header.set_context_stats(event.stats)

    def on_compression_event(self, event: CompressionEvent) -> None:
        """处理压缩事件。"""
        self._transcript.add_compression_info(event.kind, event.result)
        if event.kind == "auto-compact":
            saved = event.result.get("tokens_before", 0) - event.result.get("tokens_after", 0)
            self._footer.set_compression_status(f"压缩节省 {saved} tokens")
