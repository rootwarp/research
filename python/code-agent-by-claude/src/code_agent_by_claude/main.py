"""Main entry point for code-agent-by-claude."""

import argparse, asyncio, re, sys

from .orchestrator import run_coding_task
from .stream_handler import DefaultStreamRenderer


def parse_github_issue_url(
    url: str,
) -> tuple[str, str, int] | None:
    """Parse a GitHub issue URL.

    Args:
        url: GitHub issue URL.

    Returns:
        Tuple of (owner, repo, issue_number) or None.
    """
    pattern = (
        r"https?://github\.com/"
        r"([^/]+)/([^/]+)/issues/(\d+)")
    match = re.match(pattern, url)
    if match:
        return (match.group(1), match.group(2),
                int(match.group(3)))
    return None


def main() -> None:
    """Main function - CLI entry point."""
    parser = argparse.ArgumentParser(
        description=(
            "AI Coding Agents - Plan and implement"
            " code using Claude"),
        formatter_class=(
            argparse.RawDescriptionHelpFormatter),
        epilog="""
Examples:
  code-agent "Create a fibonacci function"
  code-agent --issue https://github.com/o/r/issues/1
  code-agent --issue URL "Additional context"
  code-agent --dir ./project "Refactor module"
        """,
    )
    parser.add_argument(
        "task", nargs="?",
        help="The coding task to complete")
    parser.add_argument(
        "--issue", "-I",
        help="GitHub issue URL to research and "
             "implement")
    parser.add_argument(
        "--dir", "-d", default=".",
        help="Working directory (default: .)")
    parser.add_argument(
        "--quiet", "-q", action="store_true",
        help="Suppress progress output")
    parser.add_argument(
        "--interactive", "-i", action="store_true",
        help="Run in interactive mode")
    parser.add_argument(
        "--stream", "-s", action="store_true",
        help="Enable real-time streaming of agent "
             "activity")
    parser.add_argument(
        "--show-thinking", action="store_true",
        help="Display thinking/reasoning blocks")
    parser.add_argument(
        "--show-tools", action="store_true",
        help="Show tool execution details")
    parser.add_argument(
        "--json-events", action="store_true",
        help="Output events as JSON lines")

    args = parser.parse_args()

    if args.interactive:
        run_interactive(args.dir, not args.quiet)
    elif args.issue or args.task:
        issue_info = None
        if args.issue:
            issue_info = parse_github_issue_url(
                args.issue)
            if not issue_info:
                print(
                    "Error: Invalid GitHub "
                    f"issue URL: {args.issue}")
                print(
                    "Expected format: https://"
                    "github.com/owner/repo/issues/123")
                sys.exit(1)

        stream_handler = None
        if args.stream:
            renderer = DefaultStreamRenderer(
                show_thinking=args.show_thinking,
                show_tools=args.show_tools,
                json_events=args.json_events)
            stream_handler = renderer.create_handler()

        result = asyncio.run(
            run_coding_task(
                task=args.task,
                working_dir=args.dir,
                verbose=not args.quiet,
                issue_url=args.issue,
                stream_handler=stream_handler,
                include_partial_messages=args.stream))

        if result.success:
            print("\n" + "=" * 60)
            print("Task completed successfully!")
            print("=" * 60)
            sys.exit(0)
        else:
            print("\n" + "=" * 60)
            error = result.error or "Unknown error"
            print(f"Task failed: {error}")
            print("=" * 60)
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


def run_interactive(
    working_dir: str, verbose: bool,
) -> None:
    """Run in interactive mode."""
    print("=" * 60)
    print("AI Coding Agents - Interactive Mode")
    print("=" * 60)
    print(f"Working directory: {working_dir}")
    print("Enter coding tasks "
          "(Ctrl+D or 'exit' to quit)\n")

    while True:
        try:
            task = input("Task> ").strip()
            if not task:
                continue
            if task.lower() in ("exit", "quit", "q"):
                print("Goodbye!")
                break

            result = asyncio.run(run_coding_task(
                task, working_dir, verbose))

            if result.success:
                print("\n[Task completed]\n")
            else:
                error = result.error or "Unknown error"
                print(f"\n[Task failed: {error}]\n")

        except EOFError:
            print("\nGoodbye!")
            break
        except KeyboardInterrupt:
            print("\n[Interrupted]")
            continue


if __name__ == "__main__":
    main()
