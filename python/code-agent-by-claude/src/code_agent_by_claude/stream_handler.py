"""Stream handler for event dispatch and rendering."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from typing import Callable, Awaitable

from .events import (
    EventType,
    StreamEvent,
    TextEvent,
    ToolEvent,
    ThinkingEvent,
    PhaseEvent,
)

EventCallbackFn = Callable[[StreamEvent], Awaitable[None]]


class StreamHandler:
    """Dispatches streaming events to callbacks."""

    def __init__(self) -> None:
        self._callbacks: dict[
            EventType,
            list[EventCallbackFn],
        ] = defaultdict(list)
        self._global_callbacks: list[EventCallbackFn] = []

    def on(
        self,
        event_type: EventType,
        callback: EventCallbackFn,
    ) -> None:
        """Register a callback for an event type."""
        self._callbacks[event_type].append(callback)

    def on_all(
        self,
        callback: EventCallbackFn,
    ) -> None:
        """Register a callback for all events."""
        self._global_callbacks.append(callback)

    async def emit(
        self,
        event: StreamEvent,
    ) -> None:
        """Dispatch event to matching callbacks."""
        for cb in self._global_callbacks:
            await cb(event)
        for cb in self._callbacks.get(
            event.type,
            [],
        ):
            await cb(event)


class DefaultStreamRenderer:
    """Default CLI renderer for streaming events."""

    def __init__(
        self,
        show_thinking: bool = False,
        show_tools: bool = False,
        json_events: bool = False,
    ) -> None:
        self.show_thinking = show_thinking
        self.show_tools = show_tools
        self.json_events = json_events

    def create_handler(self) -> StreamHandler:
        """Create a StreamHandler for this renderer."""
        handler = StreamHandler()
        if self.json_events:
            handler.on_all(self._handle_json)
        else:
            handler.on(EventType.PHASE_START, self._handle_phase)
            handler.on(EventType.PHASE_END, self._handle_phase)
            handler.on(EventType.TEXT_DELTA, self._handle_text)
            handler.on(EventType.TOOL_START, self._handle_tool)
            handler.on(EventType.TOOL_RESULT, self._handle_tool)
            handler.on(EventType.THINKING, self._handle_thinking)

        return handler

    async def _handle_json(self, event: StreamEvent) -> None:
        """Output event as JSON line."""
        data: dict[str, object] = {
            "type": event.type.value,
            "agent": event.agent_name,
            "timestamp": event.timestamp,
        }
        if isinstance(event, TextEvent):
            data["text"] = event.text
        elif isinstance(event, ToolEvent):
            data["tool"] = event.tool_name
            if event.tool_input:
                data["input"] = event.tool_input
            if event.tool_result:
                data["result"] = event.tool_result
        elif isinstance(event, ThinkingEvent):
            data["thinking"] = event.thinking
        elif isinstance(event, PhaseEvent):
            data["phase"] = event.phase
        else:
            data["data"] = event.data

        print(json.dumps(data), flush=True)

    async def _handle_phase(self, event: StreamEvent) -> None:
        if not isinstance(event, PhaseEvent):
            return
        if event.type == EventType.PHASE_START:
            print(f"\n[{event.phase}] Starting...", file=sys.stderr)
        else:
            print(f"[{event.phase}] Done.", file=sys.stderr)

    async def _handle_text(self, event: StreamEvent) -> None:
        if isinstance(event, TextEvent):
            print(event.text, end="", flush=True)

    async def _handle_tool(self, event: StreamEvent) -> None:
        if not self.show_tools:
            return
        if not isinstance(event, ToolEvent):
            return
        if event.type == EventType.TOOL_START:
            print(f"\n  [Tool: {event.tool_name}]", file=sys.stderr)
        else:
            snippet = event.tool_result[:120]
            print(f"  [Result: {snippet}]", file=sys.stderr)

    async def _handle_thinking(self, event: StreamEvent) -> None:
        if not self.show_thinking:
            return
        if isinstance(event, ThinkingEvent):
            print(f"\n  [Thinking] {event.thinking}", file=sys.stderr)
