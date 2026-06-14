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

## Short-term (v0.1.x)

### v0.1.0 — Richer tools

- [ ] Add `preview` field to `ask_user` for code snippets or config comparisons
- [ ] Richer file tools: batch reads, file diffs, directory tree
- [ ] Tool permission tiers (readonly / development / dangerous operations require confirmation)
- [ ] Better error recovery for empty LLM responses, tool failures, and compression errors

### v0.1.1 — Stability and observability

- [ ] Structured logging and diagnostics
- [ ] Persistent token-usage statistics
- [ ] Session export / import (resume from any message)
- [ ] Unit test coverage above 80%
- [ ] End-to-end smoke tests for TUI

## Mid-term (v0.2.x)

### v0.2.0 — Skills and workflows

- [x] Skill discovery and loading mechanism
- [ ] Built-in skills: code review, refactoring, test generation, documentation
- [ ] Workflow orchestration with multi-step tasks, branches, and human-in-the-loop checkpoints
- [ ] `/skill` slash command for quick skill loading

### v0.2.1 — Memory and context

- [ ] File-based long-term memory (`.camel-code/memory/`)
- [ ] Auto-capture key decisions, project conventions, and user preferences
- [ ] Memory retrieval and injection into system prompt
- [ ] Project-level context summary (structure, tech stack, key files)

## Long-term (v0.3.x - v1.0)

### v0.3.0 — MCP and plugin ecosystem

- [ ] MCP (Model Context Protocol) server integration
- [ ] Pluggable tool registration interface
- [ ] Community plugin installation and management
- [ ] Support for more LLM providers (Gemini, Kimi, local models, etc.)

### v1.0 — Production ready

- [ ] Stable API and configuration format
- [ ] Complete documentation site
- [ ] Security sandboxing and permission auditing
- [ ] Performance benchmarks and resource optimization
- [ ] Stable release and versioning policy

## How to contribute

If you are interested in any of these directions:

1. Open a GitHub Issue to discuss the implementation
2. Claim a roadmap item and submit a Pull Request
3. Propose new features

This roadmap will be updated as the project evolves.
