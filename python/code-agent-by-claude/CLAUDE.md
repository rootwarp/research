# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this
repository.

## Project Overview

A multi-agent coding system built on the Claude Agent SDK. Three specialized agents work in
sequence to handle coding tasks:

1. **Researcher** — Analyzes requirements, explores the codebase, researches unfamiliar concepts.
   Output saved to `research/`.
2. **Planner** — Reads research findings and creates a detailed implementation plan.
   Output saved to `plans/`.
3. **Coder** — Implements the plan by creating/modifying files.

The `Orchestrator` coordinates this pipeline, loading MCP server config from `.mcp.json` and
passing structured results between agents.

## Build & Development Commands

```bash
# Install (using uv, recommended)
uv sync

# Install with dev dependencies (pip)
pip install -e ".[dev]"

# Run tests
pytest

# Run a single test
pytest tests/test_main.py::test_name

# Format
black src tests

# Lint
ruff check src tests

# Type check
mypy src
```

## Running the Agent

```bash
# Single task
code-agent "Create a function to calculate fibonacci numbers"

# From GitHub issue
code-agent --issue https://github.com/owner/repo/issues/123

# Specify working directory
code-agent --dir ./my-project "Add validation"

# Interactive mode (stdin loop)
code-agent --interactive
```

## Architecture

**Agent pipeline**: `Orchestrator.run_task()` runs three phases sequentially. Each agent is
defined with specific tool permissions via `ClaudeAgentOptions`:

- **ResearcherAgent** (read-only): Read, Glob, Grep, WebFetch, WebSearch, GitHub MCP.
  Uses `bypassPermissions` mode.
- **PlannerAgent** (read-only): Read, Glob, Grep, GitHub MCP. Uses `bypassPermissions` mode.
- **CoderAgent** (read-write): Read, Write, Edit, Glob, Grep, Bash. Uses `acceptEdits` mode.

**Data flow**: Each agent produces a dataclass result
(`ResearchResult` → `Plan` → `CodeResult`).
Results are serialized to both JSON and Markdown in their respective directories. The orchestrator
assembles these into a final `TaskResult`.

**MCP integration**: The orchestrator reads `.mcp.json` for MCP server configuration and expands
environment variables (e.g., `${GITHUB_PERSONAL_ACCESS_TOKEN}`) in the config before passing
servers to agents.

**SDK usage**: Agents are executed via `claude_agent_sdk.query()` async generator, yielding
`SystemMessage`, `AssistantMessage`, and `ResultMessage` types. JSON responses from agents are
parsed via regex extraction.

## Code Conventions

### Python

- Follow PEP-8
- Line length: > 70 and < 80 characters if possible

### Markdown

- Line length: > 80 and < 100 characters if possible

## Key Configuration

- **Python**: >=3.10
- **Line length**: 80 (black/ruff)
- **Type checking**: mypy strict mode
- **Runtime dependency**: `claude-agent-sdk>=0.1.0`
- **Environment variables**: `ANTHROPIC_API_KEY` (required),
  `GITHUB_PERSONAL_ACCESS_TOKEN` (optional, for GitHub MCP)
