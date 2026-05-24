"""cept-keyfile — scaffold and inspect ceptkey files.

Subcommands:
  init    Write a new .ceptkey with auto-populated provenance metadata.
  show    Print metadata of the nearest .ceptkey (no values — safe to share).
  where   Print the path of the nearest .ceptkey.
  guide   Print the .ceptkey setup and troubleshooting guide.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from . import guides, keyfile


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cept-keyfile", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    init_p = sub.add_parser("init", help="Create a new .ceptkey with metadata.")
    init_p.add_argument(
        "--service", default="openrouter", help="Service name (default: openrouter)."
    )
    init_p.add_argument("--name", required=True, help="Human-readable key name (e.g. cept-djs-01).")
    init_p.add_argument("--key", required=True, help="The OPENROUTER_API_KEY value.")
    init_p.add_argument(
        "--env-var", default="OPENROUTER_API_KEY", help="Env var name to write the key under."
    )
    init_p.add_argument(
        "--provider",
        choices=("auto", "openrouter"),
        default=None,
        help="Sets CEPT_PROVIDER. This build routes Perplexity models through OpenRouter.",
    )
    init_p.add_argument("--model", default=None, help="Sets CEPT_DEFAULT_MODEL.")
    init_p.add_argument("--lookback", type=int, default=None, help="Sets CEPT_LOOKBACK_MINUTES.")
    init_p.add_argument("--referer", default=None, help="Sets OPENROUTER_REFERER.")
    init_p.add_argument("--title", default=None, help="Sets OPENROUTER_TITLE.")
    init_p.add_argument(
        "--scope", default=None, help="Free-form scope description (e.g. ~/repos-eidos-agi/)."
    )
    init_p.add_argument("--notes", default=None, help="Free-form notes.")
    init_p.add_argument(
        "--path",
        default=".ceptkey",
        help="Output path (default: .ceptkey in cwd).",
    )
    init_p.add_argument("--force", action="store_true", help="Overwrite if file exists.")

    show_p = sub.add_parser("show", help="Show nearest .ceptkey metadata (no values).")
    show_p.add_argument("--cwd", default=None)
    show_p.add_argument("--json", dest="as_json", action="store_true")

    where_p = sub.add_parser("where", help="Print path of nearest .ceptkey.")
    where_p.add_argument("--cwd", default=None)

    guide_p = sub.add_parser("guide", help="Print the .ceptkey guide.")
    guide_p.add_argument(
        "--path",
        action="store_true",
        help="Print the source guide path when available instead of guide contents.",
    )

    args = parser.parse_args(argv)

    if args.cmd == "init":
        return _cmd_init(args)
    if args.cmd == "show":
        return _cmd_show(args)
    if args.cmd == "where":
        return _cmd_where(args)
    if args.cmd == "guide":
        return _cmd_guide(args)
    return 2


def _cmd_init(args: argparse.Namespace) -> int:
    target = Path(args.path).expanduser().resolve()
    if target.exists() and not args.force:
        print(f"error: {target} already exists. Use --force to overwrite.", file=sys.stderr)
        return 2

    now = datetime.now(UTC).isoformat()
    host = platform.node() or socket.gethostname() or "unknown"
    user = _git_user_email() or os.environ.get("USER") or "unknown"
    osinfo = f"{platform.system()} {platform.release()} ({platform.machine()})"

    meta_lines = [
        f"# cept-meta:service={args.service}",
        f"# cept-meta:key_name={args.name}",
        f"# cept-meta:created_at={now}",
        f"# cept-meta:created_on={host}",
        f"# cept-meta:created_by={user}",
        f"# cept-meta:created_os={osinfo}",
    ]
    if args.scope:
        meta_lines.append(f"# cept-meta:scope={args.scope}")
    if args.notes:
        meta_lines.append(f"# cept-meta:notes={args.notes}")

    body_lines = [f"{args.env_var}={args.key}"]
    if args.provider:
        body_lines.append(f"CEPT_PROVIDER={args.provider}")
    if args.model:
        body_lines.append(f"CEPT_DEFAULT_MODEL={args.model}")
    if args.lookback is not None:
        body_lines.append(f"CEPT_LOOKBACK_MINUTES={args.lookback}")
    if args.referer:
        body_lines.append(f"OPENROUTER_REFERER={args.referer}")
    if args.title:
        body_lines.append(f"OPENROUTER_TITLE={args.title}")

    contents = "\n".join(meta_lines) + "\n\n" + "\n".join(body_lines) + "\n"

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(contents, encoding="utf-8")
    try:
        target.chmod(0o600)
    except OSError:
        pass
    print(f"wrote {target} (0600)")
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    cwd = args.cwd or os.getcwd()
    path = keyfile.find_keyfile(cwd)
    if not path:
        print("(no .ceptkey found in walk-up)", file=sys.stderr)
        return 1
    parsed = keyfile.parse_keyfile(path)
    info = {
        "path": str(path),
        "keys_present": sorted(parsed.values.keys()),
        "metadata": parsed.metadata,
    }
    if args.as_json:
        json.dump(info, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"path:         {info['path']}")
        print(f"keys present: {', '.join(info['keys_present']) or '(none)'}")
        if info["metadata"]:
            print("metadata:")
            for k, v in info["metadata"].items():
                print(f"  {k}: {v}")
        else:
            print("metadata: (none)")
    return 0


def _cmd_where(args: argparse.Namespace) -> int:
    cwd = args.cwd or os.getcwd()
    path = keyfile.find_keyfile(cwd)
    if not path:
        print("(no .ceptkey found in walk-up)", file=sys.stderr)
        return 1
    print(path)
    return 0


def _cmd_guide(args: argparse.Namespace) -> int:
    if args.path:
        path = guides.guide_path("ceptkey")
        print(path if path else "(bundled guide resource)")
    else:
        print(guides.read_guide("ceptkey"), end="")
    return 0


def _git_user_email() -> str | None:
    try:
        out = subprocess.run(
            ["git", "config", "user.email"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


if __name__ == "__main__":
    raise SystemExit(main())
