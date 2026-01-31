"""Reviewer Agent - Reviews implemented code."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
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
class ReviewFinding:
    """A single review finding."""
    category: str
    severity: str
    file: str
    line: int | None
    description: str
    suggestion: str


@dataclass
class ReviewResult:
    """Result of code review."""
    findings: list[ReviewFinding] = field(
        default_factory=list
    )
    summary: str = ""
    passed: bool = True

    def save_to_dir(
        self, reviews_dir: str | Path,
    ) -> Path:
        """Save review results to directory."""
        path = Path(reviews_dir)
        path.mkdir(parents=True, exist_ok=True)
        md_lines = [
            f"# Code Review\n\n{self.summary}\n"
        ]
        if self.findings:
            md_lines.append("\n## Findings\n")
            for f in self.findings:
                loc = f.file
                if f.line:
                    loc += f":{f.line}"
                md_lines.append(
                    f"### [{f.severity.upper()}]"
                    f" {f.category}\n\n"
                    f"- **Location**: `{loc}`\n"
                    f"- **Issue**:"
                    f" {f.description}\n"
                    f"- **Suggestion**:"
                    f" {f.suggestion}\n"
                )
        else:
            md_lines.append("\nNo issues found.\n")
        status = "PASS" if self.passed else "FAIL"
        md_lines.append(
            f"\n---\n**Result**: {status}\n"
        )
        with open(path / "review.md", "w") as fh:
            fh.write("\n".join(md_lines))
        data = {
            "passed": self.passed,
            "summary": self.summary,
            "findings": [
                {
                    "category": f.category,
                    "severity": f.severity,
                    "file": f.file,
                    "line": f.line,
                    "description": f.description,
                    "suggestion": f.suggestion,
                }
                for f in self.findings
            ],
        }
        with open(path / "review.json", "w") as fh:
            json.dump(data, fh, indent=2)
        return path


def _parse_review(
    text: str,
) -> ReviewResult | None:
    """Parse JSON review output."""
    if not text or not text.strip():
        return None
    json_match = re.search(
        r"```json\s*(.*?)\s*```",
        text, re.DOTALL,
    )
    raw = (
        json_match.group(1)
        if json_match else text
    )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    findings = []
    for item in data.get("findings", []):
        findings.append(
            ReviewFinding(
                category=item.get("category", ""),
                severity=item.get(
                    "severity", "info"
                ),
                file=item.get("file", ""),
                line=item.get("line"),
                description=item.get(
                    "description", ""
                ),
                suggestion=item.get(
                    "suggestion", ""
                ),
            )
        )
    return ReviewResult(
        findings=findings,
        summary=data.get("summary", ""),
        passed=data.get("passed", True),
    )


class ReviewerAgent:
    """Agent that reviews implemented code."""

    def __init__(self, working_dir: str = "."):
        self.working_dir = working_dir
        self.system_prompt = load_prompt("reviewer")

    def get_agent_definition(self) -> dict[str, Any]:
        """Return the agent definition for SDK."""
        return {
            "description": (
                "Expert code reviewer that checks"
                " convention, quality, tests, bugs,"
                " and security."
            ),
            "prompt": self.system_prompt,
            "tools": [
                "Read", "Glob", "Grep", "Bash",
            ],
        }

    async def run(
        self, verbose: bool,
        stream_handler: StreamHandler | None = None,
        include_partial: bool = False,
    ) -> ReviewResult | None:
        """Run the reviewer agent."""
        from ..message_processor import MessageProcessor

        prompt = load_prompt(
            "reviewer_task",
            working_dir=self.working_dir,
            detail_plans_dir="detail_plans",
        )
        result_text = ""
        prev_text_len = 0
        allowed_tools = [
            "Read", "Glob", "Grep", "Bash", "Task",
        ]
        processor = (
            MessageProcessor(
                stream_handler, "reviewer"
            )
            if stream_handler else None
        )
        try:
            opts = ClaudeAgentOptions(
                allowed_tools=allowed_tools,
                permission_mode="bypassPermissions",
                agents={
                    "reviewer": AgentDefinition(
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
            result = _parse_review(result_text)
            if result is None and verbose:
                print(
                    "Failed to parse review"
                    " from agent output."
                )
            return result
        except Exception as e:
            if verbose:
                print(f"Error in reviewer: {e}")
            return None
