"""Run the PlannerAgent in isolation."""

from __future__ import annotations

import asyncio

import click

from code_agent_by_claude.agents.planner import (
    PlannerAgent,
)
from code_agent_by_claude.stream_handler import (
    DefaultStreamRenderer,
)


async def run_planner(
    working_dir: str = ".",
    research_dir: str = "research",
    show_thinking: bool = False,
    show_tools: bool = False,
) -> None:
    """Run the planner agent standalone."""
    agent = PlannerAgent(working_dir)

    print(f"Working dir: {working_dir}")
    print(f"Research dir: {research_dir}")
    print("-" * 40)

    renderer = DefaultStreamRenderer(
        show_thinking=show_thinking,
        show_tools=show_tools,
    )
    handler = renderer.create_handler()

    result = await agent.run(
        verbose=False,
        research_dir=research_dir,
        stream_handler=handler,
        include_partial=True,
    )

    print("\n" + "=" * 40)

    if result is None:
        print("Planner returned no result.")
        return

    print("[Plan]")
    print(result.content)


@click.command()
@click.option("--working-dir", default=".", help="Working directory.")
@click.option("--research-dir", default="research",
              help="Path to research output directory.")
@click.option("--show-thinking", is_flag=True, help="Show agent thinking.")
@click.option("--show-tools", is_flag=True, help="Show tool usage.")
def main(working_dir: str, research_dir: str,
         show_thinking: bool, show_tools: bool) -> None:
    """Run the PlannerAgent in isolation."""
    asyncio.run(run_planner(
        working_dir, research_dir,
        show_thinking, show_tools,
    ))


if __name__ == "__main__":
    main()
