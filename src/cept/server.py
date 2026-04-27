"""MCP server exposing the cept tool over stdio."""

from __future__ import annotations

import json
import os

from mcp.server.fastmcp import FastMCP

from .core import run_cept
from .openrouter import DEFAULT_MODEL, OpenRouterError


mcp = FastMCP("cept")


@mcp.tool()
def cept(
    goal: str,
    lookback_minutes: int = 20,
    mode: str = "steer",
    question: str | None = None,
    session_id: str | None = None,
    include_repo_state: bool = True,
    include_diff: bool = True,
    max_events: int = 250,
    model: str = DEFAULT_MODEL,
) -> str:
    """Inspect the recent Claude Code transcript and return outside-in steering guidance.

    Use this when stuck, looping, or facing a low-confidence architectural choice.
    The tool reads the active session JSONL, distills the last `lookback_minutes`
    of events, redacts secrets, and asks an OpenRouter model (with web search)
    for ranked guidance.

    Args:
        goal: What the agent is currently trying to accomplish.
        lookback_minutes: How far back to inspect (1–120, default 20).
        mode: One of "steer" (default), "debug", "research", "architecture".
        question: Optional specific question to forward.
        session_id: Optional explicit Claude Code session UUID.
        include_repo_state: Whether to attach git status/diff/branch.
        include_diff: Whether to include `git diff --stat`.
        max_events: Cap on events to keep after the lookback filter.
        model: OpenRouter model id. Default "perplexity/sonar-reasoning"
            (Perplexity's reasoning + web search). Append ":online" to any
            model name to force web search where supported.
    """
    cwd = os.getcwd()
    lookback_minutes = max(1, min(int(lookback_minutes), 120))
    max_events = max(20, min(int(max_events), 1000))
    if mode not in {"steer", "debug", "research", "architecture"}:
        mode = "steer"

    try:
        result = run_cept(
            goal=goal,
            cwd=cwd,
            lookback_minutes=lookback_minutes,
            max_events=max_events,
            mode=mode,
            session_id=session_id,
            include_repo_state=include_repo_state,
            include_diff=include_diff,
            question=question,
            model=model,
        )
    except FileNotFoundError as e:
        return _err(f"Session JSONL not found: {e}")
    except OpenRouterError as e:
        return _err(f"OpenRouter call failed: {e}")
    except Exception as e:  # last-resort guard so MCP host gets a clean string
        return _err(f"Unexpected error: {e}")

    return json.dumps(result, indent=2, default=str)


def _err(msg: str) -> str:
    return json.dumps({"error": msg}, indent=2)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
