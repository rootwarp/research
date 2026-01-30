"""AI Agents for coding tasks."""

from .researcher import ResearcherAgent
from .planner import PlannerAgent
from .coder import CoderAgent

__all__ = [
    "ResearcherAgent",
    "PlannerAgent",
    "CoderAgent",
]


def warn_mcp(
    message: object, verbose: bool,
) -> None:
    """Warn about disconnected MCP servers."""
    servers = message.data.get(
        "mcp_servers", [],
    )
    for server in servers:
        status = server.get("status")
        name = server.get("name")
        if status != "connected" and verbose:
            print(
                f"Warning: MCP server "
                f"'{name}' failed to connect"
            )
