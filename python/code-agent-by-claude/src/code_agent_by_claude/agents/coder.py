"""Coder Agent - Implements code based on plans."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AgentDefinition,
    ResultMessage,
    AssistantMessage,
)


@dataclass
class CodeResult:
    """Result of code implementation."""

    files_created: list[str] = field(
        default_factory=list,
    )
    files_modified: list[str] = field(
        default_factory=list,
    )
    summary: str = ""
    success: bool = True
    errors: list[str] = field(
        default_factory=list,
    )


CODER_SYSTEM_PROMPT = """\
You are an expert software engineer who writes \
clean, efficient, and well-documented code.

Your job is to implement code based on the \
implementation plan stored in the plans directory.

When starting implementation:
1. **Read the plan** from the plans directory:
   - Read `plans/plan.md` for the plan
   - Read `plans/plan.json` for structured data
   - The plan contains task description, \
requirements, files to create/modify, and steps

2. **Follow the implementation steps in order**
3. Write clean, readable code with comments
4. Follow the project's existing code style
5. Create all necessary files per the plan
6. Ensure proper error handling
7. Write code that is testable and maintainable

After completing the implementation:
- Summarize what was created/modified
- Note any deviations from the plan and why
- List any remaining tasks or considerations

Focus on quality and correctness. Implement \
exactly what the plan specifies."""


class CoderAgent:
    """Agent that implements code based on plans."""

    def __init__(self, working_dir: str = "."):
        self.working_dir = working_dir
        self.system_prompt = CODER_SYSTEM_PROMPT

    def get_agent_definition(self) -> dict:
        """Return the agent definition for SDK."""
        return {
            "description": (
                "Expert software engineer that "
                "implements code based on plans."
            ),
            "prompt": self.system_prompt,
            "tools": [
                "Read", "Write", "Edit",
                "Glob", "Grep", "Bash",
            ],
        }

    async def run(
        self,
        verbose: bool,
        plans_dir: str | Path = "plans",
        stream_handler: object | None = None,
        include_partial: bool = False,
    ) -> CodeResult | None:
        """Run the coder agent.

        Args:
            verbose: Print progress messages.
            plans_dir: Path to plan output.
            stream_handler: Optional StreamHandler.
            include_partial: Enable partial msgs.

        Returns:
            CodeResult or None on failure.
        """
        from ..message_processor import (
            MessageProcessor,
        )

        coder_prompt = (
            "Implement the code based on the plan."
            "\n\n"
            f"Working directory: {self.working_dir}"
            "\n\n"
            "IMPORTANT: First, read the "
            "implementation plan:\n"
            f'1. Read "{plans_dir}/plan.md" for the '
            "human-readable plan\n"
            f'2. Optionally read "{plans_dir}/'
            'plan.json" for structured data\n\n'
            "The plan contains:\n"
            "- Task description\n"
            "- Requirements\n"
            "- Files to create and modify\n"
            "- Implementation steps\n"
            "- Dependencies\n\n"
            "Implement all the steps in the plan. "
            "Create and modify files as specified.\n"
            "After implementation, provide a summary "
            "of what was done."
        )

        result_text = ""

        processor = (
            MessageProcessor(
                stream_handler, "coder",
            )
            if stream_handler
            else None
        )

        try:
            opts = ClaudeAgentOptions(
                allowed_tools=[
                    "Read", "Write", "Edit",
                    "Glob", "Grep", "Bash", "Task",
                ],
                permission_mode="acceptEdits",
                agents={
                    "coder": AgentDefinition(
                        **self.get_agent_definition()
                    )
                },
            )
            if include_partial:
                opts.include_partial_messages = True

            async for message in query(
                prompt=coder_prompt,
                options=opts,
            ):
                if processor:
                    await processor.process(message)

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

            return self.parse_result_response(
                result_text,
            )

        except Exception as e:
            if verbose:
                print(f"Error in coder: {e}")
            return None

    @staticmethod
    def parse_result_response(
        response: str,
    ) -> CodeResult:
        """Parse response into a CodeResult."""
        json_match = re.search(
            r"```json\s*(.*?)\s*```",
            response,
            re.DOTALL,
        )
        if json_match:
            json_str = json_match.group(1)
            try:
                data = json.loads(json_str)
                return CodeResult(
                    files_created=data.get(
                        "files_created", [],
                    ),
                    files_modified=data.get(
                        "files_modified", [],
                    ),
                    summary=data.get("summary", ""),
                    success=data.get("success", True),
                    errors=data.get("errors", []),
                )
            except json.JSONDecodeError:
                pass

        files_created = re.findall(
            r"[Cc]reated[:\s]+[`']?([^\s`']+)[`']?",
            response,
        )
        files_modified = re.findall(
            r"[Mm]odified[:\s]+[`']?([^\s`']+)[`']?",
            response,
        )

        summary = (
            response[:1000]
            if len(response) > 1000
            else response
        )
        success = (
            "error" not in response.lower()
            or "success" in response.lower()
        )

        return CodeResult(
            files_created=files_created,
            files_modified=files_modified,
            summary=summary,
            success=success,
        )
