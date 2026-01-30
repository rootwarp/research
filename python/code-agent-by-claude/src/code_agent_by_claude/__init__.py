"""AI Coding Agents using Claude Agent SDK."""

from .agents import PlannerAgent, CoderAgent
from .agents.planner import Plan
from .agents.coder import CodeResult
from .events import (
    EventType,
    StreamEvent,
    TextEvent,
    ToolEvent,
    ThinkingEvent,
    PhaseEvent,
    ProgressEvent,
)
from .stream_handler import StreamHandler, DefaultStreamRenderer
from .message_processor import MessageProcessor
from .orchestrator import (
    Orchestrator,
    TaskResult,
    run_coding_task,
    run_coding_task_with_stream,
)

__version__ = "0.1.0"
__all__ = [
    "PlannerAgent",
    "CoderAgent",
    "Plan",
    "CodeResult",
    "Orchestrator",
    "TaskResult",
    "run_coding_task",
    "run_coding_task_with_stream",
    "EventType",
    "StreamEvent",
    "TextEvent",
    "ToolEvent",
    "ThinkingEvent",
    "PhaseEvent",
    "ProgressEvent",
    "StreamHandler",
    "DefaultStreamRenderer",
    "MessageProcessor",
]
