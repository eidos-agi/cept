"""cept-hud-install — pre-build the Swift HUD binary explicitly.

The HUD auto-builds on first ``--emit hud`` use, so this command is optional.
Useful for CI, or for users who want to surface failures early instead of
during a real cept call.
"""

from __future__ import annotations

import argparse
import sys

from . import hud_install


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cept-hud-install",
        description="Build and cache the cept-hud Swift binary.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild even if a cached binary already exists.",
    )
    parser.add_argument(
        "--path",
        action="store_true",
        help="Print the resolved binary path and exit.",
    )
    args = parser.parse_args(argv)

    if args.path:
        bin_path = hud_install.ensure(log=False)
        if not bin_path:
            print("(not available)", file=sys.stderr)
            return 1
        print(bin_path)
        return 0

    bin_path = hud_install.build(force=args.force)
    if not bin_path:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
