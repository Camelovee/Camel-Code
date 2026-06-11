
<h1 align="center">
  <br>
  <pre>
      ╭───╮ ╭───╮
      │ ■ │ │ ■ │   <b>CamelCode</b>
      ╰─┬─╯ ╰─┬─╯
     __/       \__
    /  o       o  \
   │      ___      │
    \_____________/
      ││       ││
  </pre>
  <br>
  终端 AI 编码助手 · Terminal AI Coding Assistant
</h1>

<p align="center">
  <strong>🐫 骆驼穿越沙漠——AI 在有限的上下文窗口中走得更远</strong>
</p>

<p align="center">
  <a href="#-overview">Overview</a> •
  <a href="#-features">Features</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-architecture">Architecture</a> •
  <a href="#-layer-compression-pipeline">Compression</a> •
  <a href="#-configuration">Configuration</a> •
  <a href="#-project-structure">Structure</a>
</p>

---

## 🌟 Overview

**CamelCode** is a terminal-based AI coding assistant built with **Python**, **LangChain**, and **LangGraph**. It provides both a CLI and a full-screen TUI (Terminal User Interface) where you can interact with AI models conversationally—the AI can read/write files, run shell commands, and more.

The name reflects the project's core philosophy: **like a camel crossing the desert, the AI goes further on limited context**. Built-in **four-layer progressive context compression** manages long conversations within LLM context windows, making it practical for extended coding sessions.

### Why CamelCode?

| Challenge | CamelCode Solution |
|-----------|-------------------|
| 🧠 LLM context windows are limited | **4-layer progressive compression** — from zero-cost deletions to LLM-powered summarization |
| 🔧 Coding requires tool use | **ReAct loop** + **5 built-in tools** (bash, read/write/edit file, glob) |
| 🖥️ Terminal-first experience | **Textual TUI** with desert theme, real-time token statistics |
| 🔄 Long sessions lose context | **Cross-turn state persistence** — compression state survives across conversation turns |
| 🔌 Multi-model support | **Adapter pattern** — Anthropic Claude, OpenAI GPT, DeepSeek, and more |

---

## ✨ Features

- **🧠 Multi-model support** — Claude 3, GPT-4, DeepSeek, and any OpenAI-compatible API
- **🔄 ReAct agent loop** — AI reasons, calls tools, observes results, continues iterating
- **📂 Built-in tools** — `bash`, `read_file`, `write_file`, `edit_file`, `glob`
- **🎨 Beautiful TUI** — Full-screen Textual interface with desert camel theme
- **📊 Real-time stats** — Token usage, utilization %, compression diagnostics, step counter
- **🏜️ Four-layer compression** — Progressive context management (details below)
- **💾 Tool result persistence** — Large outputs auto-saved to disk with preview
- **🔒 Security** — Path escape detection, dangerous command blocking, tool output size limits
- **🌐 Bilingual** — Chinese UI/CLI feedback, English codebase

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- An API key for your preferred LLM provider

### Installation

```bash
# Clone the repository
git clone https://github.com/camel-ai/camelcode.git
cd camelcode

# Install dependencies
pip install -r requirements.txt

# Configure your API key
cp .env.example .env
# Edit .env with your model settings
```

### Run

```bash
# CLI mode (lightweight)
python main.py

# TUI mode (full-screen interface)
python main.py --tui
```

### Usage

| Action | Description |
|--------|-------------|
| Type your question | Press Enter to send |
| `q` / `exit` / `/exit` | Quit the program |
| `Ctrl+C` | Quick exit (TUI mode) |
| Click "💭 Thinking..." | Expand/collapse AI reasoning |

---

## 🏛️ Architecture

```
main.py ──→ TUI (Textual) ──→ LeadAgent ──→ StateGraph
                                               │
                          ┌────────────────────┼────────────┐
                          ↓                    ↓            ↓
                    压缩节点(compress)    LLM节点(llm)   工具节点(tool)
                          │                    │            │
                          └────────────────────┴────────────┘
                                (循环直到无 tool_calls 或达上限)
```

### Data Flow

```
User Input → [SystemMessage, HumanMessage, ...]
    ↓
Layer 1: Snip Compact    ── Remove safe middle interval
    ↓
Layer 2: Microcompact    ── Replace old tool results with marker
    ↓
Layer 3: Context Collapse ── LLM summary replaces interval (model-view only)
    ↓
Layer 4: Auto Compact    ── LLM full conversation summary (step 0 only)
    ↓
Two Views:
  - messages         → Full history (for UI, next turn input)
  - model_messages   → Compressed view (sent to LLM)
    ↓
LLM Inference → has tool_calls? → Execute tool → Compress result → Back to Layer 1
               → no tool_calls  → Turn ends, return to user
```

