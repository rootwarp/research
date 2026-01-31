"""Detail Planner Agent - Breaks plans into parts."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..stream_handler import StreamHandler

from claude_agent_sdk import (
    AgentDefinition, AssistantMessage,
    ClaudeAgentOptions, ResultMessage, query,
)

from .prompts import load_prompt

_DETAIL_PLANS_DIR = "detail_plans"


class DetailPlannerAgent:
    """Agent that breaks plans into detailed parts."""

    def __init__(self, working_dir: str = "."):
        self.working_dir = working_dir
        self.system_prompt = load_prompt("detail_planner")

    def get_agent_definition(self) -> dict[str, Any]:
        """Return the agent definition for SDK."""
        return {
            "description": (
                "Expert architect that breaks implementation plans into small,"
                " self-contained parts."
            ),
            "prompt": self.system_prompt,
            "tools": ["Read", "Write", "Glob", "Grep"],
        }

    async def run(
        self, verbose: bool,
        plans_dir: str | Path = "plans",
        stream_handler: StreamHandler | None = None,
        include_partial: bool = False,
    ) -> bool:
        """Run the detail planner agent.

        Returns:
            True if the agent completed successfully.
        """
        from ..message_processor import MessageProcessor

        prompt = load_prompt(
            "detail_planner_task",
            working_dir=self.working_dir,
            plans_dir=str(plans_dir),
            detail_plans_dir=_DETAIL_PLANS_DIR,
        )
        allowed_tools = [
            "Read", "Write", "Glob", "Grep", "Task",
        ]
        processor = (
            MessageProcessor(stream_handler, "detail_planner")
            if stream_handler else None
        )
        success = False
        prev_text_len = 0
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
                    full = ""
                    for block in message.content:
                        chunk = getattr(block, "text", None)
                        if chunk is not None:
                            full += chunk

                    if len(full) < prev_text_len:
                        prev_text_len = 0
                    if (len(full) > prev_text_len and verbose
                        and not stream_handler):
                        print(full[prev_text_len:], end="", flush=True)
                        prev_text_len = len(full)
                if (isinstance(message, ResultMessage)
                        and message.subtype == "success"):
                    success = True
                    if verbose and not stream_handler:
                        print(message.result)
            return success
        except Exception as e:
            if verbose:
                print(f"Error in detail planner: {e}")
            return False
