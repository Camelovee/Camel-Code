"""Lead Agent —— LangGraph 驱动的编码助手 facade。

对外保留 run_agent_turn 接口，内部使用 StateGraph 编排
四层压缩 + ReAct 工具调用循环。

纯 CLI 模式：Agent 不依赖任何 UI 框架，无回调、无事件流。
"""
from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage

from src import config
from src.agents.graph import AgentState, build_graph
from src.compact import CompactPipelineState
from src.models import create_llm
from src.tools import bash, edit_file, glob, read_file, write_file


class LeadAgent:
    """CamelCode 主 Agent。

    每回合通过 LangGraph StateGraph 执行：
    上下文压缩 → LLM 推理 → 条件路由（工具执行 / 结束）
    """

    def __init__(
        self,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ):
        # LLM 实例
        self.llm: BaseChatModel = create_llm(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        # 工具注册表
        self.tools = {
            bash.name: bash,
            read_file.name: read_file,
            write_file.name: write_file,
            edit_file.name: edit_file,
            glob.name: glob,
        }

        # 跨回合持久化的压缩状态
        self.compact_state = CompactPipelineState()
        self.model_name = config.MODEL_ID

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
        # 重置本回合标记（如 snipped_this_turn）
        self.compact_state.reset_turn()

        # 构建状态图（max_steps 通过闭包注入）
        graph = build_graph(self.llm, self.tools, max_steps)

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

        # 将完整历史写回外部列表
        messages[:] = result["messages"]

        # 达到最大步数时追加提示
        if result["step"] >= max_steps:
            messages.append(AIMessage(content="达到最大步数限制"))

        return messages
