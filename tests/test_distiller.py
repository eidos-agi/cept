from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path  # noqa: F401  (kept for parse_jsonl test)

from cept import distiller


def _ts(minutes_ago: int) -> str:
    return (datetime.now(UTC) - timedelta(minutes=minutes_ago)).isoformat()


def test_filter_recent_drops_old_events() -> None:
    events = [
        {"type": "user", "timestamp": _ts(60), "message": {"role": "user", "content": "old"}},
        {"type": "user", "timestamp": _ts(5), "message": {"role": "user", "content": "fresh"}},
    ]
    recent = distiller.filter_recent(events, lookback_minutes=20, max_events=100)
    assert len(recent) == 1
    assert recent[0]["message"]["content"] == "fresh"


def test_distill_extracts_decisions_attempts_and_files() -> None:
    events = [
        {
            "type": "user",
            "timestamp": _ts(2),
            "message": {"role": "user", "content": "we need to fix the oauth callback"},
            "cwd": "/repo",
            "gitBranch": "feat/oauth",
        },
        {
            "type": "assistant",
            "timestamp": _ts(1),
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "I'll switch to disk-backed PKCE storage."},
                    {
                        "type": "tool_use",
                        "name": "Edit",
                        "input": {"file_path": "/repo/src/auth.ts"},
                    },
                ],
            },
        },
        {
            "type": "assistant",
            "timestamp": _ts(1),
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "x",
                        "is_error": True,
                        "content": "invalid_grant: missing code_verifier",
                    }
                ],
            },
        },
    ]
    traj = distiller.distill(events)
    assert traj.cwd == "/repo"
    assert traj.git_branch == "feat/oauth"
    assert any("PKCE" in d for d in traj.decisions)
    assert any("Edit:" in a for a in traj.attempts)
    assert "/repo/src/auth.ts" in traj.files_touched
    assert any("missing code_verifier" in s for s in traj.stderr_highlights)


def test_loop_detection_flags_repeat_commands() -> None:
    def assistant_with_bash(cmd: str) -> dict:
        return {
            "type": "assistant",
            "timestamp": _ts(1),
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Bash",
                        "input": {"command": cmd},
                    }
                ],
            },
        }

    events = [assistant_with_bash("npm test auth") for _ in range(4)]
    traj = distiller.distill(events)
    assert any("Repeated command" in line for line in traj.loops_detected)


def test_parse_jsonl_skips_bad_lines(tmp_path: Path) -> None:
    f = tmp_path / "s.jsonl"
    f.write_text(
        json.dumps({"type": "user", "timestamp": _ts(1)})
        + "\n"
        + "not-json\n"
        + json.dumps({"type": "assistant", "timestamp": _ts(1)})
        + "\n"
    )
    events = distiller.parse_jsonl(f)
    assert len(events) == 2
