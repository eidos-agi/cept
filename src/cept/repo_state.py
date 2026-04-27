"""Collect git-side repo state to pair with the transcript trajectory."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RepoState:
    cwd: str
    is_git_repo: bool = False
    branch: str | None = None
    dirty_files: list[str] = field(default_factory=list)
    diff_stat: str | None = None
    untracked_count: int = 0


def collect(cwd: str | Path, include_diff: bool = True) -> RepoState:
    cwd = str(Path(cwd).resolve())
    state = RepoState(cwd=cwd)

    if _git(cwd, ["rev-parse", "--is-inside-work-tree"]) != "true":
        return state
    state.is_git_repo = True

    state.branch = _git(cwd, ["branch", "--show-current"]) or None

    status = _git(cwd, ["status", "--short"])
    if status:
        lines = status.splitlines()
        state.dirty_files = [_extract_path(line) for line in lines if line.strip()]
        state.untracked_count = sum(1 for line in lines if line.startswith("??"))

    if include_diff:
        stat = _git(cwd, ["diff", "--stat"])
        if stat:
            state.diff_stat = _truncate(stat, 4000)

    return state


def _git(cwd: str, args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return ""
        return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def _extract_path(status_line: str) -> str:
    return status_line[3:].strip() if len(status_line) > 3 else status_line


def _truncate(s: str, limit: int) -> str:
    if len(s) <= limit:
        return s
    return s[: limit - 1] + "…"
