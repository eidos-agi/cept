"""Locate the active Claude Code session JSONL.

Claude Code persists each project's sessions under
``~/.claude/projects/<dashed-cwd>/<session-id>.jsonl`` and writes a global
prompt index to ``~/.claude/history.jsonl``. ``cwd_to_project_dir`` maps a
working directory to its project folder by replacing path separators with
dashes — that single rule covers most discovery cases.
"""

from __future__ import annotations

import json
import time
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
    cept_id: str | None = None,
    projects_dir: Path = PROJECTS_DIR,
    history_file: Path = HISTORY_FILE,
) -> SessionLocation:
    """Locate the JSONL backing the active session.

    Resolution order:
      1. ``session_id`` — explicit Claude Code UUID, exact match required.
      2. ``cept_id``   — caller-supplied nonce. Scan recent JSONLs in the
         project dir for a tool_use input containing this id; that file is
         confirmed to be the calling session. Two-way handshake.
      3. mtime fallback — newest JSONL in the project dir. Works because
         Claude Code is the only process actively writing.
      4. history.jsonl — last known session for this cwd.
    """
    project_dir = _resolve_project_dir(cwd, projects_dir)

    if session_id:
        candidate = project_dir / f"{session_id}.jsonl"
        if candidate.exists():
            return SessionLocation(candidate, session_id, project_dir, "explicit")
        scan = _scan_for_session_id(projects_dir, session_id)
        if scan:
            return SessionLocation(scan, session_id, scan.parent, "explicit-scan")
        raise FileNotFoundError(f"No JSONL found for session_id {session_id}")

    if cept_id:
        verified = verify_session(cwd, cept_id, projects_dir=projects_dir)
        if verified:
            return verified
        raise FileNotFoundError(
            f"No JSONL contains cept_id {cept_id!r} in a recent tool_use input. "
            "Either the id was wrong or the calling session has not yet flushed."
        )

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


def verify_session(
    cwd: str | Path,
    cept_id: str,
    projects_dir: Path = PROJECTS_DIR,
    max_candidates: int = 6,
    scan_bytes: int = 128 * 1024,
    flush_wait_seconds: float = 2.5,
    poll_interval: float = 0.2,
) -> SessionLocation | None:
    """Return the JSONL whose recent tool_use input carries the given cept_id.

    Polls for up to ``flush_wait_seconds`` to absorb Claude Code's JSONL
    write-buffering delay (typically ~1s). The first scan happens immediately;
    if the id isn't found, we sleep ``poll_interval`` and rescan, up to the
    deadline. Success on the first pass adds zero latency.
    """
    project_dir = _resolve_project_dir(cwd, projects_dir)
    if not project_dir.exists():
        return None

    deadline = time.monotonic() + flush_wait_seconds
    while True:
        candidates = sorted(
            (p for p in project_dir.iterdir() if p.suffix == ".jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:max_candidates]

        for f in candidates:
            if _file_has_cept_id(f, cept_id, scan_bytes):
                return SessionLocation(f, f.stem, project_dir, source="cept_id")

        if time.monotonic() >= deadline:
            return None
        time.sleep(poll_interval)


def _file_has_cept_id(path: Path, cept_id: str, scan_bytes: int) -> bool:
    """Tail-scan a JSONL for a tool_use whose input carries ``cept_id``."""
    try:
        size = path.stat().st_size
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            if size > scan_bytes:
                fh.seek(size - scan_bytes)
                fh.readline()  # discard partial first line
            text = fh.read()
    except OSError:
        return False

    if cept_id not in text:
        return False  # cheap reject

    for line in text.splitlines():
        if cept_id not in line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = ev.get("message") or {}
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "tool_use":
                continue
            inp = item.get("input")
            if isinstance(inp, dict) and inp.get("cept_id") == cept_id:
                return True
            # Also accept stringified input that contains the id (Claude Code
            # sometimes serializes input as a string)
            if isinstance(inp, str) and cept_id in inp:
                return True
    return False


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
