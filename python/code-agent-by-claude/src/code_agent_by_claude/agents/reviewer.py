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
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    query,
)


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

    def save_to_dir(self, reviews_dir: str | Path) -> Path:
        """Save review results to directory."""
        path = Path(reviews_dir)
        path.mkdir(parents=True, exist_ok=True)

        md_lines = [f"# Code Review\n\n{self.summary}\n"]
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
                    f"- **Issue**: {f.description}\n"
                    f"- **Suggestion**: {f.suggestion}\n"
                )
        else:
            md_lines.append("\nNo issues found.\n")

        status = "PASS" if self.passed else "FAIL"
        md_lines.append(f"\n---\n**Result**: {status}\n")

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


REVIEWER_SYSTEM_PROMPT = """\
You are an expert code reviewer. \
Review the implemented code thoroughly against \
the plan and established best practices.

You will review the following areas, in priority order:

1. **Code Convention**:
   - Naming, formatting, project style consistency
   - Adherence to language idioms (e.g., PEP-8 for Python)

2. **Code Quality** (Readability > Performance):
   - Clarity and maintainability first
   - Unnecessary complexity or over-engineering
   - Performance only where it clearly matters

3. **Unit Test Quality & Coverage**:
   - Tests exist for new/changed code
   - Edge cases and error paths are covered
   - Tests are readable and well-structured
   - Mocking is appropriate, not excessive

4. **Potential Bugs**:
   - Off-by-one errors, null/None handling
   - Race conditions, resource leaks
   - Incorrect logic or missing error handling

5. **Security Vulnerabilities**:
   - Injection risks (SQL, command, XSS)
   - Hardcoded secrets or credentials
   - Insecure deserialization or file handling
   - Missing input validation at boundaries

## Process

1. Read `detail_plans/TODO.md` to understand what was implemented
2. Read the detail plan files to understand intent
3. Explore the implemented code using Read, Glob, Grep
4. Run tests with Bash to verify they pass
5. Produce your review

## Output Format

Respond with a JSON block:

```json
{
  "passed": true,
  "summary": "Overall assessment in 2-3 sentences.",
  "findings": [
    {
      "category": "convention|quality|testing|bug|security",
      "severity": "info|warning|error|critical",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is.",
      "suggestion": "How to fix it."
    }
  ]
}
```

If there are no `error` or `critical` findings, \
set `passed` to `true`. Otherwise set it to `false`.
"""


def _parse_review(text: str) -> ReviewResult | None:
    """Parse JSON review output into ReviewResult."""
    if not text or not text.strip():
        return None

    json_match = re.search(
        r"```json\s*(.*?)\s*```", text, re.DOTALL
    )
    raw = json_match.group(1) if json_match else text

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None

    findings = []
    for item in data.get("findings", []):
        findings.append(
            ReviewFinding(
                category=item.get("category", ""),
                severity=item.get("severity", "info"),
                file=item.get("file", ""),
                line=item.get("line"),
                description=item.get("description", ""),
                suggestion=item.get("suggestion", ""),
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
        self.system_prompt = REVIEWER_SYSTEM_PROMPT

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
        self,
        verbose: bool,
        stream_handler: StreamHandler | None = None,
        include_partial: bool = False,
    ) -> ReviewResult | None:
        """Run the reviewer agent."""
        from ..message_processor import MessageProcessor

        prompt = (
            "Review the implemented code.\n\n"
            f"Working directory: {self.working_dir}\n\n"
            "Steps:\n"
            '1. Read "detail_plans/TODO.md"\n'
            "2. Read each detail plan file\n"
            "3. Explore and review the code changes\n"
            "4. Run tests with: pytest\n"
            "5. Produce your JSON review\n"
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
            if stream_handler
            else None
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
                    await processor.process(
                        message
                    )
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
