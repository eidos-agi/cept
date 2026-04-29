"""Standalone CLI — useful for dry-run inspection without an MCP host."""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import events
from .core import run_cept
from .openrouter import OpenRouterError

_DEFAULT_EMITS = ["stderr"]  # text progress to stderr keeps stdout clean for the JSON


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cept-cli",
        description="Distill recent Claude Code session and (optionally) ask OpenRouter for steering.",
    )
    parser.add_argument("--goal", required=True, help="What the agent is trying to accomplish.")
    parser.add_argument("--cwd", default=None, help="Working directory (default: current).")
    parser.add_argument(
        "--lookback",
        type=int,
        default=None,
        help="Lookback minutes (default: CEPT_LOOKBACK_MINUTES from .ceptkey, else 20).",
    )
    parser.add_argument("--max-events", type=int, default=250)
    parser.add_argument(
        "--mode",
        choices=["steer", "debug", "research", "architecture"],
        default="steer",
    )
    parser.add_argument("--session-id", default=None)
    parser.add_argument(
        "--cept-id",
        default=None,
        help="Two-way session verification nonce. When set, cept finds the JSONL whose recent tool_use input carries this id (and errors otherwise). Mostly relevant when called via MCP.",
    )
    parser.add_argument("--question", default=None)
    parser.add_argument(
        "--file",
        action="append",
        dest="files",
        default=None,
        metavar="PATH",
        help=(
            "Source file to include in the packet so the model can quote and "
            "critique specific lines. Repeatable. Caps: 50 KB/file, 256 KB total, "
            "24 files max."
        ),
    )
    parser.add_argument("--no-repo-state", action="store_true")
    parser.add_argument("--no-diff", action="store_true")
    parser.add_argument(
        "--dry-run", action="store_true", help="Print packet, skip OpenRouter call."
    )
    parser.add_argument(
        "--model",
        default=None,
        help="OpenRouter model id (default: CEPT_DEFAULT_MODEL from .ceptkey, else perplexity/sonar-reasoning).",
    )
    parser.add_argument(
        "--emit",
        action="append",
        default=None,
        metavar="SPEC",
        help=(
            "Adapter for progress events. Repeatable. Specs: "
            "stdout, stderr, jsonl:-, jsonl:PATH, file:PATH, socket:PATH, "
            "subprocess:CMD, hud, notify, noop. Default: stderr."
        ),
    )
    parser.add_argument("--quiet", action="store_true", help="Disable all event emission.")
    args = parser.parse_args(argv)

    if args.quiet:
        emit_specs: list[str] = ["noop"]
    else:
        emit_specs = args.emit if args.emit else _DEFAULT_EMITS

    adapters = events.parse_emit_specs(emit_specs)
    emitter = events.Emitter(adapters=adapters)

    try:
        result = run_cept(
            goal=args.goal,
            cwd=args.cwd or os.getcwd(),
            lookback_minutes=args.lookback,
            max_events=args.max_events,
            mode=args.mode,
            session_id=args.session_id,
            cept_id=args.cept_id,
            include_repo_state=not args.no_repo_state,
            include_diff=not args.no_diff,
            question=args.question,
            files=args.files,
            dry_run=args.dry_run,
            model=args.model,
            emitter=emitter,
        )
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        emitter.close()
        return 2
    except OpenRouterError as e:
        print(f"openrouter error: {e}", file=sys.stderr)
        emitter.close()
        return 3
    finally:
        emitter.close()

    json.dump(result, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
