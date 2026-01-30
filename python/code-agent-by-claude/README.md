# Code Agent by Claude

AI-powered coding agents using the Claude Agent SDK. This project implements a two-agent system:

1. **Planner Agent** - Analyzes requirements and creates detailed implementation plans
2. **Coder Agent** - Implements code based on the plans

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

### Using Individual Agents

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
