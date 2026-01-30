# Code Agent by Claude

AI-powered coding agents using the Claude Agent SDK.
This project implements a four-agent pipeline:

1. **Researcher** — Explores the codebase and researches unfamiliar concepts
2. **Planner** — Reads research findings and creates a high-level plan
3. **Detail Planner** — Breaks the plan into small, self-contained parts
4. **Coder** — Iterates through the TODO checklist, implementing each part

## Installation

```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -e .
```

## Prerequisites

- Python 3.10+
- Claude Code CLI installed (`curl -fsSL https://claude.ai/install.sh | bash`)
- Authenticated with Claude Code or `ANTHROPIC_API_KEY` environment variable set
- (Optional) `GITHUB_PERSONAL_ACCESS_TOKEN` for GitHub MCP integration

## Usage

### Command Line

```bash
# Run a single task
code-agent "Create a function to calculate fibonacci numbers"

# Specify working directory
code-agent --dir ./my-project "Add input validation to forms"

# Interactive mode
code-agent --interactive

# Quiet mode (less output)
code-agent --quiet "Fix the bug in utils.py"
```

### Python API

```python
import asyncio
from code_agent_by_claude import run_coding_task, Orchestrator

# Simple usage
async def main():
    result = await run_coding_task(
        task="Create a REST API endpoint for user registration",
        working_dir="./my-project",
        verbose=True
    )

    if result.success:
        print("Task completed!")
        print(f"Plan: {result.plan}")
        print(f"Files created: {result.code_result.files_created}")
    else:
        print(f"Failed: {result.error}")

asyncio.run(main())

# Using the Orchestrator directly
async def advanced_usage():
    orchestrator = Orchestrator(working_dir="./my-project")
    result = await orchestrator.run_task("Implement caching layer")
    return result
```

### Running Individual Agents

Each agent can be run in isolation via its own CLI command.
This is useful for debugging or running a single pipeline stage.

#### Researcher

Explores the codebase and researches unfamiliar concepts.

```bash
run-researcher --task "Understand the auth flow" --working-dir ./my-project
run-researcher --task "Research caching strategies" --show-thinking
```

| Option | Default | Description |
|---|---|---|
| `--task` | *(required)* | Coding task description |
| `--working-dir` | `.` | Working directory |
| `--show-thinking` | off | Show agent thinking |
| `--show-tools` | off | Show tool usage |

#### Planner

Reads research findings and creates a high-level implementation plan.

```bash
run-planner --working-dir ./my-project
run-planner --research-dir research --show-tools
```

| Option | Default | Description |
|---|---|---|
| `--working-dir` | `.` | Working directory |
| `--research-dir` | `research` | Path to research output |
| `--show-thinking` | off | Show agent thinking |
| `--show-tools` | off | Show tool usage |

#### Detail Planner

Breaks the high-level plan into small, self-contained parts
written as individual markdown files in `detail_plans/`.

```bash
run-detail-planner --working-dir ./my-project
run-detail-planner --plans-dir plans --show-thinking
```

| Option | Default | Description |
|---|---|---|
| `--working-dir` | `.` | Working directory |
| `--plans-dir` | `plans` | Path to plans directory |
| `--show-thinking` | off | Show agent thinking |
| `--show-tools` | off | Show tool usage |

#### Coder

Iterates through the `detail_plans/TODO.md` checklist,
implementing each part and running tests.

```bash
run-coder --working-dir ./my-project
run-coder --plans-dir plans --show-tools
```

| Option | Default | Description |
|---|---|---|
| `--working-dir` | `.` | Working directory |
| `--plans-dir` | `plans` | Path to plans directory |
| `--show-thinking` | off | Show agent thinking |
| `--show-tools` | off | Show tool usage |

### Using Agents from Python

```python
from code_agent_by_claude import PlannerAgent, CoderAgent

# Get agent definitions for custom orchestration
planner = PlannerAgent(working_dir=".")
coder = CoderAgent(working_dir=".")

# Use with Claude Agent SDK directly
planner_def = planner.get_agent_definition()
coder_def = coder.get_agent_definition()
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Orchestrator                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐          ┌─────────────────┐          │
│  │  Planner Agent  │  ─────>  │   Coder Agent   │          │
│  │                 │   Plan   │                 │          │
│  │ - Analyze task  │          │ - Read plan     │          │
│  │ - Explore code  │          │ - Write code    │          │
│  │ - Create plan   │          │ - Run tests     │          │
│  └─────────────────┘          └─────────────────┘          │
│         │                            │                     │
│         │ Read, Glob, Grep           │ Read, Write, Edit   │
│         │                            │ Glob, Grep, Bash    │
│         ▼                            ▼                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Codebase                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Agent Details

### Planner Agent

- **Tools**: Read, Glob, Grep, GitHub MCP (read-only)
- **MCP Integration**: Uses GitHub MCP to fetch issues, PRs, and code from repositories
- **Output**: Structured JSON plan with:
  - Task description
  - Requirements list
  - Files to create/modify
  - Implementation steps
  - Dependencies

### Coder Agent

- **Tools**: Read, Write, Edit, Glob, Grep, Bash
- **Input**: Implementation plan from Planner
- **Output**: Implemented code with summary

## GitHub MCP Integration

The Planner agent can use GitHub MCP to gather context from repositories and issues. Configure it in `.mcp.json`:

```json
{
  "mcpServers": {
    "github": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp/",
      "headers": {
        "Authorization": "Bearer ${GITHUB_PERSONAL_ACCESS_TOKEN}"
      }
    }
  }
}
```

Set your GitHub token:

```bash
export GITHUB_PERSONAL_ACCESS_TOKEN="ghp_your_token_here"
```

The planner can then:
- Fetch issue details for implementation context
- Read files from GitHub repositories
- Search for code patterns across repos
- List related issues and PRs

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src tests

# Lint
ruff check src tests

# Type check
mypy src
```

## License

MIT
