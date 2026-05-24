"""MCP server exposing the cept tool over stdio."""

from __future__ import annotations

import json
import os

from mcp.server.fastmcp import FastMCP

from . import events
from .core import run_cept
from .openrouter import OpenRouterError

mcp = FastMCP("cept")


def _emitter_from_env() -> events.Emitter:
    """Build an Emitter from CEPT_EMIT (comma-separated specs).

    MCP servers must NOT write to stdout (that's the JSON-RPC channel).
    Default is noop. Common useful settings:

      CEPT_EMIT=hud                                  # popup
      CEPT_EMIT=notify                               # banners
      CEPT_EMIT=file:~/.cept/status.jsonl            # log
      CEPT_EMIT=hud,file:~/.cept/status.jsonl        # both
    """
    spec = os.environ.get("CEPT_EMIT", "").strip()
    if not spec:
        return events.Emitter()
    return events.Emitter(adapters=events.parse_emit_specs(spec))


@mcp.tool()
def cept(
    goal: str,
    headline: str,
    cept_id: str | None = None,
    transcript: str | None = None,
    transcript_source: str = "auto",
    lookback_minutes: int | None = None,
    mode: str = "steer",
    question: str | None = None,
    files: list[str] | None = None,
    session_id: str | None = None,
    include_repo_state: bool = True,
    include_diff: bool = True,
    max_events: int = 250,
    model: str | None = None,
    provider: str | None = None,
) -> str:
    """Inspect the recent Claude Code transcript and return outside-in steering guidance.

    Use this when stuck, looping, or facing a low-confidence architectural choice.
    The tool reads the active agent transcript, distills the last
    `lookback_minutes` of events, redacts secrets, and asks an OpenRouter model
    (with web search) for ranked guidance.

    TRANSCRIPT ADAPTERS: by default cept auto-locates the active Claude Code
    session. For other agents, pass ``transcript`` with a JSONL file containing
    normalized rows such as role/text messages, tool_call rows, and tool_result
    rows. ``transcript_source`` may be "auto", "claude-code", or "file".

    SESSION VERIFICATION (important): for Claude Code, if multiple sessions are
    open in the same project, mtime-based discovery can pick the wrong file.
    For a deterministic two-way handshake, pass a fresh ``cept_id`` — a
    10-character random hex string — when invoking this tool. cept then finds
    the JSONL whose tool_use input carries that exact id, confirming the file
    matches *this* call. Generate a new id every invocation. This verification
    is only available for the claude-code adapter.

    HEADLINE (required): a 3-4 word phrase describing what you're asking,
    in newspaper-headline style. Shows up in the floating HUD popup so the
    human watching can see what's being asked at a glance, and lands in
    the packet's `meta.headline` so the model sees your own self-summary
    next to the longer goal. If you can't compress your ask to 3-4 words,
    you're not clear on what you need — that's the moment cept was made
    for, and the discipline of writing the headline IS part of the value.
    Examples: "audit research README", "debug oauth callback loop",
    "compare Postgres vs SQLite". Soft cap 4 words; hard cap 6.

    INCLUDING SOURCE FILES: trajectory alone tells the model what the agent
    *did*. To get content-shape critique (e.g. "this README claim is unsourced"
    or "this function has a bounds bug"), pass ``files=[...]`` with the paths
    you want audited. Each file is capped at 50 KB; total at 256 KB; max 24
    files. Paths can be absolute or relative to cwd.

    Args:
        goal: What the agent is currently trying to accomplish.
        headline: 3-4 word newspaper-headline summary of the ask. Required.
            Surfaces in the cept HUD callout and in the model's packet.
            See the HEADLINE block above.
        cept_id: A short (~10 char) random nonce. Must be unique per call.
            When provided, cept verifies it appears in a recent tool_use
            input in exactly one JSONL — that's the calling session.
            Supported by the claude-code adapter.
        transcript: Explicit JSONL transcript path for non-Claude agents or
            for deterministic replay.
        transcript_source: One of "auto", "claude-code", or "file".
        lookback_minutes: How far back to inspect (1–120). If None, falls back
            to CEPT_LOOKBACK_MINUTES env (set via .ceptkey) or 20.
        mode: One of "steer" (default), "debug", "research", "architecture".
        question: Optional specific question to forward.
        files: Optional list of file paths to include in the packet so the
            model can quote and critique specific lines. Pass when you want
            an adversarial content audit, not just a workflow critique.
            Caps: 50 KB/file, 256 KB total, 24 files max. Redaction still
            applies to file content.
        session_id: Optional explicit Claude Code session UUID (overrides cept_id).
        include_repo_state: Whether to attach git status/diff/branch.
        include_diff: Whether to include `git diff --stat`.
        max_events: Cap on events to keep after the lookback filter.
        model: OpenRouter model id. If None, falls back to CEPT_DEFAULT_MODEL
            env (set via .ceptkey) or "perplexity/sonar-pro". Append ":online"
            to any model name to force web search where supported.
        provider: "auto" or "openrouter". This build uses OpenRouter as the
            provider surface, with Perplexity Sonar as the default model.
    """
    cwd = os.getcwd()
    if lookback_minutes is not None:
        lookback_minutes = max(1, min(int(lookback_minutes), 120))
    max_events = max(20, min(int(max_events), 1000))
    if mode not in {"steer", "debug", "research", "architecture"}:
        mode = "steer"

    emitter = _emitter_from_env()
    try:
        result = run_cept(
            goal=goal,
            headline=headline,
            cwd=cwd,
            lookback_minutes=lookback_minutes,
            max_events=max_events,
            mode=mode,
            transcript=transcript,
            transcript_source=transcript_source,
            session_id=session_id,
            include_repo_state=include_repo_state,
            include_diff=include_diff,
            question=question,
            files=files,
            model=model,
            provider=provider,
            cept_id=cept_id,
            emitter=emitter,
        )
    except FileNotFoundError as e:
        return _err(f"Session JSONL not found: {e}")
    except OpenRouterError as e:
        return _err(f"OpenRouter call failed: {e}")
    except Exception as e:  # last-resort guard so MCP host gets a clean string
        return _err(f"Unexpected error: {e}")
    finally:
        emitter.close()

    return json.dumps(result, indent=2, default=str)


def _err(msg: str) -> str:
    return json.dumps({"error": msg}, indent=2)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
