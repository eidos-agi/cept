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
        json.dumps({"project": cwd_str, "sessionId": "from-history", "timestamp": 1}) + "\n"
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


# ---------------- cept_id two-way verification ----------------------------


def _write_jsonl_with_tool_use(path: Path, *, cept_id: str | None) -> None:
    """Write a synthetic Claude Code-shaped JSONL containing one tool_use."""
    events_lines = [
        json.dumps({"type": "permission-mode", "permissionMode": "auto"}),
        json.dumps(
            {
                "type": "user",
                "timestamp": "2026-04-27T20:00:00Z",
                "message": {"role": "user", "content": "do something"},
            }
        ),
    ]
    if cept_id is not None:
        events_lines.append(
            json.dumps(
                {
                    "type": "assistant",
                    "timestamp": "2026-04-27T20:00:01Z",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "id": "toolu_xxx",
                                "name": "cept",
                                "input": {"goal": "test", "cept_id": cept_id},
                            }
                        ],
                    },
                }
            )
        )
    path.write_text("\n".join(events_lines) + "\n")


def test_verify_session_finds_jsonl_with_matching_cept_id(fake_claude, tmp_path):
    projects, _ = fake_claude
    cwd = tmp_path / "repo"
    cwd.mkdir()
    project_dir = projects / str(cwd.resolve()).replace("/", "-")
    project_dir.mkdir(parents=True)

    other = project_dir / "other.jsonl"
    target = project_dir / "active.jsonl"
    _write_jsonl_with_tool_use(other, cept_id=None)
    _write_jsonl_with_tool_use(target, cept_id="abc1234567")

    loc = locator.verify_session(cwd=cwd, cept_id="abc1234567", projects_dir=projects)
    assert loc is not None
    assert loc.path == target
    assert loc.source == "cept_id"


def test_verify_session_returns_none_for_unknown_id(fake_claude, tmp_path):
    projects, _ = fake_claude
    cwd = tmp_path / "repo"
    cwd.mkdir()
    project_dir = projects / str(cwd.resolve()).replace("/", "-")
    project_dir.mkdir(parents=True)

    f = project_dir / "s.jsonl"
    _write_jsonl_with_tool_use(f, cept_id="abc1234567")

    assert locator.verify_session(cwd=cwd, cept_id="zzz9999999", projects_dir=projects) is None


def test_find_session_prefers_cept_id_over_mtime(fake_claude, tmp_path):
    """When cept_id is supplied, an older file matching the id wins over the newer one."""
    import time

    projects, history = fake_claude
    cwd = tmp_path / "repo"
    cwd.mkdir()
    project_dir = projects / str(cwd.resolve()).replace("/", "-")
    project_dir.mkdir(parents=True)

    older = project_dir / "older-but-correct.jsonl"
    newer = project_dir / "newer-but-wrong.jsonl"
    _write_jsonl_with_tool_use(older, cept_id="match-me-1")
    time.sleep(0.05)
    _write_jsonl_with_tool_use(newer, cept_id="some-other-id")

    loc = locator.find_session(
        cwd=cwd,
        cept_id="match-me-1",
        projects_dir=projects,
        history_file=history,
    )
    assert loc.path == older
    assert loc.source == "cept_id"


def test_find_session_raises_when_cept_id_not_found(fake_claude, tmp_path):
    projects, history = fake_claude
    cwd = tmp_path / "repo"
    cwd.mkdir()
    project_dir = projects / str(cwd.resolve()).replace("/", "-")
    project_dir.mkdir(parents=True)

    f = project_dir / "s.jsonl"
    _write_jsonl_with_tool_use(f, cept_id=None)

    with pytest.raises(FileNotFoundError):
        locator.find_session(
            cwd=cwd,
            cept_id="will-not-be-there",
            projects_dir=projects,
            history_file=history,
        )


def test_verify_session_ignores_id_in_non_tool_use_text(fake_claude, tmp_path):
    """The id appearing in user-message text shouldn't false-positive."""
    projects, _ = fake_claude
    cwd = tmp_path / "repo"
    cwd.mkdir()
    project_dir = projects / str(cwd.resolve()).replace("/", "-")
    project_dir.mkdir(parents=True)

    f = project_dir / "s.jsonl"
    f.write_text(
        json.dumps(
            {
                "type": "user",
                "timestamp": "2026-04-27T20:00:00Z",
                "message": {"role": "user", "content": "the id is abc1234567 in this text"},
            }
        )
        + "\n"
    )

    # No tool_use carrying the id, so verify_session should not match.
    assert locator.verify_session(cwd=cwd, cept_id="abc1234567", projects_dir=projects) is None