### LangGraph StateGraph

Defined in `src/agents/graph.py`:

```
Nodes:
  compress   → Four-layer compression pipeline
  llm        → LLM inference (bound tools)
  tool_node  → Tool execution + result compression

Edges:
  compress → llm (compress before each inference)
  llm → should_continue (conditional routing)
    ├─ has tool_calls → tool_node
    └─ no tool_calls or max_steps reached → END
  tool_node → compress (re-compress after tool execution)
```

---

## ⛰️ 4-Layer Compression Pipeline

This is the project's core innovation—a **progressive, multi-level context management system** inspired by the MiniCode TypeScript reference implementation.

### Layer 1: Snip Compact (`snip_compact.py`)

| Property | Value |
|----------|-------|
| **Trigger** | Utilization ≥ 70% |
| **Target** | Reduce to 60% utilization |
| **Protection** | Boundary msgs, edit tools, errors — never snipped |
| **Min release** | 2,000 tokens |
| **Keep recent** | Last 12 messages |
| **Cost** | Zero (deterministic) |

**Strategy**: Find a safe middle interval in the conversation, remove it entirely, insert a `snip_boundary` marker message. Runs once per turn.

### Layer 2: Microcompact (`microcompact.py`)

| Property | Value |
|----------|-------|
| **Trigger** | Utilization ≥ 50% |
| **Keep recent** | Last 3 tool results |
| **Compactable tools** | bash, glob, read_file, list_files |
| **Cost** | Zero (deterministic) |

**Strategy**: Replace old compactable tool results with `[Output cleared for context space]`. Lightweight, deterministic, no LLM call.

### Layer 3: Context Collapse (`context_collapse.py`)

| Property | Value |
|----------|-------|
| **Trigger** | Utilization ≥ 75% |
| **Target** | Reduce to 65% utilization |
| **Max spans/pass** | 2 |
| **Max consecutive failures** | 3 (disables layer) |
| **Cost** | 1 LLM call per span |

**Strategy**: Generate an LLM summary for a selected message span. **Key**: Only replaces in `model_messages` (model-visible view), full history preserved in `messages`. Persists across turns.

### Layer 4: Auto Compact (`auto_compact.py`)

| Property | Value |
|----------|-------|
| **Trigger** | Utilization ≥ 85% (critical) or ≥ 95% (blocked) |
| **When** | Step 0 only (first inference of each turn) |
| **Keep tail** | At least 6 messages, max 40K tokens |
| **Cost** | 1 LLM call |

**Strategy**: Full conversation summarization via LLM. Replaces compressed messages and resets all lower-layer state. The most aggressive compression layer.

### Compression Visualization

```
Utilization:  0% ─────── 50% ────── 70% ────── 75% ────── 85% ──── 95% ──→ 100%
                   │          │          │          │          │        │
Layer Active:      └─ Micro ──┘ └─ Snip ─┘ └─ Collapse ─┘ └─ Auto ──┘ └─ Blocked
```

### Tool Result Storage (`tool_result_storage.py`)

- Tool outputs exceeding **50,000 characters** are automatically persisted to `.tool_results/`
- Replaced in-message with `<persisted-output>` tag + preview
- Batch budget control via `apply_tool_result_budget()` (200K limit)

---

## ⚙️ Configuration

### Environment Variables (`.env`)

```env
# Model Provider: "anthropic" or "openai"
MODEL_PROVIDER=anthropic

# Model ID (e.g., claude-3-5-sonnet, gpt-4o, deepseek-chat)
MODEL_ID=deepseek-v4-flash

# API Endpoint (supports custom reverse proxies)
MODEL_BASE_URL=https://api.deepseek.com/anthropic

# API Key
MODEL_API_KEY=sk-...

# Generation Parameters
MODEL_MAX_TOKENS=8000
MODEL_TEMPERATURE=0.1
```

### Supported Models

| Provider | Models | Context Window |
|----------|--------|---------------|
| Anthropic | Claude 3 Opus/Sonnet/Haiku | 200K |
| OpenAI | GPT-4o, GPT-4 Turbo, GPT-4, GPT-3.5 | 8K–128K |
| DeepSeek | DeepSeek V2/V3 | 128K |
| Any OpenAI-compatible | Custom endpoints | Configurable |

