"""Locate or build the cept-hud Swift binary on demand.

Resolution order:
  1. ``$CEPT_HUD_BIN``               — explicit path to the binary
  2. ``cept-hud`` on ``$PATH``       — system-installed
  3. ``~/.cache/cept/cept-hud``      — previously auto-built and cached
  4. Build from sibling ``hud/`` source — first-call cost ~5-10s, then cached

If none of those work (no Swift toolchain, no source tree), returns ``None``
and the caller should fall back to a noop with a clear message.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "cept"


def cached_binary() -> Path:
    return cache_dir() / "cept-hud"


def find_source_dir() -> Path | None:
    """Locate the Swift HUD source.

    Resolution order:
      1. ``<package>/_hud_source/Package.swift`` — bundled in the wheel via
         hatchling's force-include. This is the path used by ``uvx --from cept``
         and any other PyPI install.
      2. Walk up from this file for ``hud/Package.swift`` — the editable /
         source-checkout layout (``cept/src/cept/hud_install.py`` ↔
         ``cept/hud/Package.swift``).
    """
    here = Path(__file__).resolve().parent
    bundled = here / "_hud_source" / "Package.swift"
    if bundled.is_file():
        return bundled.parent
    for ancestor in [here, *here.parents]:
        candidate = ancestor / "hud" / "Package.swift"
        if candidate.is_file():
            return candidate.parent
    return None


def is_built() -> bool:
    p = cached_binary()
    return p.is_file() and os.access(p, os.X_OK)


def build(force: bool = False, *, log: bool = True) -> Path | None:
    """Build the Swift HUD into the cache. Returns binary path or None on failure."""
    if not force and is_built():
        return cached_binary()

    if not shutil.which("swift"):
        if log:
            print(
                "cept: cannot build cept-hud — Swift toolchain not found. "
                "Run `xcode-select --install`.",
                file=sys.stderr,
            )
        return None

    source = find_source_dir()
    if not source:
        if log:
            print(
                "cept: cannot build cept-hud — hud/ source directory not found "
                "next to the cept package.",
                file=sys.stderr,
            )
        return None

    if log:
        print("cept: building cept-hud (one-time, ~5-10s)…", file=sys.stderr)

    try:
        result = subprocess.run(
            ["swift", "build", "-c", "release"],
            cwd=source,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        if log:
            print("cept: cept-hud build timed out.", file=sys.stderr)
        return None
    except OSError as e:
        if log:
            print(f"cept: cept-hud build failed: {e}", file=sys.stderr)
        return None

    if result.returncode != 0:
        if log:
            print(
                "cept: cept-hud build failed:\n" + (result.stderr or result.stdout)[:600],
                file=sys.stderr,
            )
        return None

    built = source / ".build" / "release" / "cept-hud"
    if not built.is_file():
        if log:
            print(
                f"cept: build succeeded but binary missing at {built}",
                file=sys.stderr,
            )
        return None

    target = cached_binary()
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(built, target)
    target.chmod(0o755)
    if log:
        print(f"cept: cept-hud → {target}", file=sys.stderr)
    return target


def ensure(*, log: bool = True) -> Path | None:
    """Return a usable cept-hud binary path, building if necessary."""
    explicit = os.environ.get("CEPT_HUD_BIN")
    if explicit:
        p = Path(explicit).expanduser()
        if p.is_file() and os.access(p, os.X_OK):
            return p

    on_path = shutil.which("cept-hud")
    if on_path:
        return Path(on_path)

    if is_built():
        return cached_binary()

    return build(log=log)
