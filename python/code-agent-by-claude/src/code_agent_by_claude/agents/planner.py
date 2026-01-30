"""Planner Agent - Creates implementation plans."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path

from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AgentDefinition,
    ResultMessage,
    SystemMessage,
    AssistantMessage,
)


@dataclass
class Plan:
    """Implementation plan from the planner agent."""

    task_description: str
    requirements: list[str] = field(
        default_factory=list,
    )
    files_to_create: list[str] = field(
        default_factory=list,
    )
    files_to_modify: list[str] = field(
        default_factory=list,
    )
    implementation_steps: list[str] = field(
        default_factory=list,
    )
    dependencies: list[str] = field(
        default_factory=list,
    )
    notes: str = ""

    def save_to_dir(
        self, plans_dir: str | Path,
    ) -> Path:
        """Save plan to a directory.

        Creates JSON and markdown files.

        Args:
            plans_dir: Directory to save to.

        Returns:
            Path to the plans directory.
        """
        path = Path(plans_dir)
        path.mkdir(parents=True, exist_ok=True)

        json_path = path / "plan.json"
        with open(json_path, "w") as f:
            json.dump(asdict(self), f, indent=2)

        md_path = path / "plan.md"
        with open(md_path, "w") as f:
            f.write(self.to_prompt())

        return path

    @classmethod
    def load_from_dir(
        cls, plans_dir: str | Path,
    ) -> Plan:
        """Load plan from a directory.

        Args:
            plans_dir: Directory with plan files.

        Returns:
            Plan loaded from directory.
        """
        path = Path(plans_dir)
        json_path = path / "plan.json"

        with open(json_path) as f:
            data = json.load(f)

        return cls(**data)

    def to_prompt(self) -> str:
        """Convert to prompt for the coder agent."""
        sections = [
            "# Implementation Plan\n\n"
            "## Task\n"
            f"{self.task_description}"
        ]

        if self.requirements:
            items = "\n".join(
                f"- {r}" for r in self.requirements
            )
            sections.append(
                f"## Requirements\n{items}"
            )

        if self.files_to_create:
            items = "\n".join(
                f"- {f}" for f in self.files_to_create
            )
            sections.append(
                f"## Files to Create\n{items}"
            )

        if self.files_to_modify:
            items = "\n".join(
                f"- {f}" for f in self.files_to_modify
            )
            sections.append(
                f"## Files to Modify\n{items}"
            )

        if self.implementation_steps:
            items = "\n".join(
                f"{i + 1}. {step}"
                for i, step
                in enumerate(
                    self.implementation_steps,
                )
            )
            sections.append(
                f"## Implementation Steps\n{items}"
            )

        if self.dependencies:
            items = "\n".join(
                f"- {d}" for d in self.dependencies
            )
            sections.append(
                f"## Dependencies\n{items}"
            )

        if self.notes:
            sections.append(
                f"## Notes\n{self.notes}"
            )

        return "\n\n".join(sections)


PLANNER_SYSTEM_PROMPT = """\
You are an expert software architect and \
requirements analyst.

Your job is to analyze coding tasks and create \
detailed implementation plans based on research.

When given a task:
1. **Read the research materials** from the \
research directory:
   - Read `research/research.md` for findings
   - Read `research/research.json` for data
   - The research contains requirements analysis, \
technical context, and recommendations

2. **Understand the requirements thoroughly**
   - Review the requirements analysis section
   - Consider technical context and patterns
   - Take into account recommendations

3. **Explore the existing codebase** if needed:
   - Use Read, Glob, and Grep tools
   - If GitHub context is needed, use MCP tools

4. **Create a detailed implementation plan**:
   - Identify files to create or modify
   - Break down into clear, actionable steps
   - Identify dependencies or prerequisites

