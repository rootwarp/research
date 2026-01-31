"""Researcher Agent - Gathers and analyzes requirements."""

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

from ..message_processor import MessageProcessor
from .prompts import load_prompt


@dataclass
class ResearchResult:
    """Research findings from the researcher agent."""
    content: str


class ResearcherAgent:
    """Agent that analyzes requirements."""

    def __init__(self, working_dir: str = "."):
        self.working_dir = working_dir
        self.system_prompt = load_prompt("researcher")

    def get_agent_definition(self) -> dict[str, Any]:
        """Return the agent definition for SDK."""
        return {
            "description": (
                "Expert requirements analyst that"
                " researches and understands"
                " requirements before planning."
            ),
            "prompt": self.system_prompt,
            "tools": [
                "Read", "Glob", "Grep",
                "WebFetch", "WebSearch",
            ],
        }

    async def run(
        self, task: str, verbose: bool,
        stream_handler: StreamHandler | None = None,
        include_partial: bool = False,
    ) -> ResearchResult | None:
        """Run the researcher agent."""
        research_dir = (
            Path(self.working_dir) / "docs" / "research"
        )
        prompt = load_prompt(
            "researcher_task",
            task=task,
            working_dir=self.working_dir,
            research_dir=str(research_dir),
        )
        result_text = ""
        prev_text_len = 0
        allowed_tools = [
            "Read", "Glob", "Grep",
            "WebFetch", "WebSearch",
        ]
        processor = (
            MessageProcessor(
                stream_handler, "researcher"
            )
            if stream_handler else None
        )
        try:
            defn = self.get_agent_definition()
            opts = ClaudeAgentOptions(
                allowed_tools=allowed_tools,
                permission_mode="bypassPermissions",
                model="opus",
                agents={
                    "researcher": AgentDefinition(
                        **defn
                    ),
                },
            )
            if include_partial:
                opts.include_partial_messages = True
            async for msg in query(
                prompt=prompt, options=opts
            ):
                if processor:
                    await processor.process(msg)
                if isinstance(msg, AssistantMessage):
                    full = ""
                    for blk in msg.content:
                        txt = getattr(
                            blk, "text", None
                        )
                        if txt is not None:
                            full += txt
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
                is_success = (
                    isinstance(msg, ResultMessage)
                    and msg.subtype == "success"
                )
                if is_success:
                    result_text = msg.result or ""
                    if verbose and not stream_handler:
                        print(msg.result)
            return ResearchResult(content=result_text)
        except Exception as e:
            if verbose:
                print(f"Error in researcher: {e}")
            return None
