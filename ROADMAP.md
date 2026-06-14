[English](ROADMAP_EN.md)

# CamelCode 开发路书

本文档描述 CamelCode 的阶段性开发计划。优先级和功能边界会随实际反馈调整。

## 已发布

### v0.0.1 —— 可用的终端编码助手

- [x] TUI 模式入口
- [x] 基础工具集：bash、read_file、write_file、edit_file、glob
- [x] 四层上下文压缩管道（Snip / Microcompact / Context Collapse / Auto-compact）
- [x] LangGraph 驱动的 ReAct 工具调用循环
- [x] 运行时配置热更新（模型、API Key、Base URL）
- [x] Anthropic / OpenAI 双模型后端
- [x] `ask_user` 工具 + TUI 模态弹窗
- [x] 中英双语的 README 与 MIT 许可证
- [x] 技能（Skill）发现与加载机制

## 短期（v0.1.x）

### v0.1.0 —— LangGraph 工作流与人工审核

- [ ] 引入 LangGraph checkpoints，支持会话状态持久化与恢复
- [ ] 引入 LangGraph 中断（interrupt）机制，在关键节点暂停等待用户确认
- [ ] 工作流编排：支持多步骤、条件分支、人工审核点
- [ ] 基于 `ask_user` 的人工审核与继续执行

### v0.1.1 —— 结构化日志、诊断与安全沙箱

- [ ] 结构化日志与诊断输出
- [ ] 工具执行权限分级（只读 / 开发 / 危险操作需确认）
- [ ] 安全沙箱基础：命令白名单、路径边界、敏感操作拦截
- [ ] 基础的错误恢复：LLM 空响应、工具失败、上下文压缩失败时的降级策略

## 中期（v0.2.x）

### v0.2.0 —— Agent 记忆系统

- [ ] 基于文件的长期记忆（`.camel-code/memory/`）
- [ ] 自动记忆关键决策、项目约定、用户偏好
- [ ] 记忆检索与注入到 system prompt
- [ ] 项目级上下文摘要（代码结构、技术栈、关键文件）

### v0.2.1 —— MCP 接入

- [ ] MCP（Model Context Protocol）服务器接入
- [ ] MCP 工具、资源、prompts 的发现与调用
- [ ] 插件化工具注册接口

## 长期（v0.3.x - v1.0）

### v0.3.0 —— 技能生态与插件

- [ ] 预置常用技能：代码审查、重构、测试生成、文档补全
- [ ] `/skill` 斜杠命令快速加载技能
- [ ] 社区插件安装与管理
- [ ] 支持更多 LLM Provider（Gemini、Kimi、本地模型等）

### v1.0 —— 生产就绪

- [ ] 稳定的 API 与配置格式
- [ ] 完整的文档站点
- [ ] 安全沙箱与权限审计完善
- [ ] 性能基准与资源占用优化
- [ ] 正式发布与版本策略

## 当前冻结 / 低优先级

- TUI 端到端测试与界面增强：当前重点放在 Agent 核心能力，TUI 暂时维持现有形态。

## 如何参与

如果你对其中的某个方向感兴趣，欢迎：

1. 在 GitHub 开 Issue 讨论具体实现方案
2. 认领路书中的任务并提交 Pull Request
3. 提出新的功能建议

路书会随项目进展持续更新。
