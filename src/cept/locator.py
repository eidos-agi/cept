"""Locate the active Claude Code session JSONL.

Claude Code persists each project's sessions under
``~/.claude/projects/<dashed-cwd>/<session-id>.jsonl`` and writes a global
prompt index to ``~/.claude/history.jsonl``. ``cwd_to_project_dir`` maps a
working directory to its project folder by replacing path separators with
dashes — that single rule covers most discovery cases.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


CLAUDE_HOME = Path.home() / ".claude"
PROJECTS_DIR = CLAUDE_HOME / "projects"
HISTORY_FILE = CLAUDE_HOME / "history.jsonl"


@dataclass
class SessionLocation:
    path: Path
    session_id: str
    project_dir: Path
    source: str


def cwd_to_project_dir(cwd: str | Path) -> Path:
    """Map a working directory to its Claude Code project folder.

    /Users/x/repos/foo  ->  ~/.claude/projects/-Users-x-repos-foo
    """
    p = Path(cwd).resolve()
    dashed = str(p).replace("/", "-")
    return PROJECTS_DIR / dashed


def find_session(
    cwd: str | Path,
    session_id: str | None = None,
    projects_dir: Path = PROJECTS_DIR,
    history_file: Path = HISTORY_FILE,
) -> SessionLocation:
    project_dir = _resolve_project_dir(cwd, projects_dir)

    if session_id:
        candidate = project_dir / f"{session_id}.jsonl"
        if candidate.exists():
            return SessionLocation(candidate, session_id, project_dir, "explicit")
        scan = _scan_for_session_id(projects_dir, session_id)
        if scan:
            return SessionLocation(scan, session_id, scan.parent, "explicit-scan")
        raise FileNotFoundError(f"No JSONL found for session_id {session_id}")

    newest = _newest_jsonl(project_dir)
    if newest:
        return SessionLocation(newest, newest.stem, project_dir, "mtime")

    historical = _from_history(history_file, cwd, projects_dir)
    if historical:
        return historical

    raise FileNotFoundError(
        f"No Claude Code session JSONL found for cwd={cwd}. "
        f"Looked in {project_dir} and {history_file}."
    )


def _resolve_project_dir(cwd: str | Path, projects_dir: Path) -> Path:
    direct = cwd_to_project_dir(cwd)
    if direct.exists():
        return direct
    if projects_dir != PROJECTS_DIR:
        relative = str(Path(cwd).resolve()).replace("/", "-")
        return projects_dir / relative
    return direct


def _newest_jsonl(project_dir: Path) -> Path | None:
    if not project_dir.exists():
        return None
    files = [p for p in project_dir.iterdir() if p.suffix == ".jsonl"]
    if not files:
        return None
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0]


def _scan_for_session_id(projects_dir: Path, session_id: str) -> Path | None:
    if not projects_dir.exists():
        return None
    for project in projects_dir.iterdir():
        if not project.is_dir():
            continue
        candidate = project / f"{session_id}.jsonl"
        if candidate.exists():
            return candidate
    return None


def _from_history(
    history_file: Path,
    cwd: str | Path,
    projects_dir: Path,
) -> SessionLocation | None:
    if not history_file.exists():
        return None
    cwd_str = str(Path(cwd).resolve())
    latest: dict | None = None
    try:
        with history_file.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("project") != cwd_str:
                    continue
                if not latest or entry.get("timestamp", 0) > latest.get("timestamp", 0):
                    latest = entry
    except OSError:
        return None
    if not latest or not latest.get("sessionId"):
        return None
    sid = latest["sessionId"]
    scan = _scan_for_session_id(projects_dir, sid)
    if scan:
        return SessionLocation(scan, sid, scan.parent, "history")
    return None
