"""Standalone CLI — useful for dry-run inspection without an MCP host."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import events, guides
from .core import run_cept
from .openrouter import OpenRouterError
from .providers import ProviderError

_DEFAULT_EMITS = ["stderr"]  # text progress to stderr keeps stdout clean for the JSON
_SELF_ASSESS_FILES = (
    "README.md",
    "src/cept/core.py",
    "src/cept/adapters.py",
    "src/cept/cli.py",
    "src/cept/server.py",
    "src/cept/openrouter.py",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cept-cli",
        description="Distill a recent agent transcript and (optionally) ask OpenRouter for steering.",
    )
    parser.add_argument("--goal", default=None, help="What the agent is trying to accomplish.")
    parser.add_argument(
        "--headline",
        default=None,
        help=(
            "3-4 word newspaper-headline summary of the ask. Surfaces in the "
            "cept HUD callout and in the model's packet. Soft cap 4 words; "
            "hard cap 6 (truncated). Example: \"audit research README\"."
        ),
    )
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
        "--transcript",
        default=None,
        metavar="PATH",
        help="Read an explicit agent transcript JSONL file instead of auto-locating Claude Code.",
    )
    parser.add_argument(
        "--transcript-source",
        choices=["auto", "claude-code", "file"],
        default="auto",
        help="Transcript adapter to use. Default auto uses --transcript when present, otherwise Claude Code.",
    )
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
        help="OpenRouter model id (default: CEPT_DEFAULT_MODEL from .ceptkey, else perplexity/sonar-pro).",
    )
    parser.add_argument(
        "--provider",
        choices=["auto", "openrouter"],
        default=None,
        help="Model provider. This build supports OpenRouter only; default auto resolves to OpenRouter.",
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
    parser.add_argument(
        "--self-assess",
        action="store_true",
        help="Dogfood cept against cept's own core files. Provides goal, headline, architecture mode, and files unless overridden.",
    )
    parser.add_argument(
        "--guide",
        nargs="?",
        const="ceptkey",
        choices=["ceptkey"],
        default=None,
        help="Print a built-in guide and exit. Defaults to 'ceptkey' for .ceptkey setup and troubleshooting.",
    )
    parser.add_argument(
        "--guide-path",
        action="store_true",
        help="With --guide, print the source path when available instead of guide contents.",
    )
    args = parser.parse_args(argv)

    if args.guide:
        if args.guide_path:
            path = guides.guide_path(args.guide)
            print(path if path else "(bundled guide resource)")
        else:
            print(guides.read_guide(args.guide), end="")
        return 0

    if args.self_assess:
        repo_root = Path(__file__).resolve().parents[2]
        args.goal = args.goal or "Assess cept's current design and implementation for blind spots before continuing."
        args.headline = args.headline or "assess cept design"
        if args.mode == "steer":
            args.mode = "architecture"
        if not args.files:
            args.files = [str(repo_root / path) for path in _SELF_ASSESS_FILES]
    else:
        if not args.goal:
            parser.error("the following arguments are required: --goal")
        if not args.headline:
            parser.error("the following arguments are required: --headline")

    if args.quiet:
        emit_specs: list[str] = ["noop"]
    else:
        emit_specs = args.emit if args.emit else _DEFAULT_EMITS

    adapters = events.parse_emit_specs(emit_specs)
    emitter = events.Emitter(adapters=adapters)

    try:
        result = run_cept(
            goal=args.goal,
            headline=args.headline,
            cwd=args.cwd or os.getcwd(),
            lookback_minutes=args.lookback,
            max_events=args.max_events,
            mode=args.mode,
            transcript=args.transcript,
            transcript_source=args.transcript_source,
            session_id=args.session_id,
            cept_id=args.cept_id,
            include_repo_state=not args.no_repo_state,
            include_diff=not args.no_diff,
            question=args.question,
            files=args.files,
            dry_run=args.dry_run,
            model=args.model,
            provider=args.provider,
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
    except ProviderError as e:
        print(f"provider error: {e}", file=sys.stderr)
        emitter.close()
        return 3
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        emitter.close()
        return 4
    finally:
        emitter.close()

    json.dump(result, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
