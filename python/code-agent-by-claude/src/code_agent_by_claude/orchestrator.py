"""Orchestrator - Coordinates the researcher, planner and coder."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from .agents.researcher import ResearcherAgent, ResearchResult
from .agents.planner import PlannerAgent, Plan
from .agents.coder import CoderAgent, CodeResult
from .events import EventType, PhaseEvent
from .stream_handler import StreamHandler, EventCallbackFn


def _expand_env_vars(value: str) -> str:
    """Expand environment variables like ${VAR_NAME}."""
    if isinstance(value, str) and "${" in value:
        pattern = r"\$\{([^}]+)\}"
        return re.sub(
            pattern,
            lambda m: os.environ.get(m.group(1), ""),
            value,
        )
    return value


def load_mcp_config(working_dir: str = ".") -> dict:
    """Load MCP server config from .mcp.json."""
    mcp_path = Path(working_dir) / ".mcp.json"

    if not mcp_path.exists():
        return {}

    try:
        with open(mcp_path) as f:
            config = json.load(f)

        mcp_servers = config.get("mcpServers", {})

        for _name, srv in mcp_servers.items():
            if "env" in srv:
                srv["env"] = {
                    k: _expand_env_vars(v)
                    for k, v in srv["env"].items()
                }
            if "headers" in srv:
                srv["headers"] = {
                    k: _expand_env_vars(v)
                    for k, v in srv["headers"].items()
                }

        return mcp_servers

    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: Could not load .mcp.json: {e}")
        return {}


@dataclass
class TaskResult:
    """Result of a complete coding task."""

    task: str
    research_result: ResearchResult | None
    plan: Plan | None
    code_result: CodeResult | None
    success: bool
    error: str | None = None


class Orchestrator:
    """Orchestrates the three-agent coding pipeline."""

    def __init__(
        self,
        working_dir: str = ".",
        stream_handler: StreamHandler | None = None,
        include_partial_messages: bool = False,
    ):
        self.working_dir = working_dir
        self.research_dir = (
            Path(working_dir) / "research"
        )
        self.plans_dir = Path(working_dir) / "plans"
        self.researcher = ResearcherAgent(working_dir)
        self.planner = PlannerAgent(working_dir)
        self.coder = CoderAgent(working_dir)
        self.mcp_servers = load_mcp_config(working_dir)
        self.stream_handler = stream_handler
        self.include_partial = include_partial_messages

    async def _emit_phase(
        self,
        phase: str,
        event_type: EventType,
    ) -> None:
        """Emit a phase event if handler is set."""
        if self.stream_handler:
            event = PhaseEvent(
                type=event_type,
                agent_name="orchestrator",
                phase=phase,
            )
            await self.stream_handler.emit(event)

    async def run_task(
        self,
        task: str | None = None,
        verbose: bool = True,
        issue_url: str | None = None,
    ) -> TaskResult:
        """Run a complete coding task with all agents.

        Args:
            task: Coding task description.
            verbose: Print progress messages.
            issue_url: GitHub issue URL.

        Returns:
            TaskResult with research, plan and code.
        """
        task_description = self._build_task_desc(
            task, issue_url,
        )
        if task_description is None:
            return TaskResult(
                task="",
                research_result=None,
                plan=None,
                code_result=None,
                success=False,
                error="No task or issue URL provided",
            )

        if verbose:
            self._print_header(task, issue_url)

        # Phase 1: Research
        if verbose:
            print("[Phase 1] Researching...")
            print("-" * 40)

        await self._emit_phase(
            "Research", EventType.PHASE_START,
        )
        research_result = await self.researcher.run(
            task=task_description,
            verbose=verbose,
            mcp_servers=self.mcp_servers,
            stream_handler=self.stream_handler,
            include_partial=self.include_partial,
            issue_url=issue_url,
        )
        await self._emit_phase(
            "Research", EventType.PHASE_END,
        )

        if research_result is None:
            return TaskResult(
                task=task_description,
                research_result=None,
                plan=None,
                code_result=None,
                success=False,
                error="Researcher agent failed",
            )

        research_result.save_to_dir(self.research_dir)

        if verbose:
            print("\n[Research Complete]")
            print(f"Saved to: {self.research_dir}")
            print(research_result.to_prompt())
            print("-" * 40)

        # Phase 2: Planning
        if verbose:
            print("\n[Phase 2] Planning...")
            print("-" * 40)

        await self._emit_phase(
            "Planning", EventType.PHASE_START,
        )
        plan = await self.planner.run(
            task=task_description,
            verbose=verbose,
            research_dir=self.research_dir,
            mcp_servers=self.mcp_servers,
            stream_handler=self.stream_handler,
            include_partial=self.include_partial,
        )
        await self._emit_phase(
            "Planning", EventType.PHASE_END,
        )

        if plan is None:
            return TaskResult(
                task=task_description,
                research_result=research_result,
                plan=None,
                code_result=None,
                success=False,
                error="Planner agent failed",
            )

        plan.save_to_dir(self.plans_dir)

        if verbose:
            print("\n[Plan Created]")
            print(f"Saved to: {self.plans_dir}")
            print(plan.to_prompt())
            print("-" * 40)

        # Phase 3: Implementation
        if verbose:
            print("\n[Phase 3] Implementing...")
            print("-" * 40)

        await self._emit_phase(
            "Implementation", EventType.PHASE_START,
        )
        code_result = await self.coder.run(
            verbose=verbose,
            plans_dir=self.plans_dir,
            stream_handler=self.stream_handler,
            include_partial=self.include_partial,
        )
        await self._emit_phase(
            "Implementation", EventType.PHASE_END,
        )

        if verbose:
            print("\n[Implementation Complete]")
            if code_result:
                print(
                    f"Created: {code_result.files_created}"
                )
                print(
                    f"Modified: "
                    f"{code_result.files_modified}"
                )
                print(f"Summary: {code_result.summary}")

        return TaskResult(
            task=task_description,
            research_result=research_result,
            plan=plan,
            code_result=code_result,
            success=(
                code_result.success
                if code_result
                else False
            ),
        )

    def _build_task_desc(
        self,
        task: str | None,
        issue_url: str | None,
    ) -> str | None:
        """Build task description from args."""
        if issue_url and task:
            return (
                f"Implement GitHub issue: {issue_url}"
                f"\n\nAdditional context: {task}"
            )
        if issue_url:
            return (
                f"Implement GitHub issue: {issue_url}"
            )
        if task:
            return task
        return None

    def _print_header(
        self,
        task: str | None,
        issue_url: str | None,
    ) -> None:
        """Print task header."""
        print(f"\n{'=' * 60}")
        if issue_url:
            print(f"GitHub Issue: {issue_url}")
        if task:
            print(f"Task: {task}")
        if self.mcp_servers:
            servers = ", ".join(self.mcp_servers.keys())
            print(f"MCP servers: {servers}")
        print(f"{'=' * 60}\n")


async def run_coding_task(
    task: str | None = None,
    working_dir: str = ".",
    verbose: bool = True,
    issue_url: str | None = None,
    stream_handler: StreamHandler | None = None,
    include_partial_messages: bool = False,
) -> TaskResult:
    """Convenience function to run a coding task.

    Args:
        task: Coding task description.
        working_dir: Working directory.
        verbose: Print progress messages.
        issue_url: GitHub issue URL.
        stream_handler: Optional StreamHandler.
        include_partial_messages: Enable streaming.

    Returns:
        TaskResult with research, plan and code.
    """
    orchestrator = Orchestrator(
        working_dir,
        stream_handler,
        include_partial_messages,
    )
    return await orchestrator.run_task(
        task, verbose, issue_url,
    )


async def run_coding_task_with_stream(
    task: str,
    working_dir: str = ".",
    on_event: EventCallbackFn | None = None,
    show_thinking: bool = False,
    show_tools: bool = False,
    issue_url: str | None = None,
) -> TaskResult:
    """Run a coding task with streaming enabled.

    Args:
        task: Coding task description.
        working_dir: Working directory.
        on_event: Async callback for all events.
        show_thinking: Show thinking blocks.
        show_tools: Show tool usage.
        issue_url: GitHub issue URL.

    Returns:
        TaskResult with research, plan and code.
    """
    from .stream_handler import DefaultStreamRenderer

    if on_event:
        handler = StreamHandler()
        handler.on_all(on_event)
    else:
        renderer = DefaultStreamRenderer(
            show_thinking=show_thinking,
            show_tools=show_tools,
        )
        handler = renderer.create_handler()

    orchestrator = Orchestrator(
        working_dir,
        stream_handler=handler,
        include_partial_messages=True,
    )
    return await orchestrator.run_task(
        task, verbose=False, issue_url=issue_url,
    )
