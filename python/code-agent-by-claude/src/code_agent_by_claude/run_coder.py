"""Run the CoderAgent in isolation."""

from __future__ import annotations

import asyncio

import click

from code_agent_by_claude.agents.coder import CoderAgent
from code_agent_by_claude.stream_handler import DefaultStreamRenderer


async def run_coder(
    working_dir: str = ".",
    plans_dir: str = "plans",
    show_thinking: bool = False,
    show_tools: bool = False,
) -> None:
    """Run the coder agent standalone."""
    agent = CoderAgent(working_dir)

    print(f"Working dir: {working_dir}")
    print(f"Plans dir: {plans_dir}")
    print("-" * 40)

    renderer = DefaultStreamRenderer(
        show_thinking=show_thinking,
        show_tools=show_tools,
    )
    handler = renderer.create_handler()

    result = await agent.run(
        verbose=False,
        plans_dir=plans_dir,
        stream_handler=handler,
        include_partial=True,
    )

    print("\n" + "=" * 40)

    if result is None:
        print("Coder returned no result.")
        return

    print(f"[Coder] success={result.success}")
    if result.files_created:
        print("  Created:")
        for f in result.files_created:
            print(f"    {f}")
    if result.files_modified:
        print("  Modified:")
        for f in result.files_modified:
            print(f"    {f}")
    if result.errors:
        print("  Errors:")
        for e in result.errors:
            print(f"    {e}")
    print(f"\n{result.summary}")


@click.command()
@click.option("--working-dir", default=".", help="Working directory.")
@click.option("--plans-dir", default="plans", help="Path to plans directory.")
@click.option("--show-thinking", is_flag=True, help="Show agent thinking.")
@click.option("--show-tools", is_flag=True, help="Show tool usage.")
def main(
    working_dir: str,
    plans_dir: str,
    show_thinking: bool,
    show_tools: bool,
) -> None:
    """Run the CoderAgent in isolation."""
    asyncio.run(
        run_coder(
            working_dir,
            plans_dir,
            show_thinking,
            show_tools,
        )
    )


if __name__ == "__main__":
    main()
