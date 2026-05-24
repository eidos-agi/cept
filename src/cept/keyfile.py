"""Hierarchical ceptkey loader — per-tree credentials, defaults, and provenance.

Walks up from ``cwd`` looking for a ``.ceptkey`` (preferred) or ``ceptkey``
file. Parses it as dotenv. Sets the values into the process env, **file
wins** — the whole point of dropping a per-folder key is "use *this* here,
not my global". Stops at ``$HOME`` (when cwd is under home) or filesystem
root, whichever comes first.

A ceptkey file may also carry **provenance metadata** as comment lines of the
form ``# cept-meta:key=value``. The parser captures these into a separate
metadata dict that is *not* applied to the environment — useful for auditing
which key is which without leaking values.

Supported env keys:

  CEPT_PROVIDER           "auto" or "openrouter" (default: auto)
  OPENROUTER_API_KEY      OpenRouter credential
  OPENROUTER_REFERER      optional, sent as HTTP-Referer
  OPENROUTER_TITLE        optional, sent as X-Title
  CEPT_DEFAULT_MODEL      e.g. "anthropic/claude-sonnet-4-5:online"
  CEPT_LOOKBACK_MINUTES   per-tree default lookback window

Recognized metadata keys (any string is accepted; these are conventions):

  service, key_name, created_at, created_on, created_by, notes,
  scope, expires_at
"""

from __future__ import annotations

import os
from collections.abc import MutableMapping
from dataclasses import dataclass, field
from pathlib import Path

KEYFILE_NAMES = (".ceptkey", "ceptkey")
META_PREFIX = "cept-meta:"


@dataclass
class ParsedKeyfile:
    values: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class KeyfileResult:
    path: Path | None
    keys_set: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)


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


def parse_keyfile(path: Path) -> ParsedKeyfile:
    """Parse env values and `# cept-meta:` metadata from a ceptkey file."""
    parsed = ParsedKeyfile()
    text = path.read_text(encoding="utf-8")
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            payload = line[1:].lstrip()
            if payload.startswith(META_PREFIX):
                meta_body = payload[len(META_PREFIX) :].strip()
                if "=" in meta_body:
                    mk, _, mv = meta_body.partition("=")
                    mk = mk.strip()
                    mv = mv.strip()
                    if len(mv) >= 2 and mv[0] == mv[-1] and mv[0] in ("'", '"'):
                        mv = mv[1:-1]
                    if mk:
                        parsed.metadata[mk] = mv
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
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        parsed.values[key] = value
    return parsed


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
        return KeyfileResult(path=None, keys_set=[], metadata={})
    parsed = parse_keyfile(path)
    keys = apply(parsed.values, env=env)
    return KeyfileResult(path=path, keys_set=keys, metadata=parsed.metadata)
