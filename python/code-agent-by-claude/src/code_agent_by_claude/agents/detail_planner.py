"""Detail Planner Agent - Breaks plans into parts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..stream_handler import StreamHandler

from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    query,
)


@dataclass
class DetailPlanPart:
    """A single part of a detailed plan."""

    sequence: int
    title: str
    content: str


@dataclass
class DetailPlan:
    """Fine-grained implementation plan."""

    parts: list[DetailPlanPart] = field(default_factory=list)
    todo_content: str = ""

    def save_to_dir(self, detail_plans_dir: str | Path) -> Path:
        """Save each part and TODO.md."""
        path = Path(detail_plans_dir)
        path.mkdir(parents=True, exist_ok=True)

        for part in self.parts:
            slug = _slugify(part.title)
            fname = f"{part.sequence:02d}_{slug}.md"
            with open(path / fname, "w") as f:
                f.write(part.content)

        with open(path / "TODO.md", "w") as f:
            f.write(self.todo_content)

        return path


def _slugify(title: str) -> str:
    """Convert title to a filename-safe slug."""
    slug = title.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    slug = slug.strip("_")
    return slug


DETAIL_PLANNER_SYSTEM_PROMPT = """\
You are an expert software architect who breaks \
high-level plans into small, self-contained \
implementation parts.

When given a plan:
1. **Read the plan** from the plans directory:
   - Read `plans/plan.md` for the implementation plan

2. **Explore the codebase** as needed:
   - Use Read, Glob, and Grep tools to understand \
existing code structure

3. **Break the plan into small parts**:
   - Each part should be small enough to have \
minimal side effects
   - Each part should be independently reviewable
   - Parts should be ordered by dependency \
(prerequisite parts first)
   - For each part describe: scope, files affected, \
detailed changes, potential side effects

4. **Write each part to a separate markdown file** \
in the `detail_plans/` directory:
   - Name files as `01_<slug>.md`, `02_<slug>.md`, etc.
   - Use the Write tool to create each file

5. **Write a TODO checklist** to \
`detail_plans/TODO.md` using the Write tool.

Each part file should use this structure:

```markdown
## 01: Title

- **Scope**: What this part covers
- **Files**: Files to create or modify
- **Changes**: Detailed step-by-step changes
- **Side effects**: Potential side effects \
and mitigations
```

The TODO file should use this structure:

```markdown
# Implementation TODO

- [ ] 01: <title>
- [ ] 02: <title>
```

Example part file (`detail_plans/01_add_data_models.md`):

```markdown
## 01: Add data models

- **Scope**: Create new model classes
- **Files**: `src/models.py` (create)
- **Changes**: Define User and Role dataclasses
- **Side effects**: None
```

Example part file \
(`detail_plans/02_update_api_endpoints.md`):

```markdown
## 02: Update API endpoints

- **Scope**: Wire models to API layer
- **Files**: `src/api.py` (modify)
- **Changes**: Add CRUD endpoints for User
- **Side effects**: Requires models from part 01
```

Example TODO file (`detail_plans/TODO.md`):

```markdown
# Implementation TODO

- [ ] 01: Add data models
- [ ] 02: Update API endpoints
```"""


_PART_HEADER_RE = re.compile(r"^##\s+(\d+)[.:]\s*(.+)$", re.MULTILINE)
_TODO_SECTION_RE = re.compile(r"^#\s+Implementation\s+TODO\s*$", re.MULTILINE)


def _parse_detail_plan(text: str) -> DetailPlan | None:
    """Parse markdown output into a DetailPlan."""
    if not text or not text.strip():
        return None

    headers = list(_PART_HEADER_RE.finditer(text))
    if not headers:
        return None

    todo_match = _TODO_SECTION_RE.search(text)
    todo_content = ""
    content_end = len(text)
    if todo_match:
        todo_content = text[todo_match.start() :].strip()
        content_end = todo_match.start()

    parts: list[DetailPlanPart] = []
    for i, match in enumerate(headers):
        seq = int(match.group(1))
        title = match.group(2).strip()
        start = match.start()
        if i + 1 < len(headers):
            end = headers[i + 1].start()
        else:
            end = content_end
        body = text[start:end].strip()
        parts.append(DetailPlanPart(sequence=seq, title=title, content=body))

    return DetailPlan(parts=parts, todo_content=todo_content)


class DetailPlannerAgent:
    """Agent that breaks plans into detailed parts."""

    def __init__(self, working_dir: str = "."):
        self.working_dir = working_dir
        self.system_prompt = DETAIL_PLANNER_SYSTEM_PROMPT

    def get_agent_definition(self) -> dict[str, Any]:
        """Return the agent definition for SDK."""
        return {
            "description": (
                "Expert architect that breaks"
                " implementation plans into small,"
                " self-contained parts."
            ),
            "prompt": self.system_prompt,
            "tools": ["Read", "Write", "Glob", "Grep"],
        }

    async def run(
        self,
        verbose: bool,
        plans_dir: str | Path = "plans",
        stream_handler: StreamHandler | None = None,
        include_partial: bool = False,
    ) -> DetailPlan | None:
        """Run the detail planner agent."""
        from ..message_processor import MessageProcessor

        prompt = (
            "Break the implementation plan into"
            " small, self-contained parts.\n\n"
            f"Working directory: {self.working_dir}\n\n"
            "IMPORTANT: First, read the plan:\n"
            f'1. Read "{plans_dir}/plan.md"\n\n'
            "Then explore the codebase as needed"
            " and produce the detailed parts.\n"
            "Write each part as a separate markdown"
            " file in the detail_plans/ directory.\n"
            "Also write a TODO.md checklist file"
            " in the same directory."
        )
        result_text = ""
        allowed_tools = ["Read", "Write", "Glob", "Grep", "Task"]
        processor = (
            MessageProcessor(stream_handler, "detail_planner")
            if stream_handler
            else None
        )
        try:
            opts = ClaudeAgentOptions(
                allowed_tools=allowed_tools,
                permission_mode="bypassPermissions",
                agents={
                    "detail_planner": AgentDefinition(
                        **self.get_agent_definition()
                    )
                },
            )
            if include_partial:
                opts.include_partial_messages = True

            async for message in query(prompt=prompt, options=opts):
                if processor:
                    await processor.process(message)
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        chunk = getattr(block, "text", None)
                        if chunk is None:
                            continue

                        result_text += chunk
                        if verbose and not stream_handler:
                            print(chunk, end="", flush=True)

                if not (
                    isinstance(message, ResultMessage)
                    and message.subtype == "success"
                ):
                    continue

                result_text = message.result or ""
                if verbose and not stream_handler:
                    print(message.result)

            result = _parse_detail_plan(result_text)
            if result is None and verbose:
                print("Failed to parse detail plan from agent output.")
            return result
        except Exception as e:
            if verbose:
                print(f"Error in detail planner: {e}")

            return None
