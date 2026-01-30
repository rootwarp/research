"""Researcher Agent - Gathers and analyzes requirements."""

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
class ResearchResult:
    """Research findings from the researcher agent."""

    original_requirements: str
    requirements_analysis: list[str] = field(
        default_factory=list,
    )
    research_agenda: list[str] = field(
        default_factory=list,
    )
    findings: list[dict] = field(
        default_factory=list,
    )
    technical_context: list[str] = field(
        default_factory=list,
    )
    recommendations: list[str] = field(
        default_factory=list,
    )
    notes: str = ""

    def save_to_dir(
        self, research_dir: str | Path,
    ) -> Path:
        """Save research result to a directory.

        Creates JSON and markdown files.

        Args:
            research_dir: Directory to save to.

        Returns:
            Path to the research directory.
        """
        path = Path(research_dir)
        path.mkdir(parents=True, exist_ok=True)

        json_path = path / "research.json"
        with open(json_path, "w") as f:
            json.dump(asdict(self), f, indent=2)

        md_path = path / "research.md"
        with open(md_path, "w") as f:
            f.write(self.to_prompt())

        return path

    @classmethod
    def load_from_dir(
        cls, research_dir: str | Path,
    ) -> ResearchResult:
        """Load research result from a directory.

        Args:
            research_dir: Directory with files.

        Returns:
            ResearchResult loaded from directory.
        """
        path = Path(research_dir)
        json_path = path / "research.json"

        with open(json_path) as f:
            data = json.load(f)

        return cls(**data)

    def to_prompt(self) -> str:
        """Convert to prompt for the planner."""
        sections = [
            "# Research Findings\n\n"
            "## Original Requirements\n"
            f"{self.original_requirements}"
        ]

        if self.requirements_analysis:
            items = "\n".join(
                f"- {r}"
                for r in self.requirements_analysis
            )
            sections.append(
                f"## Requirements Analysis\n{items}"
            )

        if self.research_agenda:
            items = "\n".join(
                f"{i + 1}. {item}"
                for i, item
                in enumerate(self.research_agenda)
            )
            sections.append(
                f"## Research Agenda\n{items}"
            )

        if self.findings:
            findings_text = []
            for finding in self.findings:
                topic = finding.get(
                    "topic", "Unknown",
                )
                summary = finding.get("summary", "")
                sources = finding.get("sources", [])
                text = f"### {topic}\n{summary}"
                if sources:
                    src = "\n".join(
                        f"- {s}" for s in sources
                    )
                    text += f"\n\nSources:\n{src}"
                findings_text.append(text)
            body = "\n\n".join(findings_text)
            sections.append(
                f"## Research Findings\n{body}"
            )

        if self.technical_context:
            items = "\n".join(
                f"- {t}"
                for t in self.technical_context
            )
            sections.append(
                f"## Technical Context\n{items}"
            )

        if self.recommendations:
            items = "\n".join(
                f"- {r}"
                for r in self.recommendations
            )
            sections.append(
                "## Recommendations for Planning\n"
                f"{items}"
            )

        if self.notes:
            sections.append(
                f"## Additional Notes\n{self.notes}"
            )

        return "\n\n".join(sections)


RESEARCHER_SYSTEM_PROMPT = """\
You are an expert requirements analyst \
and technical researcher.

Your job is to thoroughly understand and research \
requirements before any planning or implementation.

When given a task:

1. **Read and Extract Requirements**
   - If a GitHub issue is referenced, use GitHub \
MCP tools to read the full issue details
   - Use mcp__github__issue_read with method="get" \
to get the issue content
   - Use mcp__github__issue_read with \
method="get_comments" to read discussion
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
   - Use GitHub MCP tools to explore the codebase:
     - mcp__github__get_file_contents to read code
     - mcp__github__search_code to find related code
     - mcp__github__list_issues for related issues
   - Use Read, Glob, and Grep for local codebase
   - Use WebSearch for documentation and best \
practices
   - Use WebFetch to read specific documentation
   - Gather technical context about architecture

5. **Synthesize Findings**
   - Summarize learnings for each research topic
   - Document relevant existing code patterns
   - Identify potential challenges
   - Make recommendations for the planning phase

Output your research in a structured JSON format \
with these fields:
- original_requirements: The raw requirements text
- requirements_analysis: List of analyzed items
- research_agenda: List of research topics
- findings: List of {topic, summary, sources}
- technical_context: List of technical details
- recommendations: List of recommendations
- notes: Any additional context

Be thorough but focused. The goal is to provide \
the planner agent with all the context needed to \
create an accurate implementation plan."""


