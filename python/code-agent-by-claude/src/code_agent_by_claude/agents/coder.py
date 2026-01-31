"""Coder Agent - Implements code based on plans."""

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
class CodeResult:
    """Result of code implementation."""

    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    summary: str = ""
    success: bool = True
    errors: list[str] = field(default_factory=list)


CODER_SYSTEM_PROMPT = """\
You are an expert software engineer who writes clean, efficient, and well-documented code.

Your job is to implement code by iterating through the TODO checklist in `detail_plans/`.

Repeat the following cycle until every TODO item is marked done 
and every each task should be guarantted build and execute correctly:

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
                "Expert software engineer that"
                " implements code based on plans."
            ),
            "prompt": self.system_prompt,
            "tools": [
                "Read",
                "Write",
                "Edit",
                "Glob",
                "Grep",
                "Bash",
            ],
        }

    async def run(
        self,
        verbose: bool,
        plans_dir: str | Path = "plans",
        stream_handler: StreamHandler | None = None,
        include_partial: bool = False,
    ) -> CodeResult | None:
        """Run the coder agent."""
        from ..message_processor import MessageProcessor

        detail_plans = Path(plans_dir).parent / "detail_plans"
        coder_prompt = (
            "Implement code by iterating through"
            " the TODO checklist.\n\n"
            f"Working directory: {self.working_dir}\n\n"
            "Follow this cycle:\n"
            f'1. Read "{detail_plans}/TODO.md"\n'
            "2. Find the first unchecked item\n"
            "3. Read the matching detail plan file\n"
            "4. Implement the changes\n"
            "5. Run tests and fix failures\n"
            "6. Mark the item done in TODO.md\n"
            "7. Repeat until all items are done\n\n"
            "After all items are complete, provide"
            " a summary of what was done."
        )
        result_text = ""
        processor = (
            MessageProcessor(stream_handler, "coder")
            if stream_handler
            else None
        )
        try:
            opts = ClaudeAgentOptions(
                allowed_tools=[
                    "Read",
                    "Write",
                    "Edit",
                    "Glob",
                    "Grep",
                    "Bash",
                    "Task",
                ],
                permission_mode="acceptEdits",
                agents={
                    "coder": AgentDefinition(**self.get_agent_definition())
                },
            )
            if include_partial:
                opts.include_partial_messages = True
            async for message in query(prompt=coder_prompt, options=opts):
                if processor:
                    await processor.process(message)
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if hasattr(block, "text"):
                            result_text += block.text
                            if verbose and not stream_handler:
                                print(
                                    block.text,
                                    end="",
                                    flush=True,
                                )
                if (
                    isinstance(message, ResultMessage)
                    and message.subtype == "success"
                ):
                    result_text = message.result or ""
                    if verbose and not stream_handler:
                        print(message.result)
            return self.parse_result_response(result_text)
        except Exception as e:
            if verbose:
                print(f"Error in coder: {e}")
            return None

    @staticmethod
    def parse_result_response(
        response: str,
    ) -> CodeResult:
        """Parse response into a CodeResult."""
        json_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            try:
                data = json.loads(json_str)
                return CodeResult(
                    files_created=data.get("files_created", []),
                    files_modified=data.get("files_modified", []),
                    summary=data.get("summary", ""),
                    success=data.get("success", True),
                    errors=data.get("errors", []),
                )
            except json.JSONDecodeError:
                pass
        files_created = re.findall(
            r"[Cc]reated[:\s]+[`']?([^\s`']+)[`']?", response
        )
        files_modified = re.findall(
            r"[Mm]odified[:\s]+[`']?([^\s`']+)[`']?", response
        )
        summary = response[:1000] if len(response) > 1000 else response
        success = (
            "error" not in response.lower() or "success" in response.lower()
        )
        return CodeResult(
            files_created=files_created,
            files_modified=files_modified,
            summary=summary,
            success=success,
        )
