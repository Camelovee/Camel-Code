[中文](README.md) · [Roadmap](ROADMAP_EN.md)

# CamelCode 🐫

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

CamelCode is a terminal-based AI coding assistant. It combines a lightweight TUI, a LangGraph-driven agent loop, and a four-layer context compression pipeline to help you read, edit, run, and reason about code in your workspace.

![alt text](image.png)

## Features

- **TUI interface**: Rich terminal UI (`python main.py`).
- **Tool-use agent**: Reads files, writes files, runs shell commands, searches with glob, and asks you clarifying questions when needed.
- **Context compression pipeline**: Snip → Microcompact → Context Collapse → Auto-compact, designed to keep long conversations within model context windows.
- **Skill discovery and loading**: Automatically discovers `SKILL.md` files under project-level and user-level `.claude/skills` and lists them in the system prompt. When the user mentions a skill, the agent calls `load_skill` to load its details first.
- **Hot-reloadable config**: Change model, API key, or base URL at runtime without restarting.
- **Multi-provider**: Supports Anthropic and OpenAI-compatible endpoints out of the box.
- **Bilingual by design**: Code in English, comments and UI strings in Chinese.

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/Camelovee/Camel-Code.git
cd Camel-Code
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure your model

Copy the example environment file and add your API key:

```bash
cp .env.example .env
```

Edit `.env`:

```env
MODEL_PROVIDER=anthropic
MODEL_ID=claude-3-5-sonnet
MODEL_API_KEY=sk-your-api-key-here
```

Or use `~/.camel-code/settings.json`:

```json
{
  "model": "claude-3-5-sonnet",
  "ANTHROPIC_AUTH_TOKEN": "sk-your-api-key-here"
}
```

Configuration is hot-reloaded — changes take effect on the next agent turn.

### 5. Run

```bash
python main.py
```

## Usage

In the TUI, type a message and press **Enter**. The agent will reason with tools and respond in the transcript.

### Slash commands

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/tools` | List registered tools |
| `/clear` | Clear conversation history |
| `/model` | Show current model info |
| `/quit` | Exit the application |

### When the agent needs your input

If CamelCode is unsure about your intent, it will call the `ask_user` tool and pop up a modal dialog. Answer the question or cancel to let the agent continue.

## Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                         CamelTUIApp                          │
│  (Textual UI: Header, Transcript, InputBox, FooterBar)       │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│                        LeadAgent                             │
│  ┌─────────────┐    ┌─────┐    ┌──────────┐                │
│  │  compress   │───▶│ llm │───▶│ tool_node│                │
│  └─────────────┘    └─────┘    └────┬─────┘                │
│                                     │                        │
│                         ┌───────────▼────────────┐          │
│                         │  ask_user detected?    │          │
│                         │  Yes → pause for user  │          │
│                         │  No  → continue loop   │          │
│                         └────────────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

### Context compression pipeline

Long tool outputs and conversation history are managed in four layers:

1. **Snip Compact**: Drop middle-turn messages when utilization is high.
2. **Microcompact**: Clear old tool results, keep the most recent ones.
3. **Context Collapse**: Summarize older messages into a collapsed view.
4. **Auto Compact**: LLM-based summary when context is critical.

## Built-in Tools

| Tool | Purpose |
|------|---------|
| `bash` | Run allowlisted shell commands |
| `read_file` | Read a text file from the workspace |
| `write_file` | Write content to a file |
| `edit_file` | Replace exact text in a file |
| `glob` | Search files by pattern |
| `ask_user` | Ask the user a clarifying question and pause the turn |
| `load_skill` | Load the content of a `SKILL.md` from project or user skills directory |

## Development

### Run tests

```bash
PYTHONPATH=$(pwd) pytest test/ -v
```

### Project structure

```text
.
├── main.py                 # TUI entry point
├── src/
│   ├── agents/             # LeadAgent + LangGraph
│   ├── compact/            # Four-layer compression pipeline
│   ├── models/             # LLM adapter
│   ├── prompts.py          # System prompt (includes skill discovery)
│   ├── skill/              # Skill discovery, loading, and schema
│   ├── tools/              # Tool definitions
│   ├── tui/                # Textual UI
│   └── utils/              # Token estimation, etc.
├── test/                   # pytest suite
└── docs/                   # Design docs (not versioned)
```

## Contributing

Contributions are welcome! Please open an issue or pull request.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

[MIT](LICENSE)

## Acknowledgements

Built with [LangChain](https://github.com/langchain-ai/langchain), [LangGraph](https://github.com/langchain-ai/langgraph), and [Textual](https://github.com/Textualize/textual).
