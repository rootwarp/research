"""Planner Agent - Creates implementation plans."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..stream_handler import StreamHandler

from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AgentDefinition,
    ResultMessage,
    AssistantMessage,
)


@dataclass
class Plan:
    """Implementation plan from the planner agent."""

    content: str

    def save_to_dir(self, plans_dir: str | Path) -> Path:
        """Save plan as markdown."""
        path = Path(plans_dir)
        path.mkdir(parents=True, exist_ok=True)
        with open(path / "plan.md", "w") as f:
            f.write(self.content)
        return path


PLANNER_SYSTEM_PROMPT = """\
You are an expert software architect and requirements analyst.

Your job is to analyze coding tasks and create \
detailed implementation plans based on research.

When given a task:
1. **Read the research materials** from the directory:
   - Read `research/research.md` for findings
   - The research contains requirements analysis, \
technical context, and recommendations

2. **Understand the requirements thoroughly**
   - Review the requirements analysis section
   - Consider technical context and patterns
   - Take into account recommendations

3. **Explore the existing codebase** if needed:
   - Use Read, Glob, and Grep tools

4. **Create an overall implementation plan**:
   - Identify files to create or modify
   - Identify dependencies or prerequisites
   - Break down into clear, actionable steps
   - Identify implementation phases to build the target application incrementally

Output your plan as a well-structured markdown document covering:
- Task description
- Requirements
- Files to create and modify
- Implementation steps (ordered)
- Dependencies
- Any additional notes

Focus on clarity and completeness.
The coder agent will read this plan to implement the solution."""


class PlannerAgent:
    """Agent that creates implementation plans."""

    def __init__(self, working_dir: str = "."):
        self.working_dir = working_dir
        self.system_prompt = PLANNER_SYSTEM_PROMPT

    def get_agent_definition(self) -> dict[str, Any]:
        """Return the agent definition for SDK."""
        return {
            "description": (
                "Expert software architect that analyzes requirements and"
                " creates overall implementation plans."
            ),
            "prompt": self.system_prompt,
            "tools": ["Read", "Glob", "Grep"],
        }

    async def run(
        self,
        verbose: bool,
        research_dir: str | Path = "research",
        stream_handler: StreamHandler | None = None,
        include_partial: bool = False,
    ) -> Plan | None:
        """Run the planner agent."""
        from ..message_processor import MessageProcessor

        planner_prompt = (
            "Create a detailed implementation plan for this coding task.\n\n"
            f"Working directory: {self.working_dir}/docs/plans\n\n"
            "IMPORTANT: First, read the research materials:\n"
            f'1. Read "{research_dir}/research.md" for research findings\n\n'
            "The research contains:\n"
            "- Original requirements\n"
            "- Requirements analysis\n"
            "- Technical context about the existing codebase\n"
            "- Recommendations from the researcher\n\n"
            "Based on the research findings, create a comprehensive implementation plan.\n"
            "If additional exploration is needed, use the available tools.\n"
            "Output your plan in markdown format."
        )
        result_text = ""
        prev_text_len = 0
        allowed_tools = [
            "Read", "Write", "Edit", "Glob", "Grep",
        ]
        processor = (
            MessageProcessor(
                stream_handler, "planner"
            )
            if stream_handler else None
        )
        try:
            opts = ClaudeAgentOptions(
                allowed_tools=allowed_tools,
                permission_mode="bypassPermissions",
                agents={
                    "planner": AgentDefinition(
                        **self.get_agent_definition()
                    )
                },
            )
            if include_partial:
                opts.include_partial_messages = True
            async for message in query(
                prompt=planner_prompt, options=opts
            ):
                if processor:
                    await processor.process(message)
                if isinstance(
                    message, AssistantMessage
                ):
                    full = ""
                    for block in message.content:
                        chunk = getattr(
                            block, "text", None
                        )
                        if chunk is not None:
                            full += chunk
                    if len(full) < prev_text_len:
                        prev_text_len = 0
                    if len(full) > prev_text_len:
                        delta = full[prev_text_len:]
                        prev_text_len = len(full)
                        result_text = full
                        if (
                            verbose
                            and not stream_handler
                        ):
                            print(
                                delta,
                                end="",
                                flush=True,
                            )

                if not (
                    isinstance(
                        message, ResultMessage
                    )
                    and message.subtype == "success"
                ):
                    continue

                result_text = message.result or ""
                if verbose and not stream_handler:
                    print(message.result)

            return Plan(content=result_text)
        except Exception as e:
            if verbose:
                print(f"Error in planner: {e}")
            return None
