"""Run the DetailPlannerAgent in isolation."""

from __future__ import annotations

import asyncio

import click

from code_agent_by_claude.agents.detail_planner import DetailPlannerAgent
from code_agent_by_claude.stream_handler import DefaultStreamRenderer


async def run_detail_planner(
    working_dir: str = ".",
    plans_dir: str = "plans",
    show_thinking: bool = False,
    show_tools: bool = False,
) -> None:
    """Run the detail planner agent standalone."""
    agent = DetailPlannerAgent(working_dir)

    print(f"Working dir: {working_dir}")
    print(f"Plans dir: {plans_dir}")
    print("-" * 40)

    renderer = DefaultStreamRenderer(
        show_thinking=show_thinking, show_tools=show_tools
    )
    handler = renderer.create_handler()

    result = await agent.run(
        verbose=False,
        plans_dir=plans_dir,
        stream_handler=handler,
        include_partial=True,
    )

    print("\n" + "=" * 40)

    if result:
        print("[Detail Plan] Completed successfully.")
    else:
        print("[Detail Plan] Failed.")


@click.command()
@click.option("--working-dir", default=".", help="Working directory.")
@click.option("--plans-dir", default="plans", help="Path to plans directory.")
@click.option("--show-thinking", is_flag=True, help="Show agent thinking.")
@click.option("--show-tools", is_flag=True, help="Show tool usage.")
def main(
    working_dir: str, plans_dir: str, show_thinking: bool, show_tools: bool
) -> None:
    """Run the DetailPlannerAgent in isolation."""
    asyncio.run(
        run_detail_planner(working_dir, plans_dir, show_thinking, show_tools)
    )


if __name__ == "__main__":
    main()
