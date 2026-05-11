# Hermes Quick Start

This project is a good fit for Hermes as a repo assistant, startup-chain checker, and integration helper.

## Current local setup

- Hermes config: `~/.hermes/config.yaml`
- Preferred Ollama endpoint: `http://192.168.50.141:11434/v1`
- Default model: `gemma4:latest`
- Hermes provider mode: `custom` for OpenAI-compatible Ollama access

## Start Hermes in this repo

```bash
cd "/Users/macminim4/Documents/New project/jyf0330-repos/ai-trading-assistant-main"
hermes
```

## Best first commands

Use these prompts directly inside Hermes.

### 1. Understand the repo

```text
帮我快速理解这个仓库的启动方式，不改代码，只给我最短结论。
```

### 2. Trace startup chain

```text
帮我梳理这个项目从脚本到 app-shell 页面启动的链路，只看当前仓库，按“入口脚本 -> 服务 -> 页面”输出。
```

### 3. Find Ollama integration points

```text
帮我找出这个仓库里所有 Ollama 相关配置和调用点，按 文件 + 作用 输出。
```

### 4. Find hard-coded paths

```text
帮我检查仓库里还剩哪些写死的 Linux 或 Windows 路径，不修改代码，只列出风险点。
```

### 5. Review app-shell analysis flow

```text
帮我解释 app-shell 的 /analysis 页面是怎么调用分析逻辑的，给我关键文件和调用顺序。
```

### 6. Check paper trading flow

```text
帮我梳理 /paper 页面和本地规则账户、open-paper-trading-mcp 之间的关系，重点说现在是不是两套账户。
```

### 7. Plan next engineering steps

```text
基于当前仓库状态，帮我列出最值得做的 5 个下一步，只要高优先级、低空话。
```

## Good prompt pattern

Use this structure when asking Hermes to work on the repo:

```text
目标 + 范围 + 是否允许改代码 + 输出格式
```

Example:

```text
帮我检查这个项目的启动问题，只看当前仓库，可以改代码，最后给我最短验证步骤。
```

## Recommended usage pattern

1. Ask Hermes to inspect before editing.
2. Ask for the smallest safe change.
3. Ask it to verify with a concrete command or test.
4. Only then move to larger refactors.

## Quick one-shot usage

```bash
hermes chat -q "帮我列出这个仓库里所有启动脚本以及它们各自负责什么"
```
