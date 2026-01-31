"""Event types for real-time streaming."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class EventType(Enum):
    """Types of streaming events."""

    SESSION_INIT = "session_init"
    SESSION_COMPLETE = "session_complete"
    PHASE_START = "phase_start"
    PHASE_END = "phase_end"
    TEXT_DELTA = "text_delta"
    TOOL_START = "tool_start"
    TOOL_RESULT = "tool_result"
    THINKING = "thinking"
    PROGRESS = "progress"
    ERROR = "error"


@dataclass
class StreamEvent:
    """Base event emitted during streaming."""

    type: EventType
    agent_name: str = ""
    session_id: str = ""
    timestamp: float = field(default_factory=time.time)
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class TextEvent(StreamEvent):
    """Text content delta from an agent."""

    text: str = ""

    def __post_init__(self) -> None:
        self.type = EventType.TEXT_DELTA


@dataclass
class ToolEvent(StreamEvent):
    """Tool invocation or result."""

    tool_name: str = ""
    tool_input: dict[str, Any] = field(default_factory=dict)
    tool_result: str = ""
    tool_use_id: str = ""

    def __post_init__(self) -> None:
        if self.type not in (
            EventType.TOOL_START,
            EventType.TOOL_RESULT,
        ):
            self.type = EventType.TOOL_START


@dataclass
class ThinkingEvent(StreamEvent):
    """Thinking/reasoning block from an agent."""

    thinking: str = ""

    def __post_init__(self) -> None:
        self.type = EventType.THINKING


@dataclass
class PhaseEvent(StreamEvent):
    """Phase transition event."""

    phase: str = ""

    def __post_init__(self) -> None:
        if self.type not in (
            EventType.PHASE_START,
            EventType.PHASE_END,
        ):
            self.type = EventType.PHASE_START


@dataclass
class ProgressEvent(StreamEvent):
    """General progress update."""

    message: str = ""

    def __post_init__(self) -> None:
        self.type = EventType.PROGRESS


class EventCallback(Protocol):
    """Protocol for event callbacks."""

    async def __call__(
        self,
        event: StreamEvent,
    ) -> None: ...