class ResearcherAgent:
    """Agent that gathers and analyzes requirements."""

    def __init__(self, working_dir: str = "."):
        self.working_dir = working_dir
        self.system_prompt = RESEARCHER_SYSTEM_PROMPT

    def get_agent_definition(self) -> dict:
        """Return the agent definition for SDK."""
        return {
            "description": (
                "Expert requirements analyst that "
                "researches and understands "
                "requirements before planning."
            ),
            "prompt": self.system_prompt,
            "tools": [
                "Read",
                "Glob",
                "Grep",
                "WebFetch",
                "WebSearch",
                "mcp__github__*",
            ],
        }

    async def run(
        self,
        task: str,
        verbose: bool,
        mcp_servers: dict | None = None,
        stream_handler: object | None = None,
        include_partial: bool = False,
        issue_url: str | None = None,
    ) -> ResearchResult | None:
        """Run the researcher agent.

        Args:
            task: Task description.
            verbose: Print progress messages.
            mcp_servers: MCP server config.
            stream_handler: Optional StreamHandler.
            include_partial: Enable partial msgs.
            issue_url: GitHub issue URL.

        Returns:
            ResearchResult or None on failure.
        """
        from ..message_processor import (
            MessageProcessor,
        )

        issue_instructions = ""
        if issue_url:
            match = re.match(
                r"https?://github\.com/"
                r"([^/]+)/([^/]+)/issues/(\d+)",
                issue_url,
            )
            if match:
                owner = match.group(1)
                repo = match.group(2)
                number = match.group(3)
                issue_instructions = (
                    "\nIMPORTANT: Start by reading "
                    "the GitHub issue:\n"
                    "- Use mcp__github__issue_read "
                    'with method="get", '
                    f'owner="{owner}", '
                    f'repo="{repo}", '
                    f"issue_number={number}\n"
                    "- Then use "
                    "mcp__github__issue_read "
                    'with method="get_comments", '
                    f'owner="{owner}", '
                    f'repo="{repo}", '
                    f"issue_number={number}\n\n"
                    "This is the primary source of "
                    "requirements for this task.\n"
                )

        researcher_prompt = (
            "Research and analyze the requirements"
            " for this coding task.\n\n"
            f"Task: {task}\n\n"
            f"Working directory: {self.working_dir}\n"
            f"{issue_instructions}"
            "Follow these steps:\n"
            "1. Read the GitHub issue details and "
            "all comments\n"
            "2. Analyze and break down all "
            "requirements step by step\n"
            "3. Create a research agenda\n"
            "4. Research the codebase and gather "
            "technical context\n"
            "5. Use web search for unfamiliar "
            "technologies or APIs\n"
            "6. Synthesize findings and provide "
            "recommendations\n\n"
            "Output your research in JSON format."
        )

        result_text = ""

        allowed_tools = [
            "Read", "Glob", "Grep", "Task",
            "WebFetch", "WebSearch",
        ]
        if mcp_servers:
            allowed_tools.append("mcp__github__*")

        processor = (
            MessageProcessor(
                stream_handler, "researcher",
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
                    "researcher": AgentDefinition(
                        **self.get_agent_definition()
                    )
                },
            )
            if include_partial:
                opts.include_partial_messages = True

            async for message in query(
                prompt=researcher_prompt,
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

            return self.parse_research_response(
                result_text,
            )

        except Exception as e:
            if verbose:
                print(f"Error in researcher: {e}")
            return None

    @staticmethod
    def parse_research_response(
        response: str,
    ) -> ResearchResult:
        """Parse response into a ResearchResult."""
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
                return ResearchResult(
                    original_requirements=(
                        response[:1000]
                    ),
                    notes=(
                        "Could not parse structured "
                        "research from response."
                    ),
                )

        try:
            data = json.loads(json_str)
            return ResearchResult(
                original_requirements=data.get(
                    "original_requirements", "",
                ),
                requirements_analysis=data.get(
                    "requirements_analysis", [],
                ),
                research_agenda=data.get(
                    "research_agenda", [],
                ),
                findings=data.get("findings", []),
                technical_context=data.get(
                    "technical_context", [],
                ),
                recommendations=data.get(
                    "recommendations", [],
                ),
                notes=data.get("notes", ""),
            )
        except json.JSONDecodeError:
            return ResearchResult(
                original_requirements=(
                    response[:1000]
                ),
                notes=(
                    "Could not parse JSON "
                    "from response."
                ),
            )
