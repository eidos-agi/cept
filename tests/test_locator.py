from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from cept import locator


@pytest.fixture
def fake_claude(tmp_path: Path) -> tuple[Path, Path]:
    """Build a fake ~/.claude/projects layout and history.jsonl."""
    projects = tmp_path / "projects"
    projects.mkdir()
    history = tmp_path / "history.jsonl"
    history.write_text("")
    return projects, history


def test_cwd_to_project_dir_replaces_slashes_with_dashes():
    p = locator.cwd_to_project_dir("/Users/x/repos/foo")
    assert p.name == "-Users-x-repos-foo"


def test_find_session_picks_newest_mtime(fake_claude, tmp_path):
    projects, history = fake_claude
    cwd = tmp_path / "repo"
    cwd.mkdir()
    project_dir = projects / str(cwd.resolve()).replace("/", "-")
    project_dir.mkdir(parents=True)

    older = project_dir / "old-session.jsonl"
    newer = project_dir / "new-session.jsonl"
    older.write_text("{}\n")
    time.sleep(0.05)
    newer.write_text("{}\n")
    os.utime(older, (older.stat().st_atime, older.stat().st_mtime - 100))

    loc = locator.find_session(cwd=cwd, projects_dir=projects, history_file=history)
    assert loc.path == newer
    assert loc.source == "mtime"


def test_find_session_explicit_id(fake_claude, tmp_path):
    projects, history = fake_claude
    cwd = tmp_path / "repo"
    cwd.mkdir()
    project_dir = projects / str(cwd.resolve()).replace("/", "-")
    project_dir.mkdir(parents=True)

    target = project_dir / "abc123.jsonl"
    target.write_text("{}\n")

    loc = locator.find_session(
        cwd=cwd, session_id="abc123", projects_dir=projects, history_file=history
    )
    assert loc.session_id == "abc123"
    assert loc.path == target


def test_find_session_falls_back_to_history(fake_claude, tmp_path):
    projects, history = fake_claude
    cwd = tmp_path / "repo"
    cwd.mkdir()
    cwd_str = str(cwd.resolve())

    other_dir = projects / "-other-project"
    other_dir.mkdir()
    target = other_dir / "from-history.jsonl"
    target.write_text("{}\n")

    history.write_text(
        json.dumps({"project": cwd_str, "sessionId": "from-history", "timestamp": 1})
        + "\n"
    )

    loc = locator.find_session(cwd=cwd, projects_dir=projects, history_file=history)
    assert loc.session_id == "from-history"
    assert loc.source == "history"


def test_find_session_raises_when_nothing_found(fake_claude, tmp_path):
    projects, history = fake_claude
    cwd = tmp_path / "missing"
    cwd.mkdir()
    with pytest.raises(FileNotFoundError):
        locator.find_session(cwd=cwd, projects_dir=projects, history_file=history)
