"""Planner Agent - Creates implementation plans."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..stream_handler import StreamHandler

from claude_agent_sdk import (
    AgentDefinition, AssistantMessage,
    ClaudeAgentOptions, ResultMessage, query,
)

from .prompts import load_prompt


@dataclass
class Plan:
    """Implementation plan from the planner agent."""
    content: str

    def save_to_dir(
        self, plans_dir: str | Path,
    ) -> Path:
        """Save plan as markdown."""
        path = Path(plans_dir)
        path.mkdir(parents=True, exist_ok=True)
        with open(path / "plan.md", "w") as f:
            f.write(self.content)
        return path


class PlannerAgent:
    """Agent that creates implementation plans."""

    def __init__(self, working_dir: str = "."):
        self.working_dir = working_dir
        self.system_prompt = load_prompt("planner")

    def get_agent_definition(self) -> dict[str, Any]:
        """Return the agent definition for SDK."""
        return {
            "description": (
                "Expert software architect that"
                " analyzes requirements and creates"
                " overall implementation plans."
            ),
            "prompt": self.system_prompt,
            "tools": ["Read", "Glob", "Grep"],
        }

    async def run(
        self, verbose: bool,
        research_dir: str | Path = "research",
        stream_handler: StreamHandler | None = None,
        include_partial: bool = False,
    ) -> Plan | None:
        """Run the planner agent."""
        from ..message_processor import MessageProcessor

        wd = f"{self.working_dir}/docs/plans"
        prompt = load_prompt(
            "planner_task",
            working_dir=wd,
            research_dir=str(research_dir),
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
                prompt=prompt, options=opts
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
                        if (verbose
                                and not stream_handler):
                            print(
                                delta, end="",
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
