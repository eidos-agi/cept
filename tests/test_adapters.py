import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from cept import adapters
from cept.core import run_cept


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_file_adapter_normalizes_agent_neutral_jsonl(tmp_path: Path) -> None:
    transcript = tmp_path / "agent.jsonl"
    _write_jsonl(
        transcript,
        [
            {
                "timestamp": "2026-05-23T12:00:00+00:00",
                "role": "user",
                "text": "please fix the failing auth test",
                "cwd": str(tmp_path),
            },
            {
                "timestamp": "2026-05-23T12:01:00+00:00",
                "type": "tool_call",
                "tool": "shell",
                "input": {"command": "pytest tests/test_auth.py"},
            },
            {
                "timestamp": "2026-05-23T12:02:00+00:00",
                "type": "tool_result",
                "is_error": True,
                "content": "AssertionError: callback missing state",
            },
        ],
    )

    source = adapters.FileTranscriptAdapter(transcript)
    loaded = source.load(cwd=tmp_path, session_id=None, cept_id=None)

    assert loaded.adapter == "file"
    assert loaded.session_id == "agent"
    assert loaded.path == transcript
    assert loaded.events[0]["type"] == "user"
    assert loaded.events[0]["message"]["content"] == "please fix the failing auth test"
    assert loaded.events[1]["type"] == "assistant"
    assert loaded.events[1]["message"]["content"][0]["type"] == "tool_use"
    assert loaded.events[1]["message"]["content"][0]["name"] == "Bash"
    assert loaded.events[2]["message"]["content"][0]["type"] == "tool_result"


def test_run_cept_dry_run_accepts_file_transcript_without_claude_session(tmp_path: Path) -> None:
    transcript = tmp_path / "any-agent.jsonl"
    now = datetime.now(UTC).isoformat()
    _write_jsonl(
        transcript,
        [
            {"timestamp": now, "role": "user", "text": "can you fix this test?", "cwd": str(tmp_path)},
            {
                "timestamp": now,
                "type": "tool_call",
                "tool": "shell",
                "input": {"command": "pytest tests/test_any_agent.py"},
            },
        ],
    )

    result = run_cept(
        goal="prove adapter support",
        headline="prove adapter support",
        cwd=tmp_path,
        transcript=str(transcript),
        dry_run=True,
        include_repo_state=False,
    )

    assert result["session"]["adapter"] == "file"
    assert result["session"]["path"] == str(transcript)
    assert result["packet"]["recent_trajectory"]["user_intents"] == ["can you fix this test?"]
    assert result["packet"]["recent_trajectory"]["attempts"] == [
        "Bash: pytest tests/test_any_agent.py"
    ]


def test_file_adapter_rejects_malformed_rows_with_line_number(tmp_path: Path) -> None:
    transcript = tmp_path / "bad-agent.jsonl"
    _write_jsonl(
        transcript,
        [
            {"timestamp": "2026-05-23T12:00:00+00:00", "role": "user", "text": "ok"},
            {"timestamp": "2026-05-23T12:01:00+00:00", "type": "tool_call", "tool": "shell"},
        ],
    )

    with pytest.raises(adapters.TranscriptValidationError) as exc:
        adapters.FileTranscriptAdapter(transcript).load(cwd=tmp_path, session_id=None, cept_id=None)

    assert str(transcript) in str(exc.value)
    assert "line 2" in str(exc.value)
    assert "input" in str(exc.value)
