"""AI Agents for coding tasks."""

from __future__ import annotations

from typing import Any

from claude_agent_sdk import SystemMessage

from .coder import CoderAgent
from .detail_planner import DetailPlannerAgent
from .planner import PlannerAgent
from .researcher import ResearcherAgent
from .reviewer import ReviewerAgent

__all__ = [
    "ResearcherAgent",
    "PlannerAgent",
    "DetailPlannerAgent",
    "CoderAgent",
    "ReviewerAgent",
]


def warn_mcp(
    message: SystemMessage,
    verbose: bool,
) -> None:
    """Warn about disconnected MCP servers."""
    data: dict[str, Any] = getattr(message, "data", {})
    servers = data.get("mcp_servers", [])
    for server in servers:
        status = server.get("status")
        name = server.get("name")
        if status != "connected" and verbose:
            print(f"Warning: MCP server '{name}' failed to connect")