---

## 📁 Project Structure

```
CamelCode/
├── main.py              # Entry point (CLI / TUI)
├── CLAUDE.md            # Coding guidelines for AI agents
├── .env                 # Environment configuration
│
├── src/
│   ├── agents/          # Agent layer
│   │   ├── lead_agent.py    # LeadAgent facade
│   │   └── graph.py         # LangGraph StateGraph
│   │
│   ├── compact/         # 4-layer compression pipeline ❄️
│   │   ├── pipeline.py          # Orchestration
│   │   ├── compact_core.py      # Shared core (groups, protection, ranges)
│   │   ├── snip_compact.py      # Layer 1: Snip
│   │   ├── microcompact.py      # Layer 2: Micro
│   │   ├── context_collapse.py  # Layer 3: Collapse
│   │   ├── auto_compact.py      # Layer 4: Auto
│   │   ├── tool_result_storage.py # Large output persistence
│   │   └── prompts.py           # Summary generation prompts
│   │
│   ├── models/          # Model adapters
│   │   └── adapter.py   # Factory: create LLM instances
│   │
│   ├── tools/           # Tool registry
│   │   ├── bash_tool.py     # Shell command execution
│   │   ├── file_tools.py    # read/write/edit file
│   │   └── glob_tool.py     # File pattern search
│   │
│   ├── tui/             # Terminal UI (Textual)
│   │   ├── app.py       # Main app logic
│   │   ├── widgets.py   # Custom widgets
│   │   ├── render.py    # Message formatting
│   │   ├── theme.py     # Desert color palette
│   │   └── styles.tcss  # Textual CSS
│   │
│   └── utils/           # Utilities
│       ├── token_estimator.py  # Token estimation
│       └── model_context.py    # Model context window config
│
├── test/                # Python tests
│   └── test_compact.py  # Compression pipeline tests
│
└── MiniCode/            # TypeScript reference implementation
    ├── src/             # TS source
    ├── test/            # Tests (Vitest)
    └── bin/minicode     # Executable
```

---

## 🔧 Tool Reference

### bash

Execute shell commands with safety checks:

```python
bash(command="git status")           # Simple command
bash(command="ls", arguments=["-la"]) # Command + args
bash(command="npm run build &")      # Background execution
```

**Security**: Command allowlist, dangerous pattern blocking, path escape detection.

### read_file / write_file / edit_file

```python
read_file(path="src/main.py")                             # Read entire file
read_file(path="src/main.py", offset=10, limit=50)        # Read chunk
write_file(path="output.txt", content="Hello, World!")    # Write file
edit_file(path="src/main.py", old_text="foo", new_text="bar")  # Replace exact text
```

### glob

```python
glob(pattern="**/*.py")              # All Python files
glob(pattern="src/*.ts", path="lib") # Scoped search
```

---

## 🧪 Testing

```bash
# Run Python tests
pytest test/ -v

# Run TypeScript tests (MiniCode reference)
cd MiniCode && npm test
```

---

## 🔗 MiniCode Reference

The `MiniCode/` directory is the **TypeScript reference implementation** from which CamelCode's core algorithms were ported.

| Aspect | CamelCode (Python) | MiniCode (TypeScript) |
|--------|-------------------|----------------------|
| **Language** | Python 3.11+ | TypeScript (Node.js) |
| **UI Framework** | Textual (TUI) | TTY / Terminal |
| **State Management** | LangGraph StateGraph | Functional + closures |
| **Compression Pipeline** | 4 layers (Snip→Micro→Collapse→Auto) | Same |
| **Tool System** | LangChain @tool decorator | Custom Tool interface |
| **Tests** | pytest (basic) | Vitest (22 test files) |

---

## 🗺️ Roadmap

- [ ] **Web search/fetch tools** — Already registered, backend pending
- [ ] **Multi-session management** — Save and restore conversation sessions
- [ ] **Memory system** — Persistent cross-session memory
- [ ] **Skill system** — Loadable skill modules
- [ ] **MCP support** — Model Context Protocol integration
- [x] **Textual TUI** ✅ — Beautiful desert-themed interface
- [x] **4-layer compression** ✅ — Production-ready pipeline
- [x] **Multi-model support** ✅ — Anthropic, OpenAI, DeepSeek

---

## 📜 License

[MIT](LICENSE) © 2025 CamelCode Contributors

---

<p align="center">
  <sub>Built with 🐫 patience and 🏜️ endurance — like a camel crossing the desert of context.</sub>
</p>
