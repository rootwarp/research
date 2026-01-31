"""Prompt loader for agent system and local prompts."""

from __future__ import annotations

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


def load_prompt(name: str, **kwargs: str) -> str:
    """Load a prompt markdown file by name.

    Args:
        name: Prompt name matching the .md filename
              (e.g. "researcher", "researcher_task").
        **kwargs: Template variables to substitute
                  via str.format().

    Returns:
        The prompt text with variables substituted
        and trailing whitespace stripped.
    """
    path = _PROMPTS_DIR / f"{name}.md"
    text = path.read_text(encoding="utf-8").strip()
    if kwargs:
        text = text.format(**kwargs)
    return text
