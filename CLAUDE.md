# CLAUDE.md

Behavioral guidelines for the Camel Code project. Tailored for an AI Agent with a four-layer context compression pipeline.

**Tradeoff:** These guidelines bias toward correctness over speed. For trivial edits, use judgment.

## 1. Understand Before Modifying

**Read the pipeline. Know the layer.**

Before touching any code in `src/compact/` or `src/agents/`:
- Understand which of the four layers (Snip → Microcompact → Context Collapse → Auto Compact) your change affects.
- If modifying `CompactPipelineState`, check all layers that share it — they persist across turns.
- If adding a new tool, register it in `LeadAgent.tools` and handle its output size in `tool_result_storage`.

Ask: "Does this change break the contract between layers?" If unsure, trace the data flow from `run_compact_pipeline()` through all four layers.

## 2. Match the Bilingual Style

**中文注释，英文代码。保持一致。**

- Docstrings and comments: Use **Chinese** (follow existing style).
- Variable names, class names, function names: Use **English**.
- String literals for user-facing output: **Chinese** (follow CLI style in `main.py`).
- Log/diagnostic messages: Follow existing format (`[snip]`, `[collapse]`, `[auto-compact]`).

Don't mix languages in the same comment. Don't translate existing Chinese docstrings to English.

## 3. Respect the Message Lifecycle

**Messages are mutable history. Treat them carefully.**

- LangChain message types (`SystemMessage`, `HumanMessage`, `AIMessage`, `ToolMessage`) are the core abstraction. Don't break their contracts.
- `ToolMessage` content may be replaced by `replace_large_tool_result()` — always check if the message has been compacted before reading its content.
- The pipeline produces **two** views: `messages` (full history) and `model_messages` (with collapsed summaries). Know which one your code consumes.
- Never mutate a message list while iterating over it. Make a copy first.

## 4. Surgical Precision

**Touch only what you must. The pipeline is sensitive.**

When editing:
- Don't refactor adjacent layers "while you're there."
- Don't change existing warning thresholds in `token_estimator.py` unless explicitly asked.
- Don't reorder the four layers in `run_compact_pipeline()` — the order matters.
- Match existing code style (dataclasses, type hints, `__future__.annotations`).

Clean up your own orphans: if your change removes a field from a dataclass, remove all references to it. Don't remove pre-existing fields unless asked.

## 5. Verify with the Agent

**Run it. Watch the compression diagnostics.**

Before declaring a change complete:
- Start the CLI (`python main.py`) and send a query that triggers tool use.
- Verify compression diagnostics appear correctly: `[snip]`, `[collapse]`, `[auto-compact]`.
- Check that tool results are handled properly (no duplicate replacements, no dropped messages).
- For new tools: verify they appear in the model's tool list and execute correctly.

For multi-step tasks, state a brief plan:
```
1. [修改] → 验证: 诊断输出正常
2. [修改] → 验证: 工具调用成功
3. [修改] → 验证: 消息列表完整
```

---

**These guidelines are working if:** fewer pipeline regressions, consistent bilingual style, and changes stay within the layer they target.