Output your plan in a structured JSON format \
with these fields:
- task_description: Brief summary of the work
- requirements: List of functional requirements
- files_to_create: List of new files
- files_to_modify: List of existing files
- implementation_steps: Ordered steps
- dependencies: Any external dependencies
- notes: Additional context or considerations

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
                "detailed implementation plans."
            ),
            "prompt": self.system_prompt,
            "tools": [
                "Read",
                "Glob",
                "Grep",
                "mcp__github__*",
            ],
        }

    async def run(
        self,
        task: str,
        verbose: bool,
        research_dir: str | Path = "research",
        mcp_servers: dict | None = None,
        stream_handler: object | None = None,
        include_partial: bool = False,
    ) -> Plan | None:
        """Run the planner agent.

        Args:
            task: Task description.
            verbose: Print progress messages.
            research_dir: Path to research output.
            mcp_servers: MCP server config.
            stream_handler: Optional StreamHandler.
            include_partial: Enable partial msgs.

        Returns:
            Plan or None on failure.
        """
        from ..message_processor import (
            MessageProcessor,
        )

        planner_prompt = (
            "Create a detailed implementation plan "
            "for this coding task.\n\n"
            f"Task: {task}\n\n"
            f"Working directory: {self.working_dir}"
            "\n\n"
            "IMPORTANT: First, read the research "
            "materials:\n"
            f'1. Read "{research_dir}/research.md" '
            "for human-readable findings\n"
            f'2. Optionally read "{research_dir}/'
            'research.json" for structured data\n\n'
            "The research contains:\n"
            "- Original requirements from the "
            "GitHub issue\n"
            "- Requirements analysis\n"
            "- Technical context about the existing "
            "codebase\n"
            "- Recommendations from the researcher"
            "\n\n"
            "Based on the research findings, create "
            "a comprehensive implementation plan.\n"
            "If additional exploration is needed, "
            "use the available tools.\n"
            "Output your plan in JSON format."
        )

        result_text = ""

        allowed_tools = [
            "Read", "Glob", "Grep", "Task",
        ]
        if mcp_servers:
            allowed_tools.append("mcp__github__*")

        processor = (
            MessageProcessor(
                stream_handler, "planner",
            )
            if stream_handler
            else None
        )

        try:
            opts = ClaudeAgentOptions(
                allowed_tools=allowed_tools,
                permission_mode="bypassPermissions",
                mcp_servers=(
                    mcp_servers
                    if mcp_servers
                    else None
                ),
                agents={
                    "planner": AgentDefinition(
                        **self.get_agent_definition()
                    )
                },
            )
            if include_partial:
                opts.include_partial_messages = True

            async for message in query(
                prompt=planner_prompt,
                options=opts,
            ):
                if processor:
                    await processor.process(message)

                if (
                    isinstance(message, SystemMessage)
                    and message.subtype == "init"
                ):
                    from . import warn_mcp
                    warn_mcp(message, verbose)

                if isinstance(
                    message, AssistantMessage
                ):
                    for block in message.content:
                        if hasattr(block, "text"):
                            result_text += block.text
                            if (
                                verbose
                                and not stream_handler
                            ):
                                print(
                                    block.text,
                                    end="",
                                    flush=True,
                                )

                if (
                    isinstance(message, ResultMessage)
                    and message.subtype == "success"
                ):
                    result_text = message.result
                    if (
                        verbose
                        and not stream_handler
                    ):
                        print(message.result)

            return self.parse_plan_response(
                result_text,
            )

        except Exception as e:
            if verbose:
                print(f"Error in planner: {e}")
            return None

    @staticmethod
    def parse_plan_response(
        response: str,
    ) -> Plan:
        """Parse response into a Plan object."""
        json_match = re.search(
            r"```json\s*(.*?)\s*```",
            response,
            re.DOTALL,
        )
        if json_match:
            json_str = json_match.group(1)
        else:
            json_match = re.search(
                r"\{.*\}", response, re.DOTALL,
            )
            if json_match:
                json_str = json_match.group(0)
            else:
                return Plan(
                    task_description=(
                        response[:500]
                    ),
                    notes=(
                        "Could not parse structured "
                        "plan from response."
                    ),
                )

        try:
            data = json.loads(json_str)
            return Plan(
                task_description=data.get(
                    "task_description", "",
                ),
                requirements=data.get(
                    "requirements", [],
                ),
                files_to_create=data.get(
                    "files_to_create", [],
                ),
                files_to_modify=data.get(
                    "files_to_modify", [],
                ),
                implementation_steps=data.get(
                    "implementation_steps", [],
                ),
                dependencies=data.get(
                    "dependencies", [],
                ),
                notes=data.get("notes", ""),
            )
        except json.JSONDecodeError:
            return Plan(
                task_description=response[:500],
                notes=(
                    "Could not parse JSON "
                    "from response."
                ),
            )
