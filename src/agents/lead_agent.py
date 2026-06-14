"""Lead Agent —— LangGraph 驱动的编码助手 facade。

对外保留 run_agent_turn 接口，内部使用 StateGraph 编排
四层压缩 + ReAct 工具调用循环。

Agent 通过钩子与外部解耦，不直接依赖 UI 框架。
"""
from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage

from src import config
from src.agents.graph import AgentState, build_graph
from src.compact import CompactPipelineState
from src.hook import AgentEventEmitter, HookManager
from src.models import create_llm
from src.tools import bash, edit_file, glob, grep, read_file, write_file, ask_user


class LeadAgent:
    """CamelCode 主 Agent。

    每回合通过 LangGraph StateGraph 执行：
    上下文压缩 → LLM 推理 → 条件路由（工具执行 / 结束）
    """

    def __init__(self):
        # 工具注册表
        self.tools = {
            bash.name: bash,
            read_file.name: read_file,
            write_file.name: write_file,
            edit_file.name: edit_file,
            glob.name: glob,
            grep.name: grep,
            ask_user.name: ask_user,
        }

        # 跨回合持久化的压缩状态
        self.compact_state = CompactPipelineState()

        # 等待用户输入状态（由 ask_user 工具触发）
        self.awaiting_user_input = False
        self.pending_question: str | None = None
        self.pending_question_meta: dict | None = None

        # 钩子管理器：供外部注册 UI 通知、日志等横切逻辑
        self.hookManager = HookManager()

        # 事件发射器：由 Agent 管理，TUI 通过 on_xxx 方法订阅
        self.events = AgentEventEmitter(self.hookManager)

        # LLM 实例与模型名会在每个回合前重新加载配置并刷新
        self.llm: BaseChatModel
        self.model_name: str
        self._refresh_llm()

    # ── 高层事件订阅接口（供 TUI 等外部系统使用）──────────────────

    def on_tool_start(self, handler):
        """订阅工具开始事件。"""
        self.events.on_tool_start(handler)

    def on_tool_result(self, handler):
        """订阅工具结果事件。"""
        self.events.on_tool_result(handler)

    def on_assistant_message(self, handler):
        """订阅助手消息事件。"""
        self.events.on_assistant_message(handler)

    def on_progress_message(self, handler):
        """订阅进度消息事件。"""
        self.events.on_progress_message(handler)

    def on_context_stats(self, handler):
        """订阅上下文统计更新事件。"""
        self.events.on_context_stats(handler)

    def on_compression(self, handler):
        """订阅压缩事件。"""
        self.events.on_compression(handler)

    def _refresh_llm(self) -> None:
        """重新加载运行时配置并刷新 LLM 实例，实现配置热更新。"""
        runtime_config = config.load_runtime_config()
        self.llm = create_llm(runtime_config)
        self.model_name = runtime_config.model

    def run_agent_turn(
        self,
        messages: list,
        max_steps: int = 50,
    ):
        """执行一个 Agent 回合。

        Args:
            messages: 对话历史（会被原地修改并返回）
            max_steps: 每回合最多 LLM 调用轮数

        Returns:
            更新后的消息列表
        """
        # 每个回合前重新加载配置，支持运行时热更新模型
        self._refresh_llm()

        # 重置本回合标记（如 snipped_this_turn）
        self.compact_state.reset_turn()

        # 构建状态图（max_steps 通过闭包注入）
        graph = build_graph(self.llm, self.tools, max_steps, self.hookManager)

        initial_state: AgentState = {
            "messages": messages,
            "model_messages": list(messages),
            "step": 0,
            "compact_state": self.compact_state,
            "model_name": self.model_name,
        }

        # 执行图：最坏情况下每轮 3 个节点（compress + llm + tool）
        result = graph.invoke(
            initial_state,
            config={"recursion_limit": max_steps * 3 + 10},
        )

        # 读取等待用户输入状态
        self.awaiting_user_input = result.get("awaiting_user_input", False)
        self.pending_question = result.get("pending_question")
        self.pending_question_meta = result.get("pending_question_meta")

        # 将完整历史写回外部列表
        messages[:] = result["messages"]

        # 达到最大步数时追加提示
        if result["step"] >= max_steps:
            messages.append(AIMessage(content="达到最大步数限制"))

        return messages
