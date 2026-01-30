"""Researcher Agent - Gathers and analyzes requirements."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from claude_agent_sdk import (
    query, ClaudeAgentOptions, AgentDefinition,
    ResultMessage, AssistantMessage,
)

from ..message_processor import MessageProcessor


@dataclass
class ResearchResult:
    """Research findings from the researcher agent."""
    content: str

    def save_to_dir(self, research_dir: str | Path) -> Path:
        """Save research result as markdown."""
        path = Path(research_dir)
        path.mkdir(parents=True, exist_ok=True)
        with open(path / "research.md", "w") as f:
            f.write(self.content)
        return path


RESEARCHER_SYSTEM_PROMPT = """\
You are an expert requirements analyst and technical researcher.

Your job is to thoroughly understand and research \
requirements before any planning or implementation.

When given a task:

1. **Read and Extract Requirements**
   - Extract all explicit and implicit requirements

2. **Analyze Requirements Step by Step**
   - Break down into distinct, actionable items
   - Identify ambiguities or missing information
   - Note constraints or acceptance criteria
   - Think through dependencies between requirements

3. **Create a Research Agenda**
   - Identify topics needing research
   - List technical concepts needing clarification
   - Note external APIs, libraries, or services

4. **Conduct Research**
   - Use Read, Glob, and Grep for local codebase
   - Use WebSearch for documentation and best practices
   - Use WebFetch to read specific documentation
   - Gather technical context about architecture

5. **Synthesize Findings**
   - Summarize learnings for each research topic
   - Document relevant existing code patterns
   - Identify potential challenges
   - Make recommendations for the planning phase

Output your research as a well-structured markdown document \
covering:
- Original requirements
- Requirements analysis
- Research agenda and findings
- Technical context
- Recommendations for the planning phase

Be thorough but focused. The goal is to provide the planner \
agent with all the context needed to create an accurate \
implementation plan.
"""


class ResearcherAgent:
    """Agent that analyzes requirements."""

    def __init__(self, working_dir: str = "."):
        self.working_dir = working_dir
        self.system_prompt = RESEARCHER_SYSTEM_PROMPT

    def get_agent_definition(self) -> dict:
        """Return the agent definition for SDK."""
        return {
            "description": (
                "Expert requirements analyst that researches and understands"
                " requirements before planning."),
            "prompt": self.system_prompt,
            "tools": ["Read", "Glob", "Grep", "WebFetch", "WebSearch"],
        }

    async def run(
        self, task: str, verbose: bool,
        stream_handler: object | None = None,
        include_partial: bool = False,
    ) -> ResearchResult | None:
        """Run the researcher agent."""
        prompt = (
            "Research and analyze the requirements for this coding task.\n\n"
            f"Task: {task}\n\n"
            f"Working directory: {self.working_dir}\n"
            "Follow these steps:\n"
            "1. Analyze and break down all requirements step by step\n"
            "2. Create a research agenda\n"
            "3. Research the codebase and gather technical context\n"
            "4. Use web search for unfamiliar technologies or APIs\n"
            "5. Synthesize findings and provide recommendations\n\n"
            "Output your research in markdown format."
        )
        result_text = ""
        allowed_tools = [
            "Read", "Glob", "Grep", "Task", "WebFetch", "WebSearch",
        ]
        processor = (
            MessageProcessor(stream_handler, "researcher")
            if stream_handler else None)
        try:
            defn = self.get_agent_definition()
            opts = ClaudeAgentOptions(
                allowed_tools=allowed_tools,
                permission_mode="bypassPermissions",
                model="opus",
                agents={
                    "researcher": AgentDefinition(**defn)
                },
            )
            if include_partial:
                opts.include_partial_messages = True

            async for msg in query(prompt=prompt, options=opts):
                if processor:
                    await processor.process(msg)
                if isinstance(msg, AssistantMessage):
                    for blk in msg.content:
                        chunk = getattr(blk, "text", None)
                        if chunk is None:
                            continue
                        result_text += chunk
                        if verbose and not stream_handler:
                            print(chunk, end="", flush=True)

                if (isinstance(msg, ResultMessage) and msg.subtype == "success"):
                    result_text = msg.result
                    if verbose and not stream_handler:
                        print(msg.result)

            result = ResearchResult(content=result_text)
            research_dir = (
                Path(self.working_dir) / "research")
            result.save_to_dir(research_dir)
            if verbose:
                print(
                    f"\nResearch saved to:"
                    f" {research_dir / 'research.md'}")
            return result
        except Exception as e:
            if verbose:
                print(f"Error in researcher: {e}")
            return None

