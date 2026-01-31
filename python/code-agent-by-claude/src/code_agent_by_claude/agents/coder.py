"""Coder Agent - Implements code based on plans."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..stream_handler import StreamHandler

from claude_agent_sdk import (
    query, ClaudeAgentOptions, AgentDefinition,
    ResultMessage, AssistantMessage,
)

logger = logging.getLogger(__name__)

FILE_PATH_RE = re.compile(r"[\w./\\][\w./\\-]+\.\w+")


@dataclass
class CodeResult:
    """Result of code implementation."""
    files_created: list[str] = field(
        default_factory=list)
    files_modified: list[str] = field(
        default_factory=list)
    summary: str = ""
    success: bool = True
    errors: list[str] = field(default_factory=list)


CODER_SYSTEM_PROMPT = """\
You are an expert software engineer who writes clean, efficient, and well-documented code.

Your job is to implement code by iterating through the TODO checklist in `detail_plans/`.

Repeat the following cycle until every TODO item is marked done 
and every task is guaranteed to build and execute correctly:

1. **Read the TODO checklist**:
   - Read `detail_plans/TODO.md`
   - Find the first unchecked item (`- [ ]`)

2. **Read the relevant plan file**:
   - Open the corresponding detail plan file (e.g., `detail_plans/01_add_data_models.md`)
   - Understand the scope, files, changes, and side effects described

3. **Implement the plan**:
   - Write clean, readable code with comments
   - Follow the project's existing code style
   - Create or modify files as specified
   - Ensure proper error handling

4. **Run tests**:
   - Execute the relevant test suite
   - Fix any failures before proceeding

5. **Update the TODO checklist**:
   - Mark the completed item as done (`- [x]`) in `detail_plans/TODO.md`

6. **Loop back to step 1** and continue with the next unchecked item.

After all items are done:
- Summarize what was created/modified
- Note any deviations from the plan and why
- List any remaining considerations

Focus on quality and correctness. Implement exactly what each plan file specifies.
"""


class CoderAgent:
    """Agent that implements code based on plans."""

    def __init__(self, working_dir: str = "."):
        self.working_dir = working_dir
        self.system_prompt = CODER_SYSTEM_PROMPT

    def get_agent_definition(self) -> dict[str, Any]:
        """Return the agent definition for SDK."""
        return {
            "description": (
                "Expert software engineer that implements code based on plans."
            ),
            "prompt": self.system_prompt,
            "tools": ["Read", "Write", "Edit", "Glob", "Grep", "Bash", "Task"],
        }

    async def run(
        self, verbose: bool,
        plans_dir: str | Path = "plans",
        stream_handler: StreamHandler | None = None,
        include_partial: bool = False,
    ) -> CodeResult | None:
        """Run the coder agent."""
        from ..message_processor import MessageProcessor
        detail_plans = (
            Path(plans_dir).parent / "detail_plans"
        )
        coder_prompt = (
            "Implement code by iterating through the TODO checklist.\n\n"
            f"Working directory: {self.working_dir}\n\n"
            "Follow this cycle:\n"
            f'1. Read "{detail_plans}/TODO.md"\n'
            "2. Find the first unchecked item\n"
            "3. Read the matching detail plan\n"
            "4. Implement the changes\n"
            "5. Run tests and fix failures\n"
            "6. Mark the item done in TODO.md\n"
            "7. Repeat until all items done\n\n"
            "After all items are complete, provide a summary of what was done."
        )
        result_text = ""
        prev_text_len = 0
        processor = (
            MessageProcessor(
                stream_handler, "coder"
            )
            if stream_handler else None
        )
        try:
            defn = self.get_agent_definition()
            opts = ClaudeAgentOptions(
                allowed_tools=[
                    "Read", "Write", "Edit",
                    "Glob", "Grep", "Bash", "Task",
                ],
                permission_mode="acceptEdits",
                agents={
                    "coder": AgentDefinition(
                        **defn
                    ),
                },
            )
            if include_partial:
                opts.include_partial_messages = True
            async for msg in query(
                prompt=coder_prompt, options=opts
            ):
                if processor:
                    await processor.process(msg)

                if isinstance(
                    msg, AssistantMessage
                ):
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
                        if (
                            verbose
                            and not stream_handler
                        ):
                            print(
                                delta,
                                end="",
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

            return self._parse_result(result_text)
        except Exception as e:
            logger.exception("Error in coder: %s", e)
            if verbose:
                print(f"Error in coder: {e}")
            return None

    @staticmethod
    def _parse_result(response: str) -> CodeResult:
        """Parse response into a CodeResult."""
        json_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                return CodeResult(
                    files_created=data.get("files_created", []),
                    files_modified=data.get("files_modified", []),
                    summary=data.get("summary", ""),
                    success=data.get("success", True),
                    errors=data.get("errors", []),
                )
            except json.JSONDecodeError:
                pass
        created = re.findall(r"[Cc]reated:\s*`([^`]+)`", response)
        modified = re.findall(r"[Mm]odified:\s*`([^`]+)`", response)
        summary = response[:1000]
        has_error = re.search(r"\berrors?\b", response, re.IGNORECASE)
        has_success = re.search(r"\bsuccess\b", response, re.IGNORECASE)
        success = not has_error or bool(has_success)

        return CodeResult(
            files_created=created,
            files_modified=modified,
            summary=summary, success=success,
        )
