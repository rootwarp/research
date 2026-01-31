"""Run the ResearcherAgent in isolation."""

from __future__ import annotations

import asyncio
from pathlib import Path

import click

from code_agent_by_claude.agents.researcher import (
    ResearcherAgent,
)
from code_agent_by_claude.stream_handler import (
    DefaultStreamRenderer,
)


async def run_researcher(
    task: str,
    working_dir: str = ".",
    show_thinking: bool = False,
    show_tools: bool = False,
) -> None:
    """Run the researcher agent standalone."""
    agent = ResearcherAgent(working_dir)

    print(f"Task: {task}")
    print(f"Working dir: {working_dir}")
    print("-" * 40)

    renderer = DefaultStreamRenderer(
        show_thinking=show_thinking,
        show_tools=show_tools,
    )
    handler = renderer.create_handler()

    result = await agent.run(
        task=task,
        verbose=False,
        stream_handler=handler,
        include_partial=True,
    )

    print("\n" + "=" * 40)

    if result is None:
        print("Researcher returned no result.")
        return

    print("[Research Result]")
    print(result.content)


@click.command()
@click.option(
    "--task-file",
    required=True,
    type=click.Path(exists=True),
    help="Markdown file containing the task description.",
)
@click.option(
    "--working-dir", default=".", help="Working directory."
)
@click.option(
    "--show-thinking",
    is_flag=True,
    help="Show agent thinking.",
)
@click.option(
    "--show-tools", is_flag=True, help="Show tool usage."
)
def main(
    task_file: str,
    working_dir: str,
    show_thinking: bool,
    show_tools: bool,
) -> None:
    """Run the ResearcherAgent in isolation."""
    task = Path(task_file).read_text(encoding="utf-8")
    asyncio.run(
        run_researcher(
            task,
            working_dir,
            show_thinking,
            show_tools,
        )
    )


if __name__ == "__main__":
    main()
