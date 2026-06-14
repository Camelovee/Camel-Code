[中文](ROADMAP.md)

# CamelCode Roadmap

This document outlines the phased development plan for CamelCode. Priorities and scope may shift based on feedback.

## Released

### v0.0.1 — A usable terminal coding assistant

- [x] TUI mode entrypoint
- [x] Basic toolset: bash, read_file, write_file, edit_file, glob
- [x] Four-layer context compression pipeline (Snip / Microcompact / Context Collapse / Auto-compact)
- [x] LangGraph-driven ReAct tool-calling loop
- [x] Hot-reloadable runtime config (model, API key, base URL)
- [x] Anthropic / OpenAI model backends
- [x] `ask_user` tool + TUI modal dialog
- [x] Chinese and English READMEs with MIT license
- [x] Skill discovery and loading mechanism

## Short-term (v0.1.x)

### v0.1.0 — LangGraph workflows and human-in-the-loop

- [ ] LangGraph checkpoints for session persistence and recovery
- [ ] LangGraph interrupt mechanism to pause at critical nodes for user confirmation
- [ ] Workflow orchestration: multi-step tasks, conditional branches, human-in-the-loop checkpoints
- [ ] Human review and resume execution based on `ask_user`

### v0.1.1 — Structured logging, diagnostics, and security sandbox

- [ ] Structured logging and diagnostic output
- [ ] Tool permission tiers (readonly / development / dangerous operations require confirmation)
- [ ] Security sandbox basics: command allowlist, path boundaries, sensitive-operation interception
- [ ] Basic error recovery for empty LLM responses, tool failures, and compression errors

## Mid-term (v0.2.x)

### v0.2.0 — Agent memory system

- [ ] File-based long-term memory (`.camel-code/memory/`)
- [ ] Auto-capture key decisions, project conventions, and user preferences
- [ ] Memory retrieval and injection into system prompt
- [ ] Project-level context summary (structure, tech stack, key files)

### v0.2.1 — MCP integration

- [ ] MCP (Model Context Protocol) server integration
- [ ] Discovery and invocation of MCP tools, resources, and prompts
- [ ] Pluggable tool registration interface

## Long-term (v0.3.x - v1.0)

### v0.3.0 — Skill ecosystem and plugins

- [ ] Built-in skills: code review, refactoring, test generation, documentation
- [ ] `/skill` slash command for quick skill loading
- [ ] Community plugin installation and management
- [ ] Support for more LLM providers (Gemini, Kimi, local models, etc.)

### v1.0 — Production ready

- [ ] Stable API and configuration format
- [ ] Complete documentation site
- [ ] Security sandboxing and permission auditing
- [ ] Performance benchmarks and resource optimization
- [ ] Stable release and versioning policy

## Frozen / Low priority

- TUI end-to-end tests and UI enhancements: current focus is on Agent core capabilities; the TUI will remain in its current form for now.

## How to contribute

If you are interested in any of these directions:

1. Open a GitHub Issue to discuss the implementation
2. Claim a roadmap item and submit a Pull Request
3. Propose new features

This roadmap will be updated as the project evolves.
