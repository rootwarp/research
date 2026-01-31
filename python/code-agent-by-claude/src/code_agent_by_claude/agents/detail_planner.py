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


DETAIL_PLANNER_SYSTEM_PROMPT = (
    "You are an expert software architect who breaks high-level"
    " plans into small, self-contained implementation parts"
    " using strict TDD workflow.\n\n"
    "When given a plan:\n"
    "1. **Read the plan** from the plans directory:\n"
    "   - Read `plans/plan.md` for the implementation plan\n\n"
    "2. **Explore the codebase** as needed:\n"
    "   - Use Read, Glob, and Grep tools"
    " to understand existing code structure\n\n"
    "3. **Break the plan into small parts**:\n"
    "   - Each part should be small enough"
    " to have minimal side effects\n"
    "   - Each part should be independently reviewable\n"
    "   - Each part should update less than 1,000 lines"
    " of code if possible (except testcases)\n"
    "   - Parts should be ordered by dependency"
    " (prerequisite parts first)\n"
    "   - Parts aligned as building the complete software"
    " incrementally. Do not break test and build.\n\n"
    "4. **Write each part to a separate markdown file**"
    " in the `detail_plans/` directory:\n"
    "   - Name files as `01_<slug>.md`,"
    " `02_<slug>.md`, etc.\n"
    "   - Use the Write tool to create each file\n\n"
    "Each part file should use this structure:\n"
    "```markdown\n"
    "## 01: Title\n\n"
    "- **Scope**: What this part covers\n"
    "- **Tests**: What tests to write or update,"
    " including edge cases\n"
    "- **Files**: Files to create or modify\n"
    "- **Changes**: Detailed step-by-step changes\n"
    "- **Side effects**: Potential side effects"
    " and mitigations\n"
    "```\n\n"
    "5. **Write a TODO checklist** to `detail_plans/TODO.md`"
    " using the Write tool.\n\n"
    "The TODO.md MUST be a single flat numbered list. Do NOT"
    " use nested bullets, headers per part, sub-sections, or"
    " any hierarchical grouping. Reference the part number"
    " inline (e.g., `[Part 2]`) instead.\n\n"
    "Follow strict TDD (Red -> Green -> Refactor) ordering."
    " For each feature or change, produce three sequential"
    " items:\n\n"
    "- **RED**: Write a failing test that specifies the"
    " expected behavior. The test MUST fail at this point"
    " because the implementation does not exist yet.\n"
    "- **GREEN**: Write the minimal implementation code to"
    " make the failing test pass. No more, no less.\n"
    "- **REFACTOR**: Clean up both implementation and test"
    " code while keeping all tests green.\n\n"
    "NEVER group all tests at the end. Every implementation"
    " item MUST be immediately preceded by its corresponding"
    " test item.\n\n"
    "WRONG format (do NOT do this):\n"
    "```markdown\n"
    "## Part 2: Shared Types\n"
    "- [ ] Implement PartyId and ThresholdParams\n"
    "- [ ] Implement SessionId and CeremonyType\n"
    "- [ ] Write unit tests for ThresholdParams\n"
    "```\n\n"
    "CORRECT format (use this exactly):\n"
    "```markdown\n"
    "# Implementation TODO\n\n"
    "- [ ] 01: RED - [Part 1] Write test for"
    " workspace build and clippy pass\n"
    "- [ ] 02: GREEN - [Part 1] Create root"
    " Cargo.toml and crate skeletons\n"
    "- [ ] 03: REFACTOR - [Part 1] Clean up workspace config\n"
    "- [ ] 04: RED - [Part 2] Write test for"
    " PartyId creation and display\n"
    "- [ ] 05: GREEN - [Part 2] Implement PartyId struct\n"
    "- [ ] 06: REFACTOR - [Part 2] Extract"
    " common ID validation\n"
    "- [ ] 07: RED - [Part 2] Write test for"
    " ThresholdParams validation rules\n"
    "- [ ] 08: GREEN - [Part 2] Implement"
    " ThresholdParams with validation\n"
    "- [ ] 09: REFACTOR - [Part 2] Clean up"
    " ThresholdParams error messages\n"
    "```\n\n"
    "Each RED/GREEN/REFACTOR triple must target a single"
    " function, struct, or behavior. If an item covers more"
    " than one public API surface, split it into separate"
    " triples.\n"
)


class DetailPlannerAgent:
    """Agent that breaks plans into detailed parts."""

    def __init__(self, working_dir: str = "."):
        self.working_dir = working_dir
        self.system_prompt = DETAIL_PLANNER_SYSTEM_PROMPT

    def get_agent_definition(self) -> dict[str, Any]:
        """Return the agent definition for SDK."""
        return {
            "description": (
                "Expert architect that breaks implementation"
                " plans into small, self-contained parts."
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

        prompt = (
            "Break the implementation plan into small,"
            " self-contained parts.\n\n"
            f"Working directory: {self.working_dir}\n\n"
            "IMPORTANT: First, read the plan:\n"
            f'1. Read "{plans_dir}/plan.md"\n\n'
            "Then explore the codebase as needed and produce"
            " the detailed parts.\n"
            "Write each part as a separate markdown file in"
            " the detail_plans/ directory.\n"
            "Also write a TODO.md checklist file in the"
            " same directory."
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
            async for message in query(
                prompt=prompt, options=opts
            ):
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
                    if (len(full) > prev_text_len
                            and verbose
                            and not stream_handler):
                        print(
                            full[prev_text_len:],
                            end="", flush=True,
                        )
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
