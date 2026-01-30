"""Planner Agent - Creates implementation plans."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from claude_agent_sdk import (
    query, ClaudeAgentOptions, AgentDefinition,
    ResultMessage, AssistantMessage,
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

4. **Create a detailed implementation plan**:
   - Identify files to create or modify
   - Break down into clear, actionable steps
   - Identify dependencies or prerequisites

Output your plan as a well-structured markdown document covering:
- Task description
- Requirements
- Files to create and modify
- Implementation steps (ordered)
- Dependencies
- Any additional notes

Focus on clarity and completeness. The coder \
agent will read this plan to implement the \
solution."""


class PlannerAgent:
    """Agent that creates implementation plans."""

    def __init__(self, working_dir: str = "."):
        self.working_dir = working_dir
        self.system_prompt = PLANNER_SYSTEM_PROMPT

    def get_agent_definition(self) -> dict:
        """Return the agent definition for SDK."""
        return {
            "description": (
                "Expert software architect that "
                "analyzes requirements and creates "
                "detailed implementation plans."),
            "prompt": self.system_prompt,
            "tools": ["Read", "Glob", "Grep"],
        }

    async def run(
        self, verbose: bool,
        research_dir: str | Path = "research",
        stream_handler: object | None = None,
        include_partial: bool = False,
    ) -> Plan | None:
        """Run the planner agent."""
        from ..message_processor import MessageProcessor
        planner_prompt = (
            "Create a detailed implementation plan for this coding task.\n\n"
            f"Working directory: {self.working_dir}\n\n"
            "IMPORTANT: First, read the research materials:\n"
            f'1. Read "{research_dir}/research.md" for research findings\n\n'
            "The research contains:\n"
            "- Original requirements\n"
            "- Requirements analysis\n"
            "- Technical context about the existing "
            "codebase\n"
            "- Recommendations from the researcher\n\n"
            "Based on the research findings, "
            "create a comprehensive implementation plan.\n"
            "If additional exploration is needed, use the available tools.\n"
            "Output your plan in markdown format."
        )
        result_text = ""
        allowed_tools = ["Read", "Glob", "Grep", "Task"]
        processor = (
            MessageProcessor(stream_handler, "planner")
            if stream_handler else None)
        try:
            opts = ClaudeAgentOptions(
                allowed_tools=allowed_tools,
                permission_mode="bypassPermissions",
                agents={
                    "planner": AgentDefinition(**self.get_agent_definition())
                },
            )
            if include_partial:
                opts.include_partial_messages = True
            async for message in query(
                prompt=planner_prompt, options=opts):
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

                if not (isinstance(message, ResultMessage)
                        and message.subtype == "success"):
                    continue

                result_text = message.result
                if verbose and not stream_handler:
                    print(message.result)

            result = Plan(content=result_text)
            plans_dir = "/".join([(Path(self.working_dir) / "plans")])
            result.save_to_dir(plans_dir)

            if verbose:
                print(f"\nPlan saved to: {plans_dir / 'plan.md'}")

            return result
        except Exception as e:
            if verbose:
                print(f"Error in planner: {e}")

            return None
