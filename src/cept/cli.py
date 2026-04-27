"""Standalone CLI — useful for dry-run inspection without an MCP host."""

from __future__ import annotations

import argparse
import json
import os
import sys

from .core import run_cept
from .openrouter import DEFAULT_MODEL, OpenRouterError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cept-cli",
        description="Distill recent Claude Code session and (optionally) ask OpenRouter for steering.",
    )
    parser.add_argument("--goal", required=True, help="What the agent is trying to accomplish.")
    parser.add_argument("--cwd", default=None, help="Working directory (default: current).")
    parser.add_argument("--lookback", type=int, default=20, help="Lookback minutes (default 20).")
    parser.add_argument("--max-events", type=int, default=250)
    parser.add_argument(
        "--mode",
        choices=["steer", "debug", "research", "architecture"],
        default="steer",
    )
    parser.add_argument("--session-id", default=None)
    parser.add_argument("--question", default=None)
    parser.add_argument("--no-repo-state", action="store_true")
    parser.add_argument("--no-diff", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Print packet, skip OpenRouter call.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args(argv)

    try:
        result = run_cept(
            goal=args.goal,
            cwd=args.cwd or os.getcwd(),
            lookback_minutes=args.lookback,
            max_events=args.max_events,
            mode=args.mode,
            session_id=args.session_id,
            include_repo_state=not args.no_repo_state,
            include_diff=not args.no_diff,
            question=args.question,
            dry_run=args.dry_run,
            model=args.model,
        )
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except OpenRouterError as e:
        print(f"openrouter error: {e}", file=sys.stderr)
        return 3

    json.dump(result, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
