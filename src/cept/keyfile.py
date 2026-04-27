"""Hierarchical ceptkey loader — per-tree credentials and defaults.

Walks up from ``cwd`` looking for a ``.ceptkey`` (preferred) or ``ceptkey``
file. Parses it as dotenv. Sets the values into the process env, **file
wins** — the whole point of dropping a per-folder key is "use *this* here,
not my global". Stops at ``$HOME`` (when cwd is under home) or filesystem
root, whichever comes first.

Supported keys (anything dotenv-shaped works, but cept reads these):

  OPENROUTER_API_KEY      OpenRouter credential
  OPENROUTER_REFERER      optional, sent as HTTP-Referer
  OPENROUTER_TITLE        optional, sent as X-Title
  CEPT_DEFAULT_MODEL      e.g. "anthropic/claude-sonnet-4-5:online"
  CEPT_LOOKBACK_MINUTES   per-tree default lookback window
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import MutableMapping


KEYFILE_NAMES = (".ceptkey", "ceptkey")


@dataclass
class KeyfileResult:
    path: Path | None
    keys_set: list[str] = field(default_factory=list)


def find_keyfile(cwd: str | Path, home: Path | None = None) -> Path | None:
    """Walk up from cwd looking for a ceptkey file. Stops at $HOME or /."""
    cwd_path = Path(cwd).resolve()
    home_path = (home or Path.home()).resolve()
    under_home = cwd_path == home_path or home_path in cwd_path.parents

    current = cwd_path
    while True:
        for name in KEYFILE_NAMES:
            candidate = current / name
            if candidate.is_file():
                return candidate
        if under_home and current == home_path:
            return None
        if current.parent == current:
            return None
        current = current.parent


def parse_keyfile(path: Path) -> dict[str, str]:
    """Minimal dotenv parser — KEY=value, comments, optional quotes, optional `export `."""
    out: dict[str, str] = {}
    text = path.read_text(encoding="utf-8")
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export ") :].strip()
        if not key:
            continue
        value = value.strip()
        # Strip a matching pair of surrounding quotes
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        out[key] = value
    return out


def apply(
    values: dict[str, str],
    env: MutableMapping[str, str] | None = None,
) -> list[str]:
    """Apply values to env (file wins — overrides existing). Returns keys set."""
    target = env if env is not None else os.environ
    keys: list[str] = []
    for k, v in values.items():
        target[k] = v
        keys.append(k)
    return keys


def load_for(
    cwd: str | Path,
    env: MutableMapping[str, str] | None = None,
    home: Path | None = None,
) -> KeyfileResult:
    """End-to-end: find → parse → apply. Safe to call repeatedly."""
    path = find_keyfile(cwd, home=home)
    if not path:
        return KeyfileResult(path=None, keys_set=[])
    values = parse_keyfile(path)
    keys = apply(values, env=env)
    return KeyfileResult(path=path, keys_set=keys)
