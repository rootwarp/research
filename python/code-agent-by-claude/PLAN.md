# Real-Time Streaming Implementation Plan

## Summary
Add real-time streaming of Claude Code activities using `include_partial_messages=True` from the Claude Agent SDK, enabling detailed progress monitoring with events for text streaming, tool execution, and phase transitions.

## Approach
Use `query()` with `include_partial_messages=True` (simpler, backward-compatible) rather than switching to `ClaudeSDKClient`. This provides `StreamEvent` messages with raw Anthropic API events while maintaining existing code structure.

---

## Files to Create

### 1. `src/code_agent_by_claude/events.py`
Event types and dataclasses:
- `EventType` enum: `PHASE_START`, `PHASE_END`, `TEXT_DELTA`, `TOOL_START`, `TOOL_RESULT`, `SESSION_INIT`, `SESSION_COMPLETE`, etc.
- `StreamEvent` base dataclass with `type`, `timestamp`, `session_id`, `agent_name`, `data`
- Specialized events: `TextEvent`, `ToolEvent`, `ThinkingEvent`, `PhaseEvent`, `ProgressEvent`
- `EventCallback` protocol for type-safe callbacks

### 2. `src/code_agent_by_claude/stream_handler.py`
Event dispatch and rendering:
- `StreamHandler` class with `on(event_type, callback)` and `on_all(callback)` methods
- `emit(event)` async method to dispatch to registered callbacks
- `DefaultStreamRenderer` class for CLI output (text, tools, phases)

### 3. `src/code_agent_by_claude/message_processor.py`
SDK message to event conversion:
- `MessageProcessor` class that processes `StreamEvent`, `AssistantMessage`, `SystemMessage`, `ResultMessage`
- Extracts content blocks: `TextBlock`, `ToolUseBlock`, `ToolResultBlock`, `ThinkingBlock`
- Emits appropriate typed events for each SDK message type

---

## Files to Modify

### 1. `src/code_agent_by_claude/orchestrator.py`
- Add imports: `StreamEvent as SDKStreamEvent` from SDK, new modules
- `Orchestrator.__init__`: Add optional `stream_handler` and `include_partial_messages` parameters
- `_run_researcher`, `_run_planner`, `_run_coder`:
  - Add `include_partial_messages=True` to `ClaudeAgentOptions`
  - Create `MessageProcessor` and process messages through it
  - Emit `PhaseEvent` at start/end of each phase
- `run_coding_task`: Add optional `on_event` callback parameter

### 2. `src/code_agent_by_claude/main.py`
Add CLI arguments:
- `--stream` / `-s`: Enable partial message streaming
- `--show-thinking`: Display thinking/reasoning blocks
- `--show-tools`: Show tool execution details
- `--json-events`: Output events as JSON lines for programmatic use

### 3. `src/code_agent_by_claude/__init__.py`
Export new types:
- `StreamHandler`, `MessageProcessor`
- `EventType`, `StreamEvent`, `TextEvent`, `ToolEvent`, `PhaseEvent`
- `run_coding_task_with_stream` convenience function

---

## Key SDK Features to Use

From `claude_agent_sdk`:
```python
from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    StreamEvent,  # New - contains raw API events
    TextBlock, ToolUseBlock, ToolResultBlock, ThinkingBlock,
)

# Enable partial messages
options = ClaudeAgentOptions(
    include_partial_messages=True,  # Key option
    # ... other options
)

# StreamEvent structure
# - uuid: str
# - session_id: str
# - event: dict  # Raw Anthropic API stream event
# - parent_tool_use_id: str | None
```

---

## Example Usage After Implementation

### CLI
```bash
# Basic streaming with progress
code-agent --stream "Create a REST API"

# Show all details including thinking
code-agent --stream --show-thinking --show-tools "Fix bug"

# JSON output for programmatic consumption
code-agent --stream --json-events "Add feature" | jq
```

### Python API
```python
from code_agent_by_claude import run_coding_task_with_stream, TextEvent, ToolEvent

def on_text(event: TextEvent):
    print(event.text, end="", flush=True)

def on_tool(event: ToolEvent):
    print(f"\n[Tool: {event.tool_name}]")

result = await run_coding_task_with_stream(
    task="Create a CLI",
    on_event=lambda e: on_text(e) if isinstance(e, TextEvent) else on_tool(e) if isinstance(e, ToolEvent) else None
)
```

---

## Verification

1. **Unit tests**: Test `MessageProcessor` converts SDK messages to correct event types
2. **Integration test**: Run `code-agent --stream "Create hello.py"` and verify:
   - Phase transitions are displayed
   - Tool usage is shown in real-time
   - Text streams incrementally
3. **JSON output test**: `code-agent --stream --json-events "task" | head -20` produces valid JSON lines
4. **Backward compatibility**: `code-agent "task"` (without `--stream`) works as before

---

## Implementation Order

1. Create `events.py` with all event types
2. Create `stream_handler.py` with handler and default renderer
3. Create `message_processor.py` with SDK message processing
4. Modify `orchestrator.py` to integrate streaming
5. Modify `main.py` to add CLI arguments
6. Update `__init__.py` exports
7. Test end-to-end
