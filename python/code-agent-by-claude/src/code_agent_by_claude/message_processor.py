"""Process SDK messages into typed streaming events."""

from __future__ import annotations

from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    SystemMessage,
)

from .events import (
    EventType,
    StreamEvent,
    TextEvent,
    ToolEvent,
    ThinkingEvent,
    ProgressEvent,
)
from .stream_handler import StreamHandler


class MessageProcessor:
    """Converts Claude Agent SDK messages into typed events
    and emits them through a StreamHandler."""

    def __init__(
        self,
        handler: StreamHandler,
        agent_name: str = "",
        session_id: str = "",
    ) -> None:
        self.handler = handler
        self.agent_name = agent_name
        self.session_id = session_id

    async def process(self, message: object) -> None:
        """Process a single SDK message."""
        if isinstance(message, SystemMessage):
            await self._process_system(message)
        elif isinstance(message, AssistantMessage):
            await self._process_assistant(message)
        elif isinstance(message, ResultMessage):
            await self._process_result(message)
        # StreamEvent from SDK (partial messages)
        elif hasattr(message, "event"):
            await self._process_stream_event(message)

    async def _process_system(
        self, message: SystemMessage
    ) -> None:
        if message.subtype == "init":
            event = ProgressEvent(
                type=EventType.PROGRESS,
                agent_name=self.agent_name,
                session_id=self.session_id,
                message="Session initialized",
                data=message.data,
            )
            await self.handler.emit(event)

    async def _process_assistant(
        self, message: AssistantMessage
    ) -> None:
        for block in message.content:
            if hasattr(block, "text"):
                event = TextEvent(
                    type=EventType.TEXT_DELTA,
                    agent_name=self.agent_name,
                    session_id=self.session_id,
                    text=block.text,
                )
                await self.handler.emit(event)
            elif hasattr(block, "name") and hasattr(
                block, "input"
            ):
                # ToolUseBlock
                event = ToolEvent(
                    type=EventType.TOOL_START,
                    agent_name=self.agent_name,
                    session_id=self.session_id,
                    tool_name=getattr(block, "name", ""),
                    tool_input=getattr(
                        block, "input", {}
                    ),
                    tool_use_id=getattr(block, "id", ""),
                )
                await self.handler.emit(event)
            elif hasattr(block, "content") and hasattr(
                block, "tool_use_id"
            ):
                # ToolResultBlock
                result_text = ""
                content = getattr(block, "content", "")
                if isinstance(content, str):
                    result_text = content
                elif isinstance(content, list):
                    parts = []
                    for part in content:
                        if hasattr(part, "text"):
                            parts.append(part.text)
                    result_text = "\n".join(parts)
                event = ToolEvent(
                    type=EventType.TOOL_RESULT,
                    agent_name=self.agent_name,
                    session_id=self.session_id,
                    tool_name="",
                    tool_result=result_text,
                    tool_use_id=getattr(
                        block, "tool_use_id", ""
                    ),
                )
                await self.handler.emit(event)
            elif hasattr(block, "thinking"):
                event = ThinkingEvent(
                    type=EventType.THINKING,
                    agent_name=self.agent_name,
                    session_id=self.session_id,
                    thinking=getattr(
                        block, "thinking", ""
                    ),
                )
                await self.handler.emit(event)

    async def _process_result(
        self, message: ResultMessage
    ) -> None:
        if message.subtype == "success":
            event = TextEvent(
                type=EventType.TEXT_DELTA,
                agent_name=self.agent_name,
                session_id=self.session_id,
                text=message.result,
            )
            await self.handler.emit(event)

    async def _process_stream_event(
        self, message: object
    ) -> None:
        """Process a raw SDK StreamEvent (partial message)."""
        raw = getattr(message, "event", {})
        if not isinstance(raw, dict):
            return

        event_type = raw.get("type", "")

        if event_type == "content_block_delta":
            delta = raw.get("delta", {})
            delta_type = delta.get("type", "")

            if delta_type == "text_delta":
                event = TextEvent(
                    type=EventType.TEXT_DELTA,
                    agent_name=self.agent_name,
                    session_id=self.session_id,
                    text=delta.get("text", ""),
                )
                await self.handler.emit(event)
            elif delta_type == "thinking_delta":
                event = ThinkingEvent(
                    type=EventType.THINKING,
                    agent_name=self.agent_name,
                    session_id=self.session_id,
                    thinking=delta.get(
                        "thinking", ""
                    ),
                )
                await self.handler.emit(event)
            elif delta_type == "input_json_delta":
                event = StreamEvent(
                    type=EventType.PROGRESS,
                    agent_name=self.agent_name,
                    session_id=self.session_id,
                    data=delta,
                )
                await self.handler.emit(event)

        elif event_type == "content_block_start":
            block = raw.get("content_block", {})
            if block.get("type") == "tool_use":
                event = ToolEvent(
                    type=EventType.TOOL_START,
                    agent_name=self.agent_name,
                    session_id=self.session_id,
                    tool_name=block.get("name", ""),
                    tool_use_id=block.get("id", ""),
                )
                await self.handler.emit(event)
